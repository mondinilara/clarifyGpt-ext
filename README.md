# ClarifyGPT explicado

Este repositório é um pacote de replicação do artigo **ClarifyGPT: A Framework for Enhancing LLM-based Code Generation via Requirement Clarification**.

A ideia central é testar se um modelo de linguagem gera código melhor quando ele primeiro identifica requisitos ambíguos, faz perguntas de esclarecimento, recebe respostas simuladas e só depois gera a solução final.

## Visão geral do fluxo

O pipeline do ClarifyGPT tem cinco etapas principais:

1. Gerar várias soluções candidatas para cada problema.
2. Executar essas soluções nos testes disponíveis.
3. Detectar problemas em que as soluções se comportam de formas diferentes.
4. Para esses problemas, pedir ao modelo perguntas de esclarecimento e respostas simuladas.
5. Reescrever/refinar o requisito e gerar uma solução final.

Em formato de dados, o fluxo fica assim:

```text
dataset original
  -> amostras do modelo, 25 soluções por tarefa
  -> needcq, tarefas que precisam de clarification questions
  -> askcq, perguntas de esclarecimento
  -> answercq, respostas simuladas
  -> synthesize, nova solução usando o requisito refinado
  -> final, arquivo pronto para avaliação
```

## Estrutura do repositório

```text
baseline/
evaluation/
RQ2/
RQ3/
src/
README_COMANDOS.md
README.md
requirements.txt
```

## Perguntas de pesquisa deste projeto

Este workspace ficou organizado em três frentes experimentais:

| RQ | Nome | Objetivo | Pasta principal |
| --- | --- | --- | --- |
| RQ1 | Reprodução do ClarifyGPT | Fazer o pipeline original rodar localmente no MBPP, incluindo geração de samples, `needcq`, `askcq`, `answercq`, `synthesize`, `final` e avaliação. | `src/`, `evaluation/`, `README_COMANDOS.md` |
| RQ2 | Stress Test de Data Leakage | Aplicar transformações semânticas no MBPP para reduzir correspondência superficial com dados de treino. | `RQ2/` |
| RQ3 | Otimização de Prompt | Comparar o prompt original do artigo com uma versão mais curta, medindo redução de tokens e impacto em precisão. | `RQ3/` |

### RQ1 - Reprodução do ClarifyGPT

A RQ1 é o que este README já descreve nas seções principais: preparar o MBPP, gerar amostras de código, detectar tarefas ambíguas, gerar perguntas/respostas de esclarecimento, sintetizar uma solução final e avaliar com `pass@k`.

Os principais ajustes feitos para conseguir reproduzir o pipeline localmente foram:

- criação de `src/prepare_mbpp_data.py` para preparar o MBPP sanitized;
- criação de `src/generate_mbpp_samples.py` para gerar amostras reais via API;
- adaptação de `src/clarify/gpt4_utils.py` para OpenAI/OpenRouter/DeepSeek via variáveis de ambiente;
- ajuste de `src/clarify/run_clarify_gpt4_mbpp.py` para rodar por etapas com `--stage`;
- suporte a `--samples-per-task`, `--limit`, `--force` e caminhos customizados;
- correções na avaliação MBPP para rodar melhor no Windows;
- criação de `src/create_mbpp_eval_subset.py` para avaliar apenas o recorte realmente gerado.

O passo a passo operacional da RQ1 está em:

```text
README_COMANDOS.md
```

### RQ2 - Stress Test de Data Leakage

A RQ2 cria uma versão transformada do MBPP para testar se o desempenho depende de pistas superficiais do benchmark original.

A pasta principal é:

```text
RQ2/
```

Arquivos principais:

```text
RQ2/README.md
RQ2/transform_mbpp_rq2.py
RQ2/transform_mbpp_rq2.ps1
RQ2/create_rq2_final_inputs.py
RQ2/create_rq2_final_inputs.ps1
RQ2/data/
```

Transformações aplicadas:

- renomeação da função para `rq2_task_<task_id>`;
- renomeação dos argumentos para `rq2_arg_<position>`;
- reordenação dos argumentos no prompt quando havia pelo menos dois parâmetros;
- atualização correspondente das chamadas nos testes para preservar a semântica;
- parafraseamento determinístico do docstring;
- geração de relatório por tarefa em `RQ2/data/mbpp_rq2_transform_report.jsonl`.

Exemplo:

```python
def similar_elements(test_tup1, test_tup2):
    '''
    Write a function to find the shared elements from the given two lists.
    '''
```

vira:

```python
def rq2_task_2(rq2_arg_2, rq2_arg_1):
    '''
Implement a function that compute the shared elements from the provided two lists.
    '''
```

O README específico da RQ2 explica como gerar os dados transformados, rodar o pipeline e criar o arquivo final sem reutilizar baseline do MBPP original:

```text
RQ2/README.md
```

### RQ3 - Otimização de Prompt

A RQ3 compara os prompts originais do ClarifyGPT com uma versão otimizada e mais curta.

A pasta principal é:

```text
RQ3/
```

Arquivos principais:

```text
RQ3/README.md
RQ3/prompt_mbpp_optimized.py
RQ3/measure_prompt_tokens.py
RQ3/measure_prompt_tokens.ps1
RQ3/token_reduction_report.json
```

O que foi alterado:

- os prompts `three_shot` de `askcq`, `answercq` e `synthesize` foram resumidos;
- as instruções longas foram convertidas em regras objetivas;
- os exemplos few-shot foram mantidos, mas com análises e respostas mais diretas;
- a estrutura de saída foi preservada: `### Analysis`, `### Clarifying Questions`, `### Answers` e código final;
- o runner `src/clarify/run_clarify_gpt4_mbpp.py` passou a aceitar `--prompt-module`, permitindo alternar entre prompt original e otimizado sem editar o prompt original.

Redução estimada nos prompts estáticos `three_shot`:

| Etapa | Original | Otimizado | Redução | Redução % |
| --- | ---: | ---: | ---: | ---: |
| `askcq` | 1269 | 782 | 487 | 38.38% |
| `answercq` | 1012 | 689 | 323 | 31.92% |
| `synthesize` | 1016 | 482 | 534 | 52.56% |
| **Total** | **3297** | **1953** | **1344** | **40.76%** |

Esses números foram gerados em `RQ3/token_reduction_report.json` usando estimativa regex. Com `tiktoken` instalado, eles podem ser recalculados com:

```powershell
python RQ3\measure_prompt_tokens.py
```

Na RQ3, normalmente não se roda `prepare_mbpp_data`, `generate_mbpp_samples` nem `needcq` novamente. A ideia é reaproveitar dataset, samples e tarefas ambíguas do experimento base para isolar uma única variável: o prompt usado em `askcq`, `answercq` e `synthesize`.

### `src/`

É onde fica a implementação principal do ClarifyGPT.

```text
src/
  clarify/
  prompt/
  parallel_request.py
  prepare_mbpp_data.py
  data/
```

### `src/clarify/`

Contém os scripts que executam o método.

```text
src/clarify/
  run_clarify_gpt4_mbpp.py
  run_clarify_gpt4_humaneval.py
  run_clarify_chatgpt_mbpp.py
  run_clarify_chatgpt_humaneval.py
  gpt4_utils.py
  utils.py
```

Os nomes seguem o padrão:

```text
run_clarify_{modelo}_{benchmark}.py
```

Exemplos:

- `run_clarify_gpt4_mbpp.py`: versão GPT-4 para MBPP.
- `run_clarify_chatgpt_mbpp.py`: versão ChatGPT/GPT-3.5 para MBPP.
- `run_clarify_gpt4_humaneval.py`: versão GPT-4 para HumanEval.
- `run_clarify_chatgpt_humaneval.py`: versão ChatGPT/GPT-3.5 para HumanEval.

O arquivo mais importante para o seu uso atual é:

```text
src/clarify/run_clarify_gpt4_mbpp.py
```

Ele foi ajustado para rodar por etapas com `--stage`.

### `src/prompt/`

Guarda os prompts usados para pedir ao modelo:

- perguntas de esclarecimento;
- respostas simuladas;
- síntese/refinamento do requisito;
- geração de código final.

Arquivos principais:

```text
src/prompt/prompt_mbpp.py
src/prompt/prompt_humaneval.py
```

### `src/parallel_request.py`

Script auxiliar para disparar várias chamadas à API da OpenAI em paralelo.

Ele é usado principalmente pelos scripts `chatgpt_*`. Em vez de chamar o modelo uma vez por vez, ele lê um arquivo `.jsonl` de requisições, chama a API com controle de taxa e salva outro `.jsonl` com os resultados.

### `src/clarify/gpt4_utils.py`

Wrapper simples para chamada de modelo pela API normal da OpenAI.

Por padrão ele lê:

```text
OPENAI_API_KEY
OPENAI_MODEL
OPENAI_API_URL
```

Se `OPENAI_MODEL` não for informado, usa `gpt-4o`. Se `OPENAI_API_URL` não for informado, usa `https://api.openai.com/v1/chat/completions`.

Você também pode substituir `COLE_SEU_TOKEN_AQUI` no arquivo, mas a forma recomendada é usar variável de ambiente para não salvar chave no código.

### `src/clarify/utils.py`

Funções auxiliares para:

- limpar blocos de código retornados pelo modelo;
- extrair código sem o prompt;
- parsear perguntas e respostas;
- montar a versão refinada do requisito.

### `src/prepare_mbpp_data.py`

Script criado para facilitar a preparação inicial do MBPP.

Ele baixa/converte o dataset MBPP sanitized oficial e gera os arquivos base esperados pelo ClarifyGPT:

```text
src/data/mbpp_sanitized_microsoft.jsonl
src/data/mbpp_tests_final.jsonl
```

Também consegue gerar arquivos fake com soluções de referência para smoke test:

```text
src/data/mbpp_sanitized_microsoft_sample_0.8_25_results_final_gpt4.jsonl
src/data/gpt4_greedy_mbpp/mbpp_sanitized_microsoft_greedy_0.0_3_results_final_gpt4_1.jsonl
```

Esses arquivos fake servem para testar formato e fluxo, mas não reproduzem o experimento.

## `evaluation/`

Contém scripts de avaliação, principalmente para MBPP.

```text
evaluation/MBPP/
  main.py
  postprocess.py
  execution.py
  _execution.py
  evaluation.py
  io_utils.py
```

### `evaluation/MBPP/main.py`

Ponto de entrada da avaliação.

Ele lê:

- um arquivo de tarefas/dataset original;
- um arquivo de predições do modelo.

Depois executa os testes e calcula métricas como `pass@k`.

Exemplo:

```powershell
python evaluation\MBPP\main.py `
  --source_path_for_solution src\data\mbpp_sanitized_microsoft.jsonl `
  --predict_path_for_solution src\data\generated\mbpp_final_three_shot_gpt4_0.jsonl
```

### `evaluation/MBPP/postprocess.py`

Converte o formato produzido pelo modelo para o formato que o avaliador espera.

Ele associa cada predição ao `task_id` correto a partir do `prompt`.

### `evaluation/MBPP/execution.py` e `_execution.py`

Executam código gerado contra os testes.

Observação: parte desse código veio de ambientes Unix/Linux e usa recursos como `signal` e `libgcc_s.so.1`. No Windows, isso pode exigir ajustes adicionais.

## `baseline/`

Contém uma cópia do projeto `gpt-engineer`, usado como baseline no trabalho.

Ele tem seu próprio `pyproject.toml`, testes e estrutura interna. Para entender/rodar o ClarifyGPT em MBPP, você não precisa começar por essa pasta.

## Arquivos de dados

O repositório original não traz todos os arquivos `.jsonl` necessários para reproduzir o experimento completo.

Arquivos base que conseguimos gerar:

```text
src/data/mbpp_sanitized_microsoft.jsonl
src/data/mbpp_tests_final.jsonl
```

Arquivo necessário para o experimento real, mas não publicado no repo:

```text
src/data/mbpp_sanitized_microsoft_sample_0.8_25_results_final_gpt4.jsonl
```

Esse arquivo deveria conter 25 gerações GPT-4 por tarefa MBPP.

Com arquivos fake, ele contém 25 cópias da solução de referência. Isso é útil para teste de formato, mas não para resultado experimental.

## Setup inicial

Na raiz do projeto:

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
```

Prepare o MBPP:

```powershell
python src\prepare_mbpp_data.py
```

Para gerar arquivos fake de smoke test:

```powershell
python src\prepare_mbpp_data.py --write-reference-samples
```

## Rodando smoke test

Com arquivos fake, rode uma etapa pequena:

```powershell
python src\clarify\run_clarify_gpt4_mbpp.py --stage needcq --force --limit 5
```

Resultado esperado: `src/data/mbpp_needcq_gpt4.jsonl` pode ficar vazio.

Isso é normal, porque as soluções fake são repetidas e não há divergência entre candidatas.

## Rodando o experimento real

Para o experimento real, você precisa gerar ou obter amostras reais do modelo:

```text
src/data/mbpp_sanitized_microsoft_sample_0.8_25_results_final_gpt4.jsonl
```

Esse arquivo deve ter:

- 427 tarefas;
- 25 soluções por tarefa;
- 10675 linhas no total;
- campos como `task_id`, `prompt` e `raw_code_completion`.

Depois disso, o fluxo fica:

```powershell
python src\clarify\run_clarify_gpt4_mbpp.py --stage needcq --force
python src\clarify\run_clarify_gpt4_mbpp.py --stage askcq
python src\clarify\run_clarify_gpt4_mbpp.py --stage answercq
python src\clarify\run_clarify_gpt4_mbpp.py --stage synthesize
python src\clarify\run_clarify_gpt4_mbpp.py --stage final
```

Ou tudo de uma vez:

```powershell
python src\clarify\run_clarify_gpt4_mbpp.py --stage all
```

## O que cada etapa faz

### `needcq`

Lê as 25 soluções por tarefa.

Executa cada solução nos testes.

Se encontrar comportamentos diferentes, salva a tarefa em:

```text
src/data/mbpp_needcq_gpt4.jsonl
```

Essa etapa identifica quais tarefas parecem ambíguas.

### `askcq`

Para cada tarefa ambígua, pede ao modelo perguntas de esclarecimento.

Saída padrão:

```text
src/data/generated/mbpp_askcq_three_shot_0_gpt4_results.jsonl
```

### `answercq`

Pede ao modelo respostas simuladas para as perguntas.

Saída padrão:

```text
src/data/generated/mbpp_answercq_three_shot_0_gpt4_results.jsonl
```

### `synthesize`

Combina:

- requisito original;
- perguntas;
- respostas;
- prompt de síntese.

Depois pede ao modelo uma nova solução.

Saída padrão:

```text
src/data/generated/mbpp_synthesize_three_shot_0_gpt4_results.jsonl
```

### `final`

Gera o arquivo final de predições para avaliação.

Saída padrão:

```text
src/data/generated/mbpp_final_three_shot_gpt4_0.jsonl
```

## Limitações importantes

Este repo não está pronto para reprodução completa logo após o clone.

Pontos faltantes ou frágeis:

- não traz todos os datasets/intermediários usados pelos autores;
- `gpt4_utils.py` vem com endpoint e chave fictícios;
- os scripts misturam formatos de saída antigos e novos da API;
- partes da avaliação MBPP podem precisar de ajustes no Windows;
- os arquivos fake servem apenas para testar caminho e formato.

## Resumo mental

Pense neste repo como três blocos:

```text
Dados
  MBPP/HumanEval e gerações do modelo

ClarifyGPT
  detecta ambiguidade, pergunta, responde, sintetiza e gera solução

Avaliação
  executa testes e calcula pass@k
```

O principal gargalo não é o Python em si. É reconstruir os arquivos de dados intermediários que os autores usaram, especialmente as 25 gerações por tarefa.
