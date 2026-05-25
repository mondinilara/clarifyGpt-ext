import os
import random
import time
from typing import Dict, List, Tuple, Callable, Union

import requests


class Role:
    SYSTEM = "system"
    USER = "user"
    ASSISTANT = "assistant"


class FewShotLLM(object):
    def __init__(self, **kwargs) -> None:
        self.provider = kwargs.get('provider') or os.getenv('LLM_PROVIDER', 'openai').lower()
        if self.provider == 'deepseek':
            self.url = kwargs.get('url') or os.getenv('DEEPSEEK_API_URL', 'https://api.deepseek.com/chat/completions')
            self.model = kwargs.get('model') or os.getenv('DEEPSEEK_MODEL', 'deepseek-v4-flash')
            self.api_key = kwargs.get('api_key') or os.getenv('DEEPSEEK_API_KEY') or 'COLE_SEU_TOKEN_AQUI'
        elif self.provider == 'openrouter':
            self.url = kwargs.get('url') or os.getenv(
                'OPENROUTER_API_URL',
                'https://openrouter.ai/api/v1/chat/completions',
            )
            self.model = kwargs.get('model') or os.getenv('OPENROUTER_MODEL', 'deepseek/deepseek-chat-v3-0324:free')
            self.api_key = kwargs.get('api_key') or os.getenv('OPENROUTER_API_KEY') or 'COLE_SEU_TOKEN_AQUI'
        else:
            self.url = kwargs.get('url') or os.getenv('OPENAI_API_URL', 'https://api.openai.com/v1/chat/completions')
            self.model = kwargs.get('model') or os.getenv('OPENAI_MODEL', 'gpt-4o')
            self.api_key = kwargs.get('api_key') or os.getenv('OPENAI_API_KEY') or 'COLE_SEU_TOKEN_AQUI'
        self.headers = {'Content-Type': 'application/json', 'Authorization': f'Bearer {self.api_key}'}
        if self.provider == 'openrouter':
            self.headers.update({
                'HTTP-Referer': os.getenv('OPENROUTER_HTTP_REFERER', 'http://localhost'),
                'X-Title': os.getenv('OPENROUTER_APP_TITLE', 'ClarifyGPT'),
            })

    def _generate_completion_prompt(self, messages: List[Dict[str, str]]) -> str:
        return "\n".join([message['content'] for message in messages])

    def _generate_chat_completion_messages(self,
                                           instruction: str,
                                           examples: List[Dict[str, str]],
                                           prompt: str) -> List[Dict[str, str]]:
        messages = [
            {"role": Role.SYSTEM, "content": instruction}
        ]

        if examples:
            for example in examples:
                messages.append({"role": Role.USER, "content": example[Role.USER]})
                messages.append({"role": Role.ASSISTANT, "content": example[Role.ASSISTANT]})

        messages.append({"role": Role.USER, "content": prompt})

        return messages

    def _request(self, max_tokens, temperature, n, messages: List[Dict[str, str]]) -> str:
        if self.api_key == 'COLE_SEU_TOKEN_AQUI':
            raise RuntimeError(
                'Configure sua chave em OPENAI_API_KEY, DEEPSEEK_API_KEY ou OPENROUTER_API_KEY, '
                'ou substitua COLE_SEU_TOKEN_AQUI em gpt4_utils.py.'
            )

        params = {"model": self.model, "max_tokens": max_tokens, "temperature": temperature, "n": n, "stop": None, "top_p": 0.95,
                  "messages": messages}

        resp = requests.post(self.url, json=params, headers=self.headers)
        resp.raise_for_status()

        return resp.json()

    def _retry_delay(self, error: Exception, attempt: int) -> float:
        response = getattr(error, 'response', None)
        if response is not None:
            retry_after = response.headers.get('retry-after')
            if retry_after:
                try:
                    return max(float(retry_after), 1.0)
                except ValueError:
                    pass

        return min(60.0, (2 ** attempt) + random.uniform(0, 1))

    def _error_body(self, error: Exception) -> str:
        response = getattr(error, 'response', None)
        if response is None:
            return ''

        try:
            return response.text[:1000]
        except Exception:
            return ''

    def _is_quota_error(self, error: Exception) -> bool:
        body = self._error_body(error).lower()
        return 'insufficient_quota' in body or 'billing' in body or 'quota' in body

    def _completion(self,
                    max_tokens: int,
                    temperature: float,
                    n: int,
                    instruction: str,
                    examples: List[Dict[str, str]],
                    prompt: str) -> List[str]:

        messages = self._generate_chat_completion_messages(instruction, examples, prompt)

        cnt = 0
        max_retries = 8
        while cnt < max_retries:
            try:
                return [self._request(max_tokens, temperature, n, messages)['choices'][i]['message']['content']
                        for i in range(n)]

            except Exception as e:
                body = self._error_body(e)
                if body:
                    print("[Response Body]", body)
                if self._is_quota_error(e):
                    raise RuntimeError(
                        'OpenAI retornou erro de quota/billing. Verifique billing, credits e usage limits no dashboard.'
                    ) from e

                delay = self._retry_delay(e, cnt)
                print("[Request Error]", e, f"retrying in {delay:.1f} secs...")
                time.sleep(delay)
                cnt += 1

        raise Exception(f"Fail to request OpenAI services with max_retries = {cnt}")


class CodeLLM(FewShotLLM):
    def generate_code(self,
                      max_tokens: int,
                      temperature: float,
                      n: int,
                      instruction: str,
                      examples: List[Dict[str, str]],
                      prompt: str,
                      extract_code_fn: Callable[[str], Union[str, Tuple[str, str]]]) -> Union[str, Tuple[str, str]]:
        completion = self._completion(max_tokens, temperature, n, instruction, examples, prompt)

        if extract_code_fn is not None:
            return extract_code_fn(completion)
        else:
            return completion
