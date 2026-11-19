"""Etapa 4 — aba Dashboard: 5 KPIs + 4 gráficos, paisagem em 1 página.
Já incorpora o 'refinamento' do guia: áreas separadas, barras deitadas da
esquerda p/ direita com nomes à esquerda, valor na barra, sem eixo de valores
nem grade, uma fonte só, uma cor por gráfico, moeda BR como número formatado."""
from collections import defaultdict

from openpyxl.chart import BarChart, Reference
from openpyxl.chart.label import DataLabelList
from openpyxl.chart.text import RichText, Text
from openpyxl.chart.title import Title
from openpyxl.drawing.line import LineProperties
from openpyxl.chart.shapes import GraphicalProperties
from openpyxl.drawing.text import (CharacterProperties, Font as DFont, Paragraph,
                                   ParagraphProperties, RegularTextRun)
from openpyxl.styles import Alignment, Font, PatternFill
from openpyxl.utils import get_column_letter as L
from openpyxl.worksheet.properties import PageSetupProperties

from . import planilha
from .config import ABA_DASH, ABA_REC, FMT_MOEDA, MESES, NAO_IDENT, Caminhos

FONTE = "Calibri"
CORES = {"mes": "0F766E", "regiao": "4F46E5", "categoria": "D97706", "cliente": "BE185D"}
FUNDO_CARD = PatternFill("solid", fgColor="F1F5F9")
ULT = 5000                       # faixa das fórmulas na aba Recebimentos (folga para crescer)
R = lambda col: f"{ABA_REC}!${col}$5:${col}${ULT}"
LIN_APOIO, COL_APOIO = 70, 27    # tabelas de apoio: linha 70+, coluna AA+ (fora da impressão)


def _cp(sz, bold=False, cor="374151"):
    return CharacterProperties(latin=DFont(typeface=FONTE), sz=sz, b=bold, solidFill=cor)


def _rich(sz, bold=False, cor="374151"):
    cp = _cp(sz, bold, cor)
    return RichText(p=[Paragraph(pPr=ParagraphProperties(defRPr=cp), endParaRPr=cp)])


def _titulo(txt):
    cp = _cp(1200, True, "111827")
    p = Paragraph(pPr=ParagraphProperties(defRPr=cp), r=[RegularTextRun(rPr=cp, t=txt)])
    return Title(tx=Text(rich=RichText(p=[p])), overlay=False)


def _grafico(ws, titulo, col, l0, n, cor, deitado, ancora, maximo):
    ch = BarChart()
    ch.type = "bar" if deitado else "col"
    ch.title = _titulo(titulo)
    ch.legend = None
    ch.add_data(Reference(ws, min_col=col + 1, min_row=l0, max_row=l0 + n - 1), titles_from_data=False)
    ch.set_categories(Reference(ws, min_col=col, min_row=l0, max_row=l0 + n - 1))
    s = ch.series[0]
    s.graphicalProperties = GraphicalProperties(solidFill=cor, ln=LineProperties(noFill=True))
    s.dLbls = DataLabelList(showVal=True, showSerName=False, showCatName=False,
                            showLegendKey=False, showPercent=False, dLblPos="outEnd",
                            txPr=_rich(800, True, "1F2937"))
    ch.gapWidth = 45
    ch.y_axis.delete = True                 # eixo de valores fora: o valor está na barra
    ch.y_axis.majorGridlines = None
    ch.y_axis.scaling.min = 0
    ch.y_axis.scaling.max = maximo * (1.28 if deitado else 1.12)   # folga p/ o rótulo da maior barra
    ch.x_axis.delete = False
    ch.x_axis.majorGridlines = None
    ch.x_axis.majorTickMark = "none"
    ch.x_axis.txPr = _rich(900)
    ch.x_axis.spPr = GraphicalProperties(ln=LineProperties(solidFill="CBD5E1"))
    if deitado:
        ch.x_axis.scaling.orientation = "maxMin"   # 1º da lista em cima; barras crescem p/ direita
    ch.graphical_properties = GraphicalProperties(ln=LineProperties(noFill=True))
    ch.width, ch.height = 21.5, 11.0
    ws.add_chart(ch, ancora)


def _tabela(ws, col, titulo, linhas, formula):
    l = LIN_APOIO + 1
    ws.cell(l, col, titulo).font = Font(name=FONTE, bold=True)
    ws.cell(l, col + 1, "Valor (R$)").font = Font(name=FONTE, bold=True)
    for i, nome in enumerate(linhas):
        c1 = ws.cell(l + 1 + i, col, nome)
        c2 = ws.cell(l + 1 + i, col + 1, formula(nome))
        c1.font = c2.font = Font(name=FONTE)
        c2.number_format = FMT_MOEDA
        c2.alignment = Alignment(horizontal="right")
    largura = max(len(str(x)) for x in [titulo, *linhas]) + 3
    ws.column_dimensions[L(col)].width = max(12, largura)
    ws.column_dimensions[L(col + 1)].width = 18
    return l + 1, len(linhas)


def _card(ws, c0, rotulo, principal, detalhe, fmt_p=None, fmt_d=None, texto_p=False):
    c1 = c0 + 3
    for lin in (4, 5, 6):
        ws.merge_cells(start_row=lin, start_column=c0, end_row=lin, end_column=c1)
        for c in range(c0, c1 + 1):
            ws.cell(lin, c).fill = FUNDO_CARD
    a = ws.cell(4, c0, rotulo)
    a.font = Font(name=FONTE, size=9, bold=True, color="64748B")
    a.alignment = Alignment(horizontal="left", vertical="bottom", indent=1)
    b = ws.cell(5, c0, principal)
    b.font = Font(name=FONTE, size=13 if texto_p else 18, bold=True, color="0F172A")
    b.alignment = Alignment(horizontal="left" if texto_p else "right", vertical="center",
                            indent=1, shrink_to_fit=True)
    if fmt_p:
        b.number_format = fmt_p
    d = ws.cell(6, c0, detalhe)
    d.font = Font(name=FONTE, size=10, color="475569")
    d.alignment = Alignment(horizontal="right" if fmt_d else "left", vertical="top", indent=1)
    if fmt_d:
        d.number_format = fmt_d


def gerar(cam: Caminhos):
    wb = planilha.abrir(cam.planilha)
    rows = planilha.linhas(wb)
    if not rows:
        raise SystemExit("Aba Recebimentos vazia: rode as etapas 1 e 3 antes.")
    if any(r.regiao_uf is None for r in rows) and not any(r.regiao_uf for r in rows):
        raise SystemExit("Região/Categoria vazias: rode a etapa 3 (cadastro) antes.")
    if ABA_DASH in wb.sheetnames:
        del wb[ABA_DASH]
    ws = wb.create_sheet(ABA_DASH, 0)
    wb.active = 0
    ws.sheet_view.showGridLines = False

    # ---- agregados em Python (só para ordenar; os números saem de fórmulas)
    ano = min(r.data for r in rows).year
    meses = sorted({r.data.month for r in rows})
    meses = list(range(meses[0], meses[-1] + 1))
    tot = lambda chave: _ordenar({k: v for k, v in _soma(rows, chave).items()})
    regioes = tot(lambda r: r.regiao or NAO_IDENT)
    categorias = tot(lambda r: r.categoria or NAO_IDENT)
    clientes = sorted(_soma(rows, lambda r: r.cliente).items(), key=lambda kv: -kv[1])

    # ---- tabelas de apoio (visíveis, fora da área de impressão)
    ws.cell(LIN_APOIO, COL_APOIO, "Tabelas de apoio — alimentam os gráficos acima, não apagar").font = \
        Font(name=FONTE, bold=True, color="64748B")
    c = COL_APOIO
    lm, nm = _tabela(ws, c, "Mês", [MESES[m - 1] for m in meses], lambda nome: (
        lambda m: f'=SUMIFS({R("C")},{R("A")},">="&DATE({ano},{m},1),{R("A")},"<"&DATE({ano + (m == 12)},{m % 12 + 1},1))')(
        MESES.index(nome) + 1))
    lr, nr = _tabela(ws, c + 3, "Região", regioes, lambda nome: (
        f'=SUMIFS({R("C")},{R("E")},"")' if nome == NAO_IDENT
        else f'=SUMIFS({R("C")},{R("E")},"{nome}/*")'))
    lc, nc = _tabela(ws, c + 6, "Categoria", categorias, lambda nome: (
        f'=SUMIFS({R("C")},{R("F")},"")' if nome == NAO_IDENT
        else f'=SUMIFS({R("C")},{R("F")},"{nome}")'))
    lk, nk = _tabela(ws, c + 9, "Cliente", [k for k, _ in clientes],
                     lambda nome: f'=SUMIFS({R("C")},{R("B")},"{nome.replace(chr(34), chr(34) * 2)}")')

    # ---- títulos e KPIs
    for col in range(1, 26):
        ws.column_dimensions[L(col)].width = 10 if col > 1 else 2
    ws["B1"] = "Distribuidora Aurora Ltda — Dashboard do Semestre"
    ws["B1"].font = Font(name=FONTE, size=18, bold=True, color="0F172A")
    ws["B2"] = f"{MESES[meses[0] - 1]} a {MESES[meses[-1] - 1].lower()} de {ano} · visão geral do caixa"
    ws["B2"].font = Font(name=FONTE, size=11, color="64748B")
    ws.row_dimensions[1].height = 28
    ws.row_dimensions[3].height = 10
    ws.row_dimensions[4].height = 22
    ws.row_dimensions[5].height = 34
    ws.row_dimensions[6].height = 22
    ws.row_dimensions[7].height = 14

    mes_rng = f"{L(c)}{lm}:{L(c)}{lm + nm - 1}"
    mes_val = f"{L(c + 1)}{lm}:{L(c + 1)}{lm + nm - 1}"
    cli_rng = f"{L(c + 9)}{lk}:{L(c + 9)}{lk + nk - 1}"
    cli_val = f"{L(c + 10)}{lk}:{L(c + 10)}{lk + nk - 1}"
    _card(ws, 2, "TOTAL RECEBIDO NO SEMESTRE", f"=SUM({R('C')})", "jan–jun · todos os pagadores", FMT_MOEDA)
    _card(ws, 7, "NÚMERO DE RECEBIMENTOS", f"=COUNT({R('C')})", "comprovantes conciliados", "0")
    _card(ws, 12, "TICKET MÉDIO", "=IFERROR(B5/G5,0)", "por recebimento", FMT_MOEDA)
    _card(ws, 17, "MELHOR MÊS", f"=INDEX({mes_rng},MATCH(MAX({mes_val}),{mes_val},0))",
          f"=MAX({mes_val})", fmt_d=FMT_MOEDA, texto_p=True)
    _card(ws, 22, "MAIOR CLIENTE", f"=INDEX({cli_rng},MATCH(MAX({cli_val}),{cli_val},0))",
          f"=MAX({cli_val})", fmt_d=FMT_MOEDA, texto_p=True)
    for lin in range(8, 54):
        ws.row_dimensions[lin].height = 15

    # ---- gráficos 2x2 (B9, N9 / B31, N31)
    _grafico(ws, "Caixa por mês", c, lm, nm, CORES["mes"], False, "B9", max(_soma(rows, lambda r: r.data.month).values()))
    _grafico(ws, "Caixa por região", c + 3, lr, nr, CORES["regiao"], False, "N9", max(_soma(rows, lambda r: r.regiao).values()))
    _grafico(ws, "Caixa por categoria", c + 6, lc, nc, CORES["categoria"], True, "B31", max(_soma(rows, lambda r: r.categoria).values()))
    _grafico(ws, "Ranking de clientes", c + 9, lk, nk, CORES["cliente"], True, "N31", clientes[0][1])

    # ---- impressão
    ws.print_area = "A1:Y53"
    ws.page_setup.orientation = "landscape"
    ws.page_setup.paperSize = ws.PAPERSIZE_A4
    ws.sheet_properties.pageSetUpPr = PageSetupProperties(fitToPage=True)
    ws.page_setup.fitToWidth = 1
    ws.page_setup.fitToHeight = 1
    ws.print_options.horizontalCentered = True
    ws.page_margins.left = ws.page_margins.right = 0.4
    wb.calculation.fullCalcOnLoad = True
    wb.save(cam.planilha)

    print("=== ETAPA 4 · Dashboard ===")
    print(f"Aba '{ABA_DASH}' criada: 5 KPIs, 4 gráficos ({nm} meses, {nr} regiões, {nc} categorias, {nk} clientes).")
    vazios = [n for n, q in [("mês", nm), ("região", nr), ("categoria", nc), ("clientes", nk)] if q == 0]
    print("Todos os gráficos têm dados." if not vazios else f"ATENÇÃO, gráficos sem dados: {vazios}")
    from .etapas_dados import brl
    print(f"Conferência: total {brl(sum(r.valor for r in rows))} em {len(rows)} recebimentos "
          f"(Não identificado: {brl(sum(r.valor for r in rows if not r.regiao))}).")


def _soma(rows, chave):
    d = defaultdict(float)
    for r in rows:
        d[chave(r)] += r.valor
    return d


def _ordenar(d):
    """Maior para menor, com 'Não identificado' sempre por último."""
    return sorted((k for k in d if k != NAO_IDENT), key=lambda k: -d[k]) + ([NAO_IDENT] if NAO_IDENT in d else [])
