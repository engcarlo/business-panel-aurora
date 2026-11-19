---
nome: comparar_periodos
categoria: tendencia
descricao: "Compara dois intervalos de meses (ex.: 1º x 2º trimestre) por cliente, região, categoria ou forma."
parametros: "a_inicio, a_fim, b_inicio, b_fim: meses dos períodos A e B (padrão 1-3 x 4-6); agrupar_por: cliente | regiao | categoria | forma (padrão cliente)"
versao: 4
atualizada: 2026-11-19
autor: padrao
---

# `comparar_periodos`

Compara dois intervalos de meses (ex.: 1º x 2º trimestre) por cliente, região, categoria ou forma.

## Quando usar

Para descobrir quem cresceu e quem caiu entre dois períodos.

## Fórmula

para cada grupo: variação = receita B − receita A; variação % = variação ÷ receita A.

## Parâmetros

a_inicio, a_fim, b_inicio, b_fim: meses dos períodos A e B (padrão 1-3 x 4-6); agrupar_por: cliente | regiao | categoria | forma (padrão cliente)

## Código

```python
def calcular(dados, a_inicio=1, a_fim=3, b_inicio=4, b_fim=6, agrupar_por="cliente"):
    a = agrupar([d for d in dados if a_inicio <= d["mes"] <= a_fim], agrupar_por)
    b = agrupar([d for d in dados if b_inicio <= d["mes"] <= b_fim], agrupar_por)
    linhas = []
    for nome in set(a) | set(b):
        va, vb = soma(a.get(nome, [])), soma(b.get(nome, []))
        linhas.append({"grupo": nome, "A": va, "B": vb, "var": vb - va, "pct": (vb - va) / va if va else None})
    linhas = sorted(linhas, key=lambda r: r["var"])
    ta, tb = sum(r["A"] for r in linhas), sum(r["B"] for r in linhas)
    return {"resumo": f"Período A (meses {a_inicio}-{a_fim}): {brl(ta)} · Período B ({b_inicio}-{b_fim}): {brl(tb)} · "
                      f"variação {brl(tb - ta)} ({pct((tb - ta) / ta) if ta else '—'}).",
            "tabela": [{"grupo": r["grupo"], "período A": brl(r["A"]), "período B": brl(r["B"]), "variação": brl(r["var"]),
                        "variação %": pct(r["pct"]) if r["pct"] is not None else "novo"} for r in linhas]}
```
