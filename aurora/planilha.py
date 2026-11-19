"""Leitura/escrita da planilha Controle_Recebimentos.xlsx."""
from dataclasses import dataclass
from datetime import date, datetime
from decimal import Decimal

import openpyxl
from openpyxl.comments import Comment
from openpyxl.styles import Alignment, Font, PatternFill

from .config import ABA_CAD, ABA_REC, FMT_DATA, FMT_MOEDA, LINHA_INI

FONTE = "Calibri"
AMARELO = PatternFill("solid", fgColor="FFF4CC")
SEM_COR = PatternFill(fill_type=None)


@dataclass
class Linha:
    n: int
    data: date
    cliente: str
    valor: float
    forma: str
    regiao_uf: str | None
    categoria: str | None

    @property
    def regiao(self): return self.regiao_uf.split("/")[0] if self.regiao_uf else None


def abrir(caminho):
    return openpyxl.load_workbook(caminho)


def cadastro(wb) -> dict[str, tuple[str, str]]:
    ws = wb[ABA_CAD]
    out = {}
    for cli, reg, cat in ws.iter_rows(min_row=LINHA_INI, max_col=3, values_only=True):
        if cli:
            out[str(cli).strip()] = (str(reg).strip(), str(cat).strip())
    return out


def limpar_recebimentos(ws):
    if ws.max_row >= LINHA_INI:
        ws.delete_rows(LINHA_INI, ws.max_row - LINHA_INI + 1)


def escrever_linha(ws, n, data, cliente, valor: Decimal, forma):
    f = Font(name=FONTE, size=11)
    vals = [data, cliente, float(valor), forma]
    for col, v in enumerate(vals, start=1):
        c = ws.cell(n, col, v)
        c.font = f
    ws.cell(n, 1).number_format = FMT_DATA
    ws.cell(n, 3).number_format = FMT_MOEDA
    ws.cell(n, 3).alignment = Alignment(horizontal="right")


def marcar(ws, n, texto: str | None):
    """Destaca a linha (A:F) e coloca um comentário; texto=None remove a marca."""
    for col in range(1, 7):
        ws.cell(n, col).fill = AMARELO if texto else SEM_COR
    ws.cell(n, 2).comment = Comment(texto, "Aurora") if texto else None


def linhas(wb) -> list[Linha]:
    ws = wb[ABA_REC]
    out = []
    for n, row in enumerate(ws.iter_rows(min_row=LINHA_INI, max_col=6, values_only=True), LINHA_INI):
        d, cli, v, forma, reg, cat = row
        if d is None and cli is None:
            continue
        if isinstance(d, datetime):
            d = d.date()
        out.append(Linha(n, d, cli, float(v or 0), forma, reg or None, cat or None))
    return out


def ajustar_larguras(ws, minimo=10, maximo=60, min_row=4):
    larg = {}
    for row in ws.iter_rows(min_row=min_row):
        for c in row:
            if c.value is None or c.coordinate in ws.merged_cells:
                continue
            v = c.value
            txt = f"R$ {v:,.2f}" if isinstance(v, (int, float)) else (
                "00/00/0000" if isinstance(v, (date, datetime)) else str(v))
            larg[c.column_letter] = max(larg.get(c.column_letter, 0), len(txt))
    for col, w in larg.items():
        ws.column_dimensions[col].width = max(minimo, min(maximo, w + 3))
