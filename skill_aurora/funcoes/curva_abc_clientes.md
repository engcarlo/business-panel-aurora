---
nome: curva_abc_clientes
categoria: clientes
descricao: "Curva ABC de clientes: classe A (até 80% da receita), B (até 95%) e C (restante)."
parametros: "corte_a: % acumulado da classe A (padrão 0.80); corte_b: % acumulado da classe B (padrão 0.95)"
versao: 4
atualizada: 2026-11-19
autor: padrao
---

# `curva_abc_clientes`

Curva ABC de clientes: classe A (até 80% da receita), B (até 95%) e C (restante).

## Quando usar

Para priorizar atendimento e cobrança: poucos clientes A sustentam a maior parte do caixa.

## Fórmula

ordena clientes por receita; % acumulado = soma acumulada ÷ total; A se acumulado ≤ corte_a, B se ≤ corte_b, senão C.

## Parâmetros

corte_a: % acumulado da classe A (padrão 0.80); corte_b: % acumulado da classe B (padrão 0.95)

## Código

```python
def calcular(dados, corte_a=0.80, corte_b=0.95):
    total = soma(dados)
    por_cli = sorted(((c, soma(g)) for c, g in agrupar(dados, "cliente").items()), key=lambda x: -x[1])
    acum, linhas, cont = 0.0, [], {"A": 0, "B": 0, "C": 0}
    for cli, v in por_cli:
        antes = acum / total
        acum += v
        classe = "A" if antes < corte_a else ("B" if antes < corte_b else "C")
        cont[classe] += 1
        linhas.append({"cliente": cli, "receita": brl(v), "participação": pct(v / total), "acumulado": pct(acum / total), "classe": classe})
    return {"resumo": f"A: {cont['A']} clientes · B: {cont['B']} · C: {cont['C']} (total {brl(total)}).", "tabela": linhas}
```
