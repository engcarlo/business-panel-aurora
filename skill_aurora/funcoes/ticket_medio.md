---
nome: ticket_medio
categoria: receita
descricao: "Ticket médio (valor médio por recebimento), geral ou por cliente, forma, região, categoria ou mês."
parametros: "agrupar_por: nenhum | cliente | forma | regiao | categoria | mes (padrão: nenhum)"
versao: 4
atualizada: 2026-11-19
autor: padrao
---

# `ticket_medio`

Ticket médio (valor médio por recebimento), geral ou por cliente, forma, região, categoria ou mês.

## Quando usar

Para saber o tamanho típico de cada pagamento e comparar perfis de cliente ou de forma de pagamento.

## Fórmula

ticket médio = soma dos valores ÷ número de recebimentos (por grupo).

## Parâmetros

agrupar_por: nenhum | cliente | forma | regiao | categoria | mes (padrão: nenhum)

## Código

```python
def calcular(dados, agrupar_por="nenhum"):
    chave = (lambda d: "Total") if agrupar_por == "nenhum" else (
        (lambda d: f"{d['ano']}-{d['mes']:02d}") if agrupar_por == "mes" else (lambda d: d[agrupar_por]))
    linhas = []
    for nome, grupo in agrupar(dados, chave).items():
        linhas.append({"grupo": nome, "recebimentos": len(grupo), "total": soma(grupo), "ticket": soma(grupo) / len(grupo)})
    linhas = sorted(linhas, key=lambda r: -r["ticket"])
    geral = soma(dados) / len(dados)
    return {"resumo": f"Ticket médio geral: {brl(geral)} em {len(dados)} recebimentos.",
            "tabela": [{"grupo": r["grupo"], "recebimentos": r["recebimentos"], "total": brl(r["total"]),
                        "ticket médio": brl(r["ticket"])} for r in linhas]}
```
