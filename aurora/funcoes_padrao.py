"""Funções de negócio iniciais da skill. `python -m aurora funcoes --semear` (re)cria as páginas
pelo mesmo caminho que o chat usa (validação + teste com os dados reais)."""
from . import funcoes
from .config import Caminhos

PADRAO = [
    dict(nome="ticket_medio", categoria="receita",
         descricao="Ticket médio (valor médio por recebimento), geral ou por cliente, forma, região, categoria ou mês.",
         parametros="agrupar_por: nenhum | cliente | forma | regiao | categoria | mes (padrão: nenhum)",
         explicacao="Para saber o tamanho típico de cada pagamento e comparar perfis de cliente ou de forma de pagamento.",
         formula="ticket médio = soma dos valores ÷ número de recebimentos (por grupo).",
         exemplo={"agrupar_por": "forma"},
         codigo='''
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
'''),
    dict(nome="curva_abc_clientes", categoria="clientes",
         descricao="Curva ABC de clientes: classe A (até 80% da receita), B (até 95%) e C (restante).",
         parametros="corte_a: % acumulado da classe A (padrão 0.80); corte_b: % acumulado da classe B (padrão 0.95)",
         explicacao="Para priorizar atendimento e cobrança: poucos clientes A sustentam a maior parte do caixa.",
         formula="ordena clientes por receita; % acumulado = soma acumulada ÷ total; A se acumulado ≤ corte_a, B se ≤ corte_b, senão C.",
         exemplo={},
         codigo='''
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
'''),
    dict(nome="concentracao_receita", categoria="concentracao",
         descricao="Mede dependência de poucos clientes: participação do top N e índice HHI (Herfindahl).",
         parametros="top: quantos maiores clientes somar (padrão 3)",
         explicacao="Para avaliar risco de concentração: HHI acima de 0,25 indica receita muito concentrada.",
         formula="participação_i = receita_i ÷ total; HHI = Σ participação_i²; top N = Σ das N maiores participações.",
         exemplo={"top": 3},
         codigo='''
def calcular(dados, top=3):
    total = soma(dados)
    parts = sorted((soma(g) / total for g in agrupar(dados, "cliente").values()), reverse=True)
    hhi = sum(p * p for p in parts)
    nivel = "alta" if hhi > 0.25 else ("moderada" if hhi > 0.15 else "baixa")
    return {"resumo": f"Top {top} clientes = {pct(sum(parts[:top]))} da receita. HHI = {num(hhi, 3)} (concentração {nivel}). "
                      f"Equivale a {num(1 / hhi, 1)} clientes de mesmo tamanho.",
            "tabela": [{"posição": i + 1, "participação": pct(p), "acumulado": pct(sum(parts[:i + 1]))} for i, p in enumerate(parts)]}
'''),
    dict(nome="variacao_mensal", categoria="tendencia",
         descricao="Receita mês a mês com variação absoluta e percentual sobre o mês anterior.",
         parametros="nenhum",
         explicacao="Para entender a evolução do caixa e localizar picos e quedas.",
         formula="variação % = (receita do mês − receita do mês anterior) ÷ receita do mês anterior.",
         exemplo={},
         codigo='''
def calcular(dados):
    meses = sorted(agrupar(dados, lambda d: (d["ano"], d["mes"])).items())
    linhas, anterior = [], None
    for (a, m), g in meses:
        v = soma(g)
        linhas.append({"mês": f"{MESES[m - 1]}/{a}", "receita": brl(v), "recebimentos": len(g),
                       "variação": "—" if anterior is None else brl(v - anterior),
                       "variação %": "—" if not anterior else pct((v - anterior) / anterior)})
        anterior = v
    return {"resumo": f"{len(meses)} meses analisados.", "tabela": linhas}
'''),
    dict(nome="comparar_periodos", categoria="tendencia",
         descricao="Compara dois intervalos de meses (ex.: 1º x 2º trimestre) por cliente, região, categoria ou forma.",
         parametros="a_inicio, a_fim, b_inicio, b_fim: meses dos períodos A e B (padrão 1-3 x 4-6); agrupar_por: cliente | regiao | categoria | forma (padrão cliente)",
         explicacao="Para descobrir quem cresceu e quem caiu entre dois períodos.",
         formula="para cada grupo: variação = receita B − receita A; variação % = variação ÷ receita A.",
         exemplo={"agrupar_por": "cliente"},
         codigo='''
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
'''),
    dict(nome="clientes_em_queda", categoria="clientes",
         descricao="Lista clientes cuja receita caiu mais que um limite entre dois períodos (alerta de churn).",
         parametros="limite: queda mínima em fração (padrão 0.20 = 20%); a_inicio, a_fim, b_inicio, b_fim (padrão 1-3 x 4-6)",
         explicacao="Para a equipe comercial agir antes de perder o cliente.",
         formula="queda % = (receita B − receita A) ÷ receita A; entra na lista se queda % ≤ −limite (inclui quem zerou).",
         exemplo={"limite": 0.2},
         codigo='''
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
'''),
    dict(nome="recorrencia_clientes", categoria="clientes",
         descricao="Frequência de cada cliente: meses ativos, nº de pagamentos, intervalo médio entre pagamentos e último pagamento.",
         parametros="nenhum",
         explicacao="Para identificar clientes regulares, esporádicos e quem está sem pagar há muito tempo.",
         formula="intervalo médio = média dos dias entre pagamentos consecutivos; dias sem pagar = última data da base − último pagamento do cliente.",
         exemplo={},
         codigo='''
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
'''),
    dict(nome="mix_formas_pagamento", categoria="pagamentos",
         descricao="Participação de cada forma de pagamento (Pix, boleto, TED...) em valor e quantidade, com ticket médio.",
         parametros="por_cliente: true para detalhar a forma predominante de cada cliente (padrão false)",
         explicacao="Para negociar custos bancários e entender o comportamento de pagamento dos clientes.",
         formula="participação = receita da forma ÷ receita total; ticket = receita da forma ÷ nº de recebimentos da forma.",
         exemplo={},
         codigo='''
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
'''),
    dict(nome="sazonalidade_mensal", categoria="tendencia",
         descricao="Índice de sazonalidade: quanto cada mês fica acima ou abaixo da média mensal (100 = média).",
         parametros="nenhum",
         explicacao="Para planejar caixa e estoque nos meses fortes e fracos.",
         formula="índice do mês = receita do mês ÷ média mensal × 100.",
         exemplo={},
         codigo='''
def calcular(dados):
    meses = sorted(agrupar(dados, lambda d: (d["ano"], d["mes"])).items())
    valores = [soma(g) for _, g in meses]
    m = media(valores)
    return {"resumo": f"Média mensal {brl(m)}; desvio padrão {brl(desvio(valores))} "
                      f"(coeficiente de variação {pct(desvio(valores) / m)}).",
            "tabela": [{"mês": f"{MESES[mes - 1]}/{a}", "receita": brl(v), "índice": round(v / m * 100),
                        "leitura": "acima da média" if v > m else "abaixo da média"} for ((a, mes), _), v in zip(meses, valores)]}
'''),
    dict(nome="projecao_media_movel", categoria="previsao",
         descricao="Projeta a receita dos próximos meses pela média móvel dos últimos N meses (estimativa simples).",
         parametros="janela: nº de meses na média (padrão 3); meses_a_frente: quantos meses projetar (padrão 1)",
         explicacao="Para uma estimativa rápida do caixa futuro. É uma referência, não uma previsão garantida.",
         formula="projeção = média da receita dos últimos `janela` meses (repetida para cada mês à frente).",
         exemplo={"janela": 3},
         codigo='''
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
'''),
    dict(nome="qualidade_base", categoria="qualidade",
         descricao="Mostra quanto da receita está sem região/categoria (pagadores fora do cadastro) e quem são.",
         parametros="nenhum",
         explicacao="Para medir a confiabilidade das análises por região/categoria e cobrar o cadastro dos pagadores.",
         formula="% sem cadastro = receita com situação fora_do_cadastro ÷ receita total.",
         exemplo={},
         codigo='''
def calcular(dados):
    fora = [d for d in dados if d["situacao"] == "fora_do_cadastro"]
    total = soma(dados)
    linhas = [{"pagador": c, "recebimentos": len(g), "valor": brl(soma(g))} for c, g in agrupar(fora, "cliente").items()]
    return {"resumo": f"{len(fora)} recebimento(s) de pagadores fora do cadastro = {brl(soma(fora))} "
                      f"({pct(soma(fora) / total) if total else '0%'} da receita).", "tabela": linhas}
'''),
]


def semear(cam: Caminhos) -> list[str]:
    out = []
    for f in PADRAO:
        r = funcoes.criar(cam, f["nome"], f["categoria"], f["descricao"], f["parametros"], f["explicacao"],
                          f["formula"], f["codigo"], f.get("exemplo"), sobrescrever=True, autor="padrao")
        out.append(f"{f['nome']}: {r.splitlines()[0]}")
    funcoes.gerar_indice()
    return out
