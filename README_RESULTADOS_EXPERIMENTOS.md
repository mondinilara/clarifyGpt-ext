# Resultados dos Experimentos

Este arquivo resume os resultados obtidos nos experimentos RQ1, RQ2 e RQ3.

## Tabela Comparativa

| Experimento | Modelo | Tarefas avaliadas | Exemplos por tarefa | NeedCQ / chamadas Clarify | Total requests | Total tokens | Custo | pass@1 | Observacao |
| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | --- |
| RQ1 Exp. 1 | gpt-4o-mini | 32 | 15 | nao informado | 537 | 62.717 | US$ 0.22 | 0.7812 | Recorte pequeno, usado para teste inicial. |
| RQ1 Exp. 2 | gpt-4o-mini | 214 | 25 | nao informado | 6.016 | 969.159 | US$ 4.00 | 0.8290 | Maior reproducao da RQ1, 1/2 da base. |
| RQ1 Exp. 3 | gpt-4o-mini | 85 | 25 | 20 tarefas / 60 chamadas | estimado: 60 | estimado: 70.313 | estimado: US$ 0.0146 | 0.7412 | Estimativa offline apenas das etapas `askcq`, `answercq`, `synthesize`; nao inclui geracao inicial dos 25 samples. |
| RQ2 | gpt-4o-mini | 85 | 25 | nao informado | 3.186 | 330.053 | US$ 2.72 | 0.7176 | Stress test com prompts transformados. Custo inclui tentativa interrompida por quota e nova execucao. |
| RQ3 | gpt-4o-mini | 85 no resultado final, mas estimativa tokenizada sobre 214 NeedCQ | 25 | 214 tarefas / 642 chamadas | estimado: 642 | estimado: 355.113 | estimado: US$ 0.0687 | 0.7294 | Prompt otimizado. Estimativa offline das etapas `askcq`, `answercq`, `synthesize`; nao inclui geracao inicial dos samples. |

## Comparacao Principal

| Comparacao | Diferenca de pass@1 | Interpretacao |
| --- | ---: | --- |
| RQ2 vs RQ1 Exp. 3 | 0.7176 - 0.7412 = **-0.0236** | O stress test de data leakage reduziu a precisao em 2.36 pontos absolutos. |
| RQ3 vs RQ1 Exp. 3 | 0.7294 - 0.7412 = **-0.0118** | O prompt otimizado teve queda pequena, de 1.18 ponto absoluto. |
| RQ3 vs RQ2 | 0.7294 - 0.7176 = **+0.0118** | O prompt otimizado ficou levemente acima do cenario transformado da RQ2. |
| RQ1 Exp. 2 vs RQ1 Exp. 3 | 0.8290 - 0.7412 = **+0.0878** | O experimento maior de RQ1 teve desempenho mais alto que o recorte de 85 tarefas. |

## Leitura Por RQ

| RQ | Resultado observado | Leitura |
| --- | --- | --- |
| RQ1 | A reproducao conseguiu rodar e atingiu `pass@1` entre 0.7412 e 0.8290, dependendo do recorte. | O pipeline foi reproduzido com sucesso, mas os resultados variam com tamanho/seleção das tarefas. |
| RQ2 | `pass@1 = 0.7176`, abaixo da RQ1 de 85 tarefas. | As transformacoes semanticas reduziram o desempenho, sugerindo sensibilidade a pistas superficiais do benchmark original. |
| RQ3 | `pass@1 = 0.7294`, proximo da RQ1 de 85 tarefas. | O prompt otimizado reduziu contexto estatico e manteve desempenho parecido, com queda menor que a RQ2. |

## Ressalvas Metodologicas

Os valores de custo e tokens nao foram obtidos todos da mesma forma:

- RQ1 Exp. 1, RQ1 Exp. 2 e RQ2 usam valores do dashboard/API, mais proximos do custo real.
- RQ1 Exp. 3 e RQ3 usam estimativa offline baseada nos arquivos JSONL salvos.
- A estimativa offline considera apenas as etapas `askcq`, `answercq` e `synthesize`.
- A estimativa offline nao inclui o custo da geracao inicial dos samples com `generate_mbpp_samples.py`.
- Em RQ3, a estimativa de tokens foi calculada sobre 214 linhas de NeedCQ, enquanto o `pass@1` reportado considera o arquivo final avaliado no recorte de 85 tarefas.
- Em RQ2, o custo inclui uma tentativa interrompida por erro de quota e uma nova execucao; por isso, o custo pode estar acima do custo limpo de uma unica execucao completa.

## Comparacao Recomendada Para Discussao

Para uma comparacao mais justa de precisao, use principalmente:

```text
RQ1 Exp. 3 vs RQ2 vs RQ3
```

Motivo:

- os tres reportam `pass@1` para 85 tarefas;
- RQ1 Exp. 3 serve como baseline original no mesmo tamanho de avaliacao;
- RQ2 testa robustez contra transformacoes semanticas;
- RQ3 testa custo-beneficio do prompt otimizado.

## Conclusao Sugerida

Os resultados indicam que a reproducao do ClarifyGPT foi viavel no MBPP usando `gpt-4o-mini`. A RQ2 apresentou uma queda de `pass@1` em relacao ao baseline de 85 tarefas, sugerindo que transformacoes semanticas que removem pistas superficiais podem afetar o desempenho. A RQ3 apresentou uma queda menor de `pass@1`, indicando que prompts mais concisos podem reduzir custo/contexto com perda limitada de precisao.
