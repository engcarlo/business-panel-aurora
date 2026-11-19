---
nome: sazonalidade_mensal
categoria: tendencia
descricao: "Índice de sazonalidade: quanto cada mês fica acima ou abaixo da média mensal (100 = média)."
parametros: "nenhum"
versao: 4
atualizada: 2026-11-19
autor: padrao
---

# `sazonalidade_mensal`

Índice de sazonalidade: quanto cada mês fica acima ou abaixo da média mensal (100 = média).

## Quando usar

Para planejar caixa e estoque nos meses fortes e fracos.

## Fórmula

índice do mês = receita do mês ÷ média mensal × 100.

## Parâmetros

nenhum

## Código

```python
def calcular(dados):
    meses = sorted(agrupar(dados, lambda d: (d["ano"], d["mes"])).items())
    valores = [soma(g) for _, g in meses]
    m = media(valores)
    return {"resumo": f"Média mensal {brl(m)}; desvio padrão {brl(desvio(valores))} "
                      f"(coeficiente de variação {pct(desvio(valores) / m)}).",
            "tabela": [{"mês": f"{MESES[mes - 1]}/{a}", "receita": brl(v), "índice": round(v / m * 100),
                        "leitura": "acima da média" if v > m else "abaixo da média"} for ((a, mes), _), v in zip(meses, valores)]}
```
