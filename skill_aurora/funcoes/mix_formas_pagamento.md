---
nome: mix_formas_pagamento
categoria: pagamentos
descricao: "Participação de cada forma de pagamento (Pix, boleto, TED...) em valor e quantidade, com ticket médio."
parametros: "por_cliente: true para detalhar a forma predominante de cada cliente (padrão false)"
versao: 4
atualizada: 2026-11-19
autor: padrao
---

# `mix_formas_pagamento`

Participação de cada forma de pagamento (Pix, boleto, TED...) em valor e quantidade, com ticket médio.

## Quando usar

Para negociar custos bancários e entender o comportamento de pagamento dos clientes.

## Fórmula

participação = receita da forma ÷ receita total; ticket = receita da forma ÷ nº de recebimentos da forma.

## Parâmetros

por_cliente: true para detalhar a forma predominante de cada cliente (padrão false)

## Código

```python
def calcular(dados, por_cliente=False):
    total = soma(dados)
    if por_cliente:
        linhas = []
        for cli, g in agrupar(dados, "cliente").items():
            formas = sorted(((f, soma(x)) for f, x in agrupar(g, "forma").items()), key=lambda t: -t[1])
            linhas.append({"cliente": cli, "forma predominante": formas[0][0], "% na forma": pct(formas[0][1] / soma(g)),
                           "formas usadas": ", ".join(f for f, _ in formas)})
        return {"resumo": "Forma predominante por cliente.", "tabela": linhas}
    linhas = [{"forma": f, "receita": brl(soma(g)), "participação": pct(soma(g) / total), "recebimentos": len(g),
               "ticket médio": brl(soma(g) / len(g))} for f, g in sorted(agrupar(dados, "forma").items(), key=lambda t: -soma(t[1]))]
    return {"resumo": f"Total {brl(total)} em {len(dados)} recebimentos.", "tabela": linhas}
```
