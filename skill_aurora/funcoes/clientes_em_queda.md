---
nome: clientes_em_queda
categoria: clientes
descricao: "Lista clientes cuja receita caiu mais que um limite entre dois períodos (alerta de churn)."
parametros: "limite: queda mínima em fração (padrão 0.20 = 20%); a_inicio, a_fim, b_inicio, b_fim (padrão 1-3 x 4-6)"
versao: 4
atualizada: 2026-11-19
autor: padrao
---

# `clientes_em_queda`

Lista clientes cuja receita caiu mais que um limite entre dois períodos (alerta de churn).

## Quando usar

Para a equipe comercial agir antes de perder o cliente.

## Fórmula

queda % = (receita B − receita A) ÷ receita A; entra na lista se queda % ≤ −limite (inclui quem zerou).

## Parâmetros

limite: queda mínima em fração (padrão 0.20 = 20%); a_inicio, a_fim, b_inicio, b_fim (padrão 1-3 x 4-6)

## Código

```python
def calcular(dados, limite=0.20, a_inicio=1, a_fim=3, b_inicio=4, b_fim=6):
    a = agrupar([d for d in dados if a_inicio <= d["mes"] <= a_fim], "cliente")
    b = agrupar([d for d in dados if b_inicio <= d["mes"] <= b_fim], "cliente")
    alertas = []
    for cli, g in a.items():
        va, vb = soma(g), soma(b.get(cli, []))
        if va and (vb - va) / va <= -limite:
            alertas.append({"cliente": cli, "período A": brl(va), "período B": brl(vb), "queda": pct((vb - va) / va), "_q": (vb - va) / va})
    alertas = sorted(alertas, key=lambda r: r["_q"])
    for r in alertas:
        r.pop("_q")
    return {"resumo": f"{len(alertas)} cliente(s) com queda de {pct(limite, 0)} ou mais." if alertas
            else f"Nenhum cliente caiu {pct(limite, 0)} ou mais.", "tabela": alertas}
```
