---
nome: participacao_forma_por_categoria
categoria: pagamentos
descricao: "Percentual da receita de cada categoria que entrou por uma forma de pagamento (ex.: % de Pix por categoria)."
parametros: "forma: Pix | TED | Transferência | Boleto | Depósito (padrão Pix)"
versao: 1
atualizada: 2026-11-19
autor: chat
---

# `participacao_forma_por_categoria`

Percentual da receita de cada categoria que entrou por uma forma de pagamento (ex.: % de Pix por categoria).

## Quando usar

Para ver quais categorias adotam mais cada forma de pagamento.

## Fórmula

% = receita da categoria na forma ÷ receita total da categoria.

## Parâmetros

forma: Pix | TED | Transferência | Boleto | Depósito (padrão Pix)

## Código

```python
def calcular(dados, forma="Pix"):
    total = soma(dados)
    linhas = []
    for cat, g in agrupar(dados, "categoria").items():
        na_forma = soma([d for d in g if d["forma"] == forma])
        linhas.append({"categoria": cat, f"% em {forma}": pct(na_forma / soma(g)), "receita na forma": brl(na_forma)})
    return {"resumo": f"{forma} = {pct(soma([d for d in dados if d['forma'] == forma]) / total)} da receita.",
            "tabela": sorted(linhas, key=lambda r: r["categoria"])}
```
