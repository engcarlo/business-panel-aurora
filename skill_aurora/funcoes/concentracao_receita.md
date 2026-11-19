---
nome: concentracao_receita
categoria: concentracao
descricao: "Mede dependência de poucos clientes: participação do top N e índice HHI (Herfindahl)."
parametros: "top: quantos maiores clientes somar (padrão 3)"
versao: 4
atualizada: 2026-11-19
autor: padrao
---

# `concentracao_receita`

Mede dependência de poucos clientes: participação do top N e índice HHI (Herfindahl).

## Quando usar

Para avaliar risco de concentração: HHI acima de 0,25 indica receita muito concentrada.

## Fórmula

participação_i = receita_i ÷ total; HHI = Σ participação_i²; top N = Σ das N maiores participações.

## Parâmetros

top: quantos maiores clientes somar (padrão 3)

## Código

```python
def calcular(dados, top=3):
    total = soma(dados)
    parts = sorted((soma(g) / total for g in agrupar(dados, "cliente").values()), reverse=True)
    hhi = sum(p * p for p in parts)
    nivel = "alta" if hhi > 0.25 else ("moderada" if hhi > 0.15 else "baixa")
    return {"resumo": f"Top {top} clientes = {pct(sum(parts[:top]))} da receita. HHI = {num(hhi, 3)} (concentração {nivel}). "
                      f"Equivale a {num(1 / hhi, 1)} clientes de mesmo tamanho.",
            "tabela": [{"posição": i + 1, "participação": pct(p), "acumulado": pct(sum(parts[:i + 1]))} for i, p in enumerate(parts)]}
```
