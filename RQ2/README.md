# RQ2 - Stress Test de Data Leakage

Esta pasta contem os insumos para a RQ2:

> O desempenho do modelo se mantem quando removemos pistas superficiais que podem ter aparecido nos dados de treino?

A ideia e transformar os prompts do MBPP sem mudar a tarefa semantica. Assim, se o modelo estava acertando por memorizar nomes de funcoes, nomes de variaveis ou docstrings muito parecidos com o benchmark original, o desempenho tende a cair.

## Arquivos gerados

Depois de rodar o script desta pasta, os arquivos ficam em:

```text
RQ2\data\mbpp_rq2_transformed.jsonl
RQ2\data\mbpp_rq2_tests_final.jsonl
RQ2\data\mbpp_rq2_transform_report.jsonl
RQ2\data\mbpp_rq2_summary.json
```

Uso de cada arquivo:

| Arquivo | Uso |
| --- | --- |
| `mbpp_rq2_transformed.jsonl` | Dataset MBPP transformado para gerar codigo e avaliar. |
| `mbpp_rq2_tests_final.jsonl` | Mesmo conteudo, com nome separado para usar como arquivo de testes no `needcq`. |
| `mbpp_rq2_transform_report.jsonl` | Relatorio por tarefa mostrando o que foi alterado. |
| `mbpp_rq2_summary.json` | Resumo global das transformacoes. |

## Transformacoes aplicadas

As transformacoes sao deterministicas e locais. Nenhuma etapa usa API.

1. Renomeacao da funcao:

```text
similar_elements -> rq2_task_2
is_not_prime -> rq2_task_3
```

2. Renomeacao dos argumentos:

```text
test_tup1, test_tup2 -> rq2_arg_1, rq2_arg_2
```

3. Reordenacao dos argumentos no prompt quando a funcao tem pelo menos dois parametros:

```text
def similar_elements(test_tup1, test_tup2):
```

vira:

```text
def rq2_task_2(rq2_arg_2, rq2_arg_1):
```

As chamadas nos testes tambem sao reordenadas para preservar a semantica:

```text
similar_elements(a, b)
```

vira:

```text
rq2_task_2(b, a)
```

4. Parafraseamento do docstring por regras lexicais:

```text
Write a function to find...
```

vira algo como:

```text
Implement a function that compute...
```

Esse parafraseamento nao e perfeito linguisticamente, mas serve ao objetivo da RQ2: reduzir correspondencia textual superficial com o MBPP original sem depender de outro LLM.

## Como gerar os insumos da RQ2

Na raiz do projeto:

```powershell
python RQ2\transform_mbpp_rq2.py
```

Para gerar apenas um recorte, por exemplo 85 tarefas:

```powershell
python RQ2\transform_mbpp_rq2.py --limit 85
```

## Como rodar o experimento RQ2

Exemplo com 85 tarefas e 25 codigos por tarefa:

```powershell
python src\generate_mbpp_samples.py `
  --source-path RQ2\data\mbpp_rq2_transformed.jsonl `
  --output-path RQ2\data\mbpp_rq2_sample_25.jsonl `
  --samples-per-task 25 `
  --limit 85 `
  --sleep-between-tasks 2 `
  --force
```

Depois rode o `needcq` usando os arquivos da RQ2:

```powershell
python src\clarify\run_clarify_gpt4_mbpp.py `
  --stage needcq `
  --sample-code-file RQ2\data\mbpp_rq2_sample_25.jsonl `
  --test-case-file RQ2\data\mbpp_rq2_tests_final.jsonl `
  --needcq-path RQ2\data\mbpp_rq2_needcq.jsonl `
  --samples-per-task 25 `
  --limit 85 `
  --test-timeout 1.0 `
  --force
```

As etapas com API:

```powershell
python src\clarify\run_clarify_gpt4_mbpp.py --stage askcq --needcq-path RQ2\data\mbpp_rq2_needcq.jsonl --askcq-path RQ2\data\mbpp_rq2_askcq.jsonl --force

python src\clarify\run_clarify_gpt4_mbpp.py --stage answercq --needcq-path RQ2\data\mbpp_rq2_needcq.jsonl --askcq-path RQ2\data\mbpp_rq2_askcq.jsonl --answercq-path RQ2\data\mbpp_rq2_answercq.jsonl --force

python src\clarify\run_clarify_gpt4_mbpp.py --stage synthesize --needcq-path RQ2\data\mbpp_rq2_needcq.jsonl --askcq-path RQ2\data\mbpp_rq2_askcq.jsonl --answercq-path RQ2\data\mbpp_rq2_answercq.jsonl --synthesize-path RQ2\data\mbpp_rq2_synthesize.jsonl --force
```

## Avaliacao

Antes de rodar a etapa `final`, crie um baseline greedy da propria RQ2. Esse passo e necessario porque a etapa `final` precisa de uma solucao alternativa para as tarefas que nao receberam solucao sintetizada pelo ClarifyGPT.

Exemplo com 85 tarefas e 25 amostras por tarefa:

```powershell
python RQ2\create_rq2_final_inputs.py `
  --task-count 85 `
  --samples-per-task 25 `
  --sample-code-file RQ2\data\mbpp_rq2_sample_25.jsonl
```

Se o `python` nao estiver no PATH, use a versao PowerShell:

```powershell
powershell -ExecutionPolicy Bypass -File RQ2\create_rq2_final_inputs.ps1 `
  -TaskCount 85 `
  -SamplesPerTask 25 `
  -SampleCodeFile RQ2\data\mbpp_rq2_sample_25.jsonl
```

Esse comando gera:

```text
RQ2\data\mbpp_rq2_first_85_source.jsonl
RQ2\data\mbpp_rq2_first_85_greedy.jsonl
```

Depois gere o arquivo final da RQ2:

```powershell
python src\clarify\run_clarify_gpt4_mbpp.py `
  --stage final `
  --mbpp-file RQ2\data\mbpp_rq2_first_85_source.jsonl `
  --greedy-generate-file RQ2\data\mbpp_rq2_first_85_greedy.jsonl `
  --synthesize-path RQ2\data\mbpp_rq2_synthesize.jsonl `
  --final-path RQ2\data\mbpp_rq2_final_85.jsonl `
  --force
```

Para avaliar diretamente as amostras geradas antes do ClarifyGPT, crie um arquivo de predicoes no formato esperado pelo avaliador ou adapte a saida para:

```json
{"prompt": "...", "samples": ["..."]}
```

Para avaliar o arquivo final do ClarifyGPT na RQ2, use:

```powershell
python evaluation\MBPP\main.py `
  --source_path_for_solution RQ2\data\mbpp_rq2_first_85_source.jsonl `
  --predict_path_for_solution RQ2\data\mbpp_rq2_final_85.jsonl
```

Observacao: a etapa `final` original mistura solucoes sintetizadas com um baseline greedy. Para a RQ2, evite comparar um arquivo final que use baseline do MBPP original, porque isso reintroduz sinais do experimento antigo. O ideal e usar um baseline tambem gerado sobre `mbpp_rq2_transformed.jsonl`.

## Comparacao esperada

Compare pelo menos dois cenarios:

| Cenario | Dataset | Objetivo |
| --- | --- | --- |
| Original | `src\data\mbpp_sanitized_microsoft.jsonl` | Resultado base. |
| RQ2 transformado | `RQ2\data\mbpp_rq2_transformed.jsonl` | Stress test contra data leakage superficial. |

Se o `pass@1` cair muito na RQ2, isso sugere que parte do desempenho anterior pode depender de correspondencia superficial com o benchmark original. Se o resultado se mantiver, o modelo parece mais robusto a variacoes semanticas do prompt.
