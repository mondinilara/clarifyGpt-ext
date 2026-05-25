# Passo a passo para rodar o ClarifyGPT MBPP

Este arquivo lista os comandos para preparar dados e rodar o pipeline MBPP.

## 1. Entrar no projeto

```powershell
cd C:\Users\laram\Desenvolvimento\_doutorado\ClarifyGPT
```

## 2. Ativar o ambiente Python

Este passo descreve como ativar o ambiente virtual Python criado para o projeto ClarifyGPT. 
Ative o ambiente virtual antes de executar qualquer comando ou script do projeto para garantir 
que todas as dependências corretas sejam utilizadas.

### No Windows:

Se o `.venv` já existe:

```powershell
.\.venv\Scripts\Activate.ps1
```

Se ainda não existir:

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
```

## 3. Instalar dependências

```powershell
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
```

## 4. Configurar OpenAI API

Na janela atual do PowerShell:

```powershell
$env:OPENAI_API_KEY = "SEU_TOKEN_AQUI"
$env:OPENAI_MODEL = "gpt-4o"
```

Para conferir:

```powershell
$env:OPENAI_API_KEY
$env:OPENAI_MODEL
```

### Alternativa: DeepSeek API

A API do DeepSeek usa formato compatível com OpenAI. Para usar DeepSeek em vez de OpenAI:

```powershell
$env:LLM_PROVIDER = "deepseek"
$env:DEEPSEEK_API_KEY = "SEU_TOKEN_DEEPSEEK_AQUI"
$env:DEEPSEEK_MODEL = "deepseek-v4-flash"
```

Para conferir:

```powershell
$env:LLM_PROVIDER
$env:DEEPSEEK_API_KEY
$env:DEEPSEEK_MODEL
```

Para voltar para OpenAI:

```powershell
$env:LLM_PROVIDER = "openai"
```

### Alternativa: OpenRouter

Para usar OpenRouter:

```powershell
$env:LLM_PROVIDER = "openrouter"
$env:OPENROUTER_API_KEY = "SEU_TOKEN_OPENROUTER_AQUI"
$env:OPENROUTER_MODEL = "deepseek/deepseek-chat-v3-0324:free"
```

Opcionalmente:

```powershell
$env:OPENROUTER_HTTP_REFERER = "http://localhost"
$env:OPENROUTER_APP_TITLE = "ClarifyGPT"
```

Para conferir:

```powershell
$env:LLM_PROVIDER
$env:OPENROUTER_API_KEY
$env:OPENROUTER_MODEL
```

## 5. Preparar o dataset MBPP

```powershell
python src\prepare_mbpp_data.py
```

Isso gera:

```text
src\data\mbpp_sanitized_microsoft.jsonl
src\data\mbpp_tests_final.jsonl
```

O MBPP sanitized baixado aqui tem **427 tarefas**.

## 6. Sobre o número de códigos por prompt

No artigo/repo original, o ClarifyGPT usa **25 códigos por prompt**.

Com 427 prompts:

```text
427 * 25 = 10675 gerações de código
```

Se você quiser usar menos, escolha um número `N`.

Exemplo com 3 códigos por prompt:

```text
N = 3
427 * 3 = 1281 gerações de código
```

Esse valor precisa ficar consistente em dois lugares:

1. Na geração/criação do arquivo de amostras.
2. Na etapa `needcq`, usando `--samples-per-task N`.

## 7. Smoke test com arquivos fake, usando N = 3

Os arquivos fake usam soluções de referência do MBPP, não GPT-4.

Eles servem para testar formato, caminhos e execução básica.

Aqui o número de códigos por prompt é configurado no primeiro lugar:

```powershell
python src\prepare_mbpp_data.py --write-reference-samples --samples-per-task 3
```

Esse comando gera 3 amostras fake por tarefa.

Depois o mesmo número precisa ser informado na etapa `needcq`, que é o segundo lugar:

```powershell
python src\clarify\run_clarify_gpt4_mbpp.py --stage needcq --force --samples-per-task 3 --limit 5
```

Resultado esperado com fake: `src\data\mbpp_needcq_gpt4.jsonl` pode ficar vazio.

Isso é normal, porque as amostras fake são repetidas ou equivalentes e não produzem divergência.

## 8. Experimento real

Para o experimento real, você precisa de um arquivo com gerações reais do modelo:

```text
src\data\mbpp_sanitized_microsoft_sample_0.8_25_results_final_gpt4.jsonl
```

Se usar menos de 25, o arquivo pode manter o mesmo nome por enquanto, mas precisa ter:

```text
427 * N linhas
```

Exemplo com `N = 3`:

```text
427 * 3 = 1281 linhas
```

Cada linha deve representar uma geração de código para uma tarefa.

O campo importante é:

```json
{
  "task_id": 2,
  "prompt": "...",
  "raw_code_completion": "..."
}
```

## 9. Rodar o pipeline com menos amostras

Supondo que você tem `N = 3` gerações reais por tarefa:

```powershell
python src\clarify\run_clarify_gpt4_mbpp.py --stage needcq --force --samples-per-task 3
```

Depois:

```powershell
python src\clarify\run_clarify_gpt4_mbpp.py --stage askcq
python src\clarify\run_clarify_gpt4_mbpp.py --stage answercq
python src\clarify\run_clarify_gpt4_mbpp.py --stage synthesize
python src\clarify\run_clarify_gpt4_mbpp.py --stage final
```

Ou tudo de uma vez:

```powershell
python src\clarify\run_clarify_gpt4_mbpp.py --stage all --force --samples-per-task 3
```

Para testar em poucas tarefas antes de gastar com tudo:

```powershell
python src\clarify\run_clarify_gpt4_mbpp.py --stage all --force --samples-per-task 3 --limit 5
```

Observação: `--limit` só limita a etapa `needcq`. As etapas seguintes rodam sobre o arquivo `mbpp_needcq_gpt4.jsonl` que foi gerado por ela.

## 10. O que cada etapa faz

### `needcq`

Lê as soluções candidatas.

Compara os resultados nos testes.

Gera:

```text
src\data\mbpp_needcq_gpt4.jsonl
```

### `askcq`

Chama a OpenAI API para gerar perguntas de esclarecimento.

### `answercq`

Chama a OpenAI API para gerar respostas simuladas.

### `synthesize`

Chama a OpenAI API para gerar uma nova solução com requisito refinado.

### `final`

Gera o arquivo final para avaliação.

## 11. Cuidado com custo

As etapas que chamam API são:

```text
askcq
answercq
synthesize
```

A etapa `needcq` não deveria chamar API. Ela só executa e compara códigos já gerados.

O arquivo de amostras de código real também custa chamadas de modelo, mas essa geração ainda precisa ser feita/automatizada separadamente.

## 12. Resumo rápido

Smoke test com 3 amostras fake:

```powershell
cd C:\Users\laram\Desenvolvimento\_doutorado\ClarifyGPT
.\.venv\Scripts\Activate.ps1
$env:OPENAI_API_KEY = "SEU_TOKEN_AQUI"
$env:OPENAI_MODEL = "gpt-4o"
python -m pip install -r requirements.txt
python src\prepare_mbpp_data.py --write-reference-samples --samples-per-task 3
python src\clarify\run_clarify_gpt4_mbpp.py --stage needcq --force --samples-per-task 3 --limit 5
```

Gerar samples reais com DeepSeek, usando 3 amostras e 5 tarefas primeiro:

```powershell
cd C:\Users\laram\Desenvolvimento\_doutorado\ClarifyGPT
.\.venv\Scripts\Activate.ps1
$env:LLM_PROVIDER = "deepseek"
$env:DEEPSEEK_API_KEY = "SEU_TOKEN_DEEPSEEK_AQUI"
$env:DEEPSEEK_MODEL = "deepseek-v4-flash"
python src\generate_mbpp_samples.py --samples-per-task 3 --limit 5 --sleep-between-tasks 2 --force
python src\clarify\run_clarify_gpt4_mbpp.py --stage all --force --samples-per-task 3 --limit 5
```

Gerar samples reais com OpenRouter, usando 3 amostras e 5 tarefas primeiro:

```powershell
cd C:\Users\laram\Desenvolvimento\_doutorado\ClarifyGPT
.\.venv\Scripts\Activate.ps1
$env:LLM_PROVIDER = "openrouter"
$env:OPENROUTER_API_KEY = "SEU_TOKEN_OPENROUTER_AQUI"
$env:OPENROUTER_MODEL = "deepseek/deepseek-chat-v3-0324:free"
python src\generate_mbpp_samples.py --samples-per-task 3 --limit 5 --sleep-between-tasks 2 --force
python src\clarify\run_clarify_gpt4_mbpp.py --stage all --force --samples-per-task 3 --limit 5
```

Experimento real com 3 amostras por tarefa, depois de gerar/substituir o arquivo de amostras reais:

```powershell
python src\clarify\run_clarify_gpt4_mbpp.py --stage all --force --samples-per-task 3
```

## 13. Onde ajustar o número de amostras

Para fake/reference samples:

```powershell
python src\prepare_mbpp_data.py --write-reference-samples --samples-per-task 3
python src\clarify\run_clarify_gpt4_mbpp.py --stage needcq --force --samples-per-task 3
```

ATENÇÃO: depois que você gerar amostras reais com IA, **não rode de novo**:

```powershell
python src\prepare_mbpp_data.py --write-reference-samples --samples-per-task 3
```

Esse comando sobrescreve:

```text
src\data\mbpp_sanitized_microsoft_sample_0.8_25_results_final_gpt4.jsonl
```

com amostras fake/reference, apagando o arquivo de amostras reais gerado pela IA.

Se precisar apenas regenerar os arquivos base do dataset, rode sem `--write-reference-samples`:

```powershell
python src\prepare_mbpp_data.py
```

Para samples reais de GPT, use:

```powershell
python src\generate_mbpp_samples.py --samples-per-task 3 --force
```

Para testar antes com poucas tarefas:

```powershell
python src\generate_mbpp_samples.py --samples-per-task 3 --limit 5 --sleep-between-tasks 2 --force
```

Depois o pipeline deve rodar com o mesmo valor:

```powershell
python src\clarify\run_clarify_gpt4_mbpp.py --stage all --force --samples-per-task 3
```

Se você gerou samples reais só com `--limit 5`, rode o pipeline também com `--limit 5`:

```powershell
python src\clarify\run_clarify_gpt4_mbpp.py --stage all --force --samples-per-task 3 --limit 5
```

Se aparecer erro `429`, aumente a pausa:

```powershell
python src\generate_mbpp_samples.py --samples-per-task 3 --limit 5 --sleep-between-tasks 10 --force
```

Se o corpo do erro mencionar `insufficient_quota`, `billing` ou `quota`, não é velocidade; é limite de crédito, billing ou orçamento da conta/projeto.

## 14. Se aparecer muito `error!!!`

Se a etapa `needcq` mostrar muitas linhas assim:

```text
['error!!!', 'error!!!', 'error!!!']
```

regenere os arquivos de dados e amostras com o mesmo `--samples-per-task` que você vai usar no `needcq`.

Exemplo com `N = 3`:

```powershell
python src\prepare_mbpp_data.py --input-jsonl src\data\mbpp_sanitized_microsoft.jsonl
python src\clarify\run_clarify_gpt4_mbpp.py --stage needcq --force --samples-per-task 3 --limit 5
```

Os avisos do tipo abaixo podem aparecer por causa de strings do próprio dataset:

```text
SyntaxWarning: "\w" is an invalid escape sequence
```

Esses avisos não são necessariamente fatais.
