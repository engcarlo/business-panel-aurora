---
nome: projecao_media_movel
categoria: previsao
descricao: "Projeta a receita dos próximos meses pela média móvel dos últimos N meses (estimativa simples)."
parametros: "janela: nº de meses na média (padrão 3); meses_a_frente: quantos meses projetar (padrão 1)"
versao: 4
atualizada: 2026-11-19
autor: padrao
---

# `projecao_media_movel`

Projeta a receita dos próximos meses pela média móvel dos últimos N meses (estimativa simples).

## Quando usar

Para uma estimativa rápida do caixa futuro. É uma referência, não uma previsão garantida.

## Fórmula

projeção = média da receita dos últimos `janela` meses (repetida para cada mês à frente).

## Parâmetros

janela: nº de meses na média (padrão 3); meses_a_frente: quantos meses projetar (padrão 1)

## Código

```python
def calcular(dados, janela=3, meses_a_frente=1):
    meses = sorted(agrupar(dados, lambda d: (d["ano"], d["mes"])).items())
    valores = [soma(g) for _, g in meses]
    if len(valores) < janela:
        return f"São necessários pelo menos {janela} meses de dados (há {len(valores)})."
    proj = media(valores[-janela:])
    a, m = meses[-1][0]
    linhas = []
    for i in range(meses_a_frente):
        m += 1
        if m > 12:
            a, m = a + 1, 1
        linhas.append({"mês": f"{MESES[m - 1]}/{a}", "projeção": brl(proj)})
    return {"resumo": f"Média dos últimos {janela} meses: {brl(proj)} (estimativa simples; não considera sazonalidade).",
            "tabela": linhas}
```
