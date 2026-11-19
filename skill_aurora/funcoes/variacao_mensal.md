---
nome: variacao_mensal
categoria: tendencia
descricao: "Receita mês a mês com variação absoluta e percentual sobre o mês anterior."
parametros: "nenhum"
versao: 4
atualizada: 2026-11-19
autor: padrao
---

# `variacao_mensal`

Receita mês a mês com variação absoluta e percentual sobre o mês anterior.

## Quando usar

Para entender a evolução do caixa e localizar picos e quedas.

## Fórmula

variação % = (receita do mês − receita do mês anterior) ÷ receita do mês anterior.

## Parâmetros

nenhum

## Código

```python
def calcular(dados):
    meses = sorted(agrupar(dados, lambda d: (d["ano"], d["mes"])).items())
    linhas, anterior = [], None
    for (a, m), g in meses:
        v = soma(g)
        linhas.append({"mês": f"{MESES[m - 1]}/{a}", "receita": brl(v), "recebimentos": len(g),
                       "variação": "—" if anterior is None else brl(v - anterior),
                       "variação %": "—" if not anterior else pct((v - anterior) / anterior)})
        anterior = v
    return {"resumo": f"{len(meses)} meses analisados.", "tabela": linhas}
```
