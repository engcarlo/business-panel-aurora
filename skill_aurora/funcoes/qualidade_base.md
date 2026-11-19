---
nome: qualidade_base
categoria: qualidade
descricao: "Mostra quanto da receita está sem região/categoria (pagadores fora do cadastro) e quem são."
parametros: "nenhum"
versao: 4
atualizada: 2026-11-19
autor: padrao
---

# `qualidade_base`

Mostra quanto da receita está sem região/categoria (pagadores fora do cadastro) e quem são.

## Quando usar

Para medir a confiabilidade das análises por região/categoria e cobrar o cadastro dos pagadores.

## Fórmula

% sem cadastro = receita com situação fora_do_cadastro ÷ receita total.

## Parâmetros

nenhum

## Código

```python
def calcular(dados):
    fora = [d for d in dados if d["situacao"] == "fora_do_cadastro"]
    total = soma(dados)
    linhas = [{"pagador": c, "recebimentos": len(g), "valor": brl(soma(g))} for c, g in agrupar(fora, "cliente").items()]
    return {"resumo": f"{len(fora)} recebimento(s) de pagadores fora do cadastro = {brl(soma(fora))} "
                      f"({pct(soma(fora) / total) if total else '0%'} da receita).", "tabela": linhas}
```
