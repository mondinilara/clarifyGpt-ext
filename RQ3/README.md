# RQ3 - Otimizacao de Prompt

Esta pasta contem os insumos da RQ3:

> Perguntas e instrucoes mais concisas reduzem custo de API sem perder precisao?

A comparacao proposta e manter o mesmo dataset, o mesmo modelo, o mesmo numero de amostras e o mesmo pipeline, mudando apenas os prompts de raciocinio usados nas etapas:

```text
askcq
answercq
synthesize
```

O objetivo e comparar:

| Condicao | Prompt |
| --- | --- |
| Original | `src\prompt\prompt_mbpp.py` |
| Otimizado | `RQ3\prompt_mbpp_optimized.py` |

## Arquivos desta pasta

```text
RQ3\prompt_mbpp_optimized.py
RQ3\measure_prompt_tokens.py
RQ3\measure_prompt_tokens.ps1
RQ3\token_reduction_report.json
```

Uso de cada arquivo:

| Arquivo | Uso |
| --- | --- |
| `prompt_mbpp_optimized.py` | Prompts compactados para `three_shot`. |
| `measure_prompt_tokens.py` | Mede tokens usando `tiktoken` quando disponivel. |
| `measure_prompt_tokens.ps1` | Mede reducao por estimativa regex no PowerShell. |
| `token_reduction_report.json` | Relatorio gerado com a reducao de tokens. |

## O que foi otimizado

Foi mantida a estrutura geral do artigo:

1. `askcq`: analisar divergencia entre solucoes candidatas e gerar perguntas de esclarecimento.
2. `answercq`: responder perguntas usando o requisito original e inferencias razoaveis.
3. `synthesize`: gerar uma solucao Python final usando requisito + esclarecimentos.

O que foi reduzido:

- Instrucoes longas viraram regras curtas.
- Analises repetitivas foram resumidas para o contraste essencial.
- Exemplos few-shot foram mantidos, mas com respostas mais diretas.
- Frases explicativas redundantes foram removidas.
- A estrutura de saida foi preservada: `### Analysis`, `### Clarifying Questions`, `### Answers` e codigo final.

O que nao foi alterado:

- O numero de exemplos few-shot continua sendo 3.
- As tres etapas do ClarifyGPT continuam iguais.
- O modelo, temperatura, dataset e avaliacao devem ser os mesmos do experimento original.
- O prompt dinamico de cada tarefa continua sendo inserido pelo pipeline.

## Reducao de tokens

Relatorio gerado com `measure_prompt_tokens.ps1`, usando estimativa regex sobre os prompts estaticos `three_shot`:

| Etapa | Original | Otimizado | Reducao | Reducao % |
| --- | ---: | ---: | ---: | ---: |
| `askcq` | 1269 | 782 | 487 | 38.38% |
| `answercq` | 1012 | 689 | 323 | 31.92% |
| `synthesize` | 1016 | 482 | 534 | 52.56% |
| **Total** | **3297** | **1953** | **1344** | **40.76%** |

Observacao: esses numeros cobrem apenas os prompts estaticos few-shot. O texto dinamico de cada tarefa, codigos candidatos, perguntas e respostas varia por exemplo e nao entra nessa tabela.

Para medir com o tokenizer da OpenAI, rode:

```powershell
python RQ3\measure_prompt_tokens.py
```

Se `tiktoken` estiver instalado, o arquivo `RQ3\token_reduction_report.json` sera recalculado com `cl100k_base`.

## Como rodar a RQ3

Primeiro rode o pipeline original ou aproveite um experimento ja executado.

Depois rode o pipeline otimizado apontando para `RQ3\prompt_mbpp_optimized.py`.

### Por que a RQ3 nao comeca do zero?

A RQ3 reaproveita os insumos do experimento base:

```text
dataset MBPP
samples iniciais de codigo
arquivo needcq
```

Ou seja, normalmente voce **nao precisa** rodar novamente:

```powershell
python src\prepare_mbpp_data.py
python src\generate_mbpp_samples.py --samples-per-task 3 --force
python src\clarify\run_clarify_gpt4_mbpp.py --stage needcq --force --samples-per-task 3
```

Esses comandos pertencem a preparacao do experimento base:

| Comando | O que gera |
| --- | --- |
| `python src\prepare_mbpp_data.py` | Dataset MBPP convertido. |
| `python src\generate_mbpp_samples.py ...` | Codigos candidatos iniciais do modelo. |
| `python src\clarify\run_clarify_gpt4_mbpp.py --stage needcq ...` | Lista de tarefas que precisam de clarifying questions. |

Na RQ3, a pergunta de pesquisa e:

> Se eu trocar o prompt original por um prompt mais curto, o custo cai sem perder precisao?

Para isolar essa variavel, a comparacao deve manter iguais:

```text
mesmo dataset
mesmos samples iniciais
mesmas tarefas em needcq
mesmo modelo
mesma avaliacao
```

E mudar apenas:

```text
prompts das etapas askcq, answercq e synthesize
```

Se voce rodar `generate_mbpp_samples.py` novamente, os codigos candidatos podem mudar. Nesse caso, uma diferenca no `pass@1` poderia vir dos novos samples, e nao necessariamente do prompt otimizado.

So faz sentido rodar a RQ3 do zero se voce tambem rodar o experimento original do zero com exatamente a mesma configuracao, para comparar duas execucoes equivalentes.

### Experimento com 85 tarefas

Use estes comandos para rodar a RQ3 no recorte de 85 tarefas. As etapas `askcq`, `answercq` e `synthesize` chamam API. As etapas `final` e avaliacao nao chamam API.

```powershell
python src\clarify\run_clarify_gpt4_mbpp.py `
  --stage askcq `
  --needcq-path src\data\mbpp_needcq_gpt4.jsonl `
  --askcq-path RQ3\mbpp_askcq_optimized_85.jsonl `
  --prompt-module RQ3\prompt_mbpp_optimized.py `
  --force
```

```powershell
python src\clarify\run_clarify_gpt4_mbpp.py `
  --stage answercq `
  --needcq-path src\data\mbpp_needcq_gpt4.jsonl `
  --askcq-path RQ3\mbpp_askcq_optimized_85.jsonl `
  --answercq-path RQ3\mbpp_answercq_optimized_85.jsonl `
  --prompt-module RQ3\prompt_mbpp_optimized.py `
  --force
```

```powershell
python src\clarify\run_clarify_gpt4_mbpp.py `
  --stage synthesize `
  --needcq-path src\data\mbpp_needcq_gpt4.jsonl `
  --askcq-path RQ3\mbpp_askcq_optimized_85.jsonl `
  --answercq-path RQ3\mbpp_answercq_optimized_85.jsonl `
  --synthesize-path RQ3\mbpp_synthesize_optimized_85.jsonl `
  --prompt-module RQ3\prompt_mbpp_optimized.py `
  --force
```

Antes de gerar o final, crie o recorte de avaliacao de 85 tarefas, caso ele ainda nao exista:

```powershell
python src\create_mbpp_eval_subset.py --task-count 85 --samples-per-task 25
```

Isso gera:

```text
src\data\generated\eval_subset\mbpp_eval_first_85_source.jsonl
src\data\generated\eval_subset\mbpp_eval_first_85_final.jsonl
```

Depois gere o final otimizado apontando para o `synthesize` da RQ3:

```powershell
python src\clarify\run_clarify_gpt4_mbpp.py `
  --stage final `
  --mbpp-file src\data\generated\eval_subset\mbpp_eval_first_85_source.jsonl `
  --greedy-generate-file src\data\generated\eval_subset\mbpp_eval_first_85_final.jsonl `
  --synthesize-path RQ3\mbpp_synthesize_optimized_85.jsonl `
  --final-path RQ3\mbpp_final_optimized_85.jsonl `
  --force
```

Avalie o resultado otimizado:

```powershell
python evaluation\MBPP\main.py `
  --source_path_for_solution src\data\generated\eval_subset\mbpp_eval_first_85_source.jsonl `
  --predict_path_for_solution RQ3\mbpp_final_optimized_85.jsonl
```

## Como comparar

Compare o resultado original com o otimizado:

| Metrica | Original | Otimizado |
| --- | --- | --- |
| `pass@1` | resultado do pipeline original | resultado com `prompt_mbpp_optimized.py` |
| tokens estaticos | 3297 | 1953 |
| reducao estimada | - | 40.76% |

Interpretacao:

- Se o `pass@1` ficar parecido e os tokens cairem, o prompt otimizado reduz custo sem perda relevante.
- Se o `pass@1` cair muito, o prompt original provavelmente continha contexto util.
- Se o `pass@1` subir, o prompt otimizado pode estar removendo ruido ou induzindo respostas mais objetivas.

## Como estimar tokens e custo da RQ3

As proximas execucoes do pipeline salvam o campo `usage` retornado pela API nos arquivos de saida. Para experimentos antigos, use uma estimativa offline reconstruindo os prompts e contando os outputs salvos.

Para estimar a RQ3 de 85 tarefas com `gpt-4o-mini`:

```powershell
python src\estimate_experiment_tokens.py `
  --experiment-name RQ3_optimized_85 `
  --needcq-path src\data\mbpp_needcq_gpt4_first_85.jsonl `
  --askcq-path RQ3\mbpp_askcq_optimized_85.jsonl `
  --answercq-path RQ3\mbpp_answercq_optimized_85.jsonl `
  --synthesize-path RQ3\mbpp_synthesize_optimized_85.jsonl `
  --prompt-module RQ3\prompt_mbpp_optimized.py `
  --output-json RQ3\token_usage_estimate_85.json `
  --output-csv RQ3\token_usage_estimate_85.csv
```

Se o seu arquivo `needcq` de 85 tarefas tiver outro nome, troque o valor de `--needcq-path`.

Se os arquivos `RQ3\mbpp_askcq_optimized_85.jsonl`, `RQ3\mbpp_answercq_optimized_85.jsonl` e `RQ3\mbpp_synthesize_optimized_85.jsonl` tiverem mais linhas que o recorte de 85 tarefas, use o `needcq` que originou essas linhas. Por exemplo, se eles tiverem 214 linhas:

```powershell
python src\estimate_experiment_tokens.py `
  --experiment-name RQ3_optimized_214_needcq `
  --needcq-path src\data\mbpp_needcq_gpt4.jsonl `
  --askcq-path RQ3\mbpp_askcq_optimized_85.jsonl `
  --answercq-path RQ3\mbpp_answercq_optimized_85.jsonl `
  --synthesize-path RQ3\mbpp_synthesize_optimized_85.jsonl `
  --prompt-module RQ3\prompt_mbpp_optimized.py `
  --output-json RQ3\token_usage_estimate_matched.json `
  --output-csv RQ3\token_usage_estimate_matched.csv
```

O estimador alinha os arquivos por `task_id`; se houver diferenca de contagem, ele usa apenas as tarefas presentes nos quatro arquivos.

O script usa por padrao os precos historicos do `gpt-4o-mini`:

```text
input:  US$ 0.15 / 1M tokens
output: US$ 0.60 / 1M tokens
```

Antes de escrever o resultado final, confirme os precos atuais no dashboard/pricing da OpenAI.
