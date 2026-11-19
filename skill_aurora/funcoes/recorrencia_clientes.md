---
nome: recorrencia_clientes
categoria: clientes
descricao: "Frequência de cada cliente: meses ativos, nº de pagamentos, intervalo médio entre pagamentos e último pagamento."
parametros: "nenhum"
versao: 3
atualizada: 2026-11-19
autor: padrao
---

# `recorrencia_clientes`

Frequência de cada cliente: meses ativos, nº de pagamentos, intervalo médio entre pagamentos e último pagamento.

## Quando usar

Para identificar clientes regulares, esporádicos e quem está sem pagar há muito tempo.

## Fórmula

intervalo médio = média dos dias entre pagamentos consecutivos; dias sem pagar = última data da base − último pagamento do cliente.

## Parâmetros

nenhum

## Código

```python
def calcular(dados):
    fim = max(d["data"] for d in dados)
    linhas = []
    for cli, g in agrupar(dados, "cliente").items():
        datas = sorted(d["data"] for d in g)
        gaps = [(datas[i + 1] - datas[i]).days for i in range(len(datas) - 1)]
        linhas.append({"cliente": cli, "pagamentos": len(g), "meses ativos": len({(d["ano"], d["mes"]) for d in g}),
                       "intervalo médio (dias)": round(media(gaps), 1) if gaps else "—",
                       "último pagamento": data_br(datas[-1]), "dias sem pagar": (fim - datas[-1]).days})
    return {"resumo": f"Base até {data_br(fim)}.",
            "tabela": sorted(linhas, key=lambda r: -r["dias sem pagar"])}
```
