# Passo a passo para rodar o ClarifyGPT MBPP

Este arquivo lista os comandos para preparar dados e rodar o pipeline MBPP.

## 1. Entrar no projeto

```powershell
cd C:\Users\laram\Desenvolvimento\_doutorado\ClarifyGPT
```

## 2. Ativar o ambiente Python

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

## 7. Smoke test com arquivos fake

Os arquivos fake usam soluções de referência do MBPP, não GPT-4.

Eles servem para testar formato, caminhos e execução básica.

Exemplo com 3 códigos por prompt:

```powershell
python src\prepare_mbpp_data.py --write-reference-samples --samples-per-task 3
```

Depois rode só algumas tarefas:

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

## 10.1. Qual comando gera qual arquivo

| Etapa | Comando | O que faz | Arquivo gerado |
| --- | --- | --- | --- |
| Preparar dataset | `python src\prepare_mbpp_data.py` | Baixa/converte o MBPP sanitized para o formato esperado pelo repo. | `src\data\mbpp_sanitized_microsoft.jsonl` e `src\data\mbpp_tests_final.jsonl` |
| Gerar samples reais | `python src\generate_mbpp_samples.py --samples-per-task 3 --force` | Chama o modelo e gera N soluções candidatas por tarefa. | `src\data\mbpp_sanitized_microsoft_sample_0.8_25_results_final_gpt4.jsonl` |
| Detectar tarefas ambíguas | `python src\clarify\run_clarify_gpt4_mbpp.py --stage needcq --force --samples-per-task 3` | Executa as soluções candidatas nos testes e identifica tarefas com comportamentos divergentes. | `src\data\mbpp_needcq_gpt4.jsonl` |
| Gerar perguntas | `python src\clarify\run_clarify_gpt4_mbpp.py --stage askcq --force` | Chama o modelo para criar perguntas de esclarecimento para cada tarefa em `mbpp_needcq_gpt4.jsonl`. | `src\data\generated\mbpp_askcq_three_shot_0_gpt4_results.jsonl` |
| Gerar respostas | `python src\clarify\run_clarify_gpt4_mbpp.py --stage answercq --force` | Chama o modelo para criar respostas simuladas para as perguntas. | `src\data\generated\mbpp_answercq_three_shot_0_gpt4_results.jsonl` |
| Sintetizar solução refinada | `python src\clarify\run_clarify_gpt4_mbpp.py --stage synthesize --force` | Usa requisito original, perguntas e respostas para gerar uma solução refinada. | `src\data\generated\mbpp_synthesize_three_shot_0_gpt4_results.jsonl` |
| Montar arquivo final | `python src\clarify\run_clarify_gpt4_mbpp.py --stage final --force` | Monta o arquivo final para avaliação; usa soluções refinadas quando existirem e baseline/greedy nas demais. | `src\data\generated\mbpp_final_three_shot_gpt4_0.jsonl` |

Exemplo usando `--samples-per-task 15` e somente 32 tarefas:

```powershell
python src\clarify\run_clarify_gpt4_mbpp.py --stage needcq --force --samples-per-task 15 --limit 32
python src\clarify\run_clarify_gpt4_mbpp.py --stage askcq --force
python src\clarify\run_clarify_gpt4_mbpp.py --stage answercq --force
python src\clarify\run_clarify_gpt4_mbpp.py --stage synthesize --force
python src\clarify\run_clarify_gpt4_mbpp.py --stage final --force
```

Se a etapa `needcq` ficar presa no Windows, provavelmente algum codigo gerado pelo modelo entrou em loop ou demorou demais para executar. Use `--test-timeout` para limitar cada execucao de teste:

```powershell
python src\clarify\run_clarify_gpt4_mbpp.py --stage needcq --force --samples-per-task 25 --limit 214 --test-timeout 0.2
```

Se muitos resultados virarem `error!!!`, tente um timeout um pouco maior:

```powershell
python src\clarify\run_clarify_gpt4_mbpp.py --stage needcq --force --samples-per-task 25 --limit 214 --test-timeout 1.0
```

Depois de rodar, confira as contagens:

```powershell
(Get-Content src\data\mbpp_needcq_gpt4.jsonl).Count
(Get-Content src\data\generated\mbpp_askcq_three_shot_0_gpt4_results.jsonl).Count
(Get-Content src\data\generated\mbpp_answercq_three_shot_0_gpt4_results.jsonl).Count
(Get-Content src\data\generated\mbpp_synthesize_three_shot_0_gpt4_results.jsonl).Count
(Get-Content src\data\generated\mbpp_final_three_shot_gpt4_0.jsonl).Count
```

As três etapas abaixo devem ter a mesma quantidade de linhas que `mbpp_needcq_gpt4.jsonl`:

```text
mbpp_askcq_three_shot_0_gpt4_results.jsonl
mbpp_answercq_three_shot_0_gpt4_results.jsonl
mbpp_synthesize_three_shot_0_gpt4_results.jsonl
```

Se `needcq` tem linhas, mas `askcq`, `answercq` ou `synthesize` ficaram com `0`, o pipeline não aplicou ClarifyGPT nessas tarefas. Nesse caso, rerode a etapa que ficou vazia e veja o erro no terminal.


## 10.2. Avaliar o resultado final

Antes de avaliar, confirme se o arquivo final existe:

```powershell
Test-Path src\data\generated\mbpp_final_three_shot_gpt4_0.jsonl
```

Se retornar `False`, gere o arquivo final:

```powershell
python src\clarify\run_clarify_gpt4_mbpp.py --stage final --force
```

Depois rode a avaliação:

```powershell
python evaluation\MBPP\main.py `
  --source_path_for_solution src\data\mbpp_sanitized_microsoft.jsonl `
  --predict_path_for_solution src\data\generated\mbpp_final_three_shot_gpt4_0.jsonl
```

Esse comando executa os testes do MBPP contra as soluções finais e gera:

```text
src\data\generated\mbpp_final_three_shot_gpt4_0.results_jsonl
```

Também imprime no terminal as métricas, incluindo `pass@1`.

No MBPP, os testes são `assert ...` diretos. Diferente do HumanEval, eles não usam uma função `check(...)`.

Se você rodou só um recorte com `--limit`, a avaliação ainda usa o arquivo final montado com 427 linhas. Nesse caso, as tarefas fora do recorte tendem a vir do baseline/greedy, não do ClarifyGPT refinado.

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

Experimento real com 3 amostras por tarefa, depois de gerar/substituir o arquivo de amostras reais:

```powershell
python src\clarify\run_clarify_gpt4_mbpp.py --stage all --force --samples-per-task 3
```
