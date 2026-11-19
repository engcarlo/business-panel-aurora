"""Camada de regras do extrator híbrido: texto (Markdown do Docling) -> campos.

Um leitor por layout de banco. Cada leitor só devolve status 'ok' quando achou os
quatro campos de forma inequívoca; qualquer dúvida devolve 'revisar' e o comprovante
segue para a camada de IA (ou para conferência manual). Nunca chuta."""
from __future__ import annotations

import re
import unicodedata
from datetime import date

AURORA = "distribuidora aurora"
MESES = {m: i for i, m in enumerate(["janeiro", "fevereiro", "marco", "abril", "maio", "junho", "julho",
                                      "agosto", "setembro", "outubro", "novembro", "dezembro"], 1)}
MES3 = {k[:3]: v for k, v in MESES.items()}
# OCR costuma trocar "R$" por "RS", "R5", "R§"...
RE_VALOR = re.compile(r"(?:R\s?[\$S5§]\s*)?(\d{1,3}(?:[.\s]\d{3})+,\d{2}|\d+,\d{2}|\d+\.\d{2}(?!\d))")


# ------------------------------------------------------------------ normalização
def _sem_acento(s: str) -> str:
    return "".join(c for c in unicodedata.normalize("NFKD", s) if not unicodedata.combining(c))


def linhas(md: str) -> list[str]:
    """Markdown -> linhas de texto. Células de tabela viram linhas separadas."""
    out = []
    for raw in md.splitlines():
        raw = raw.replace("<!-- image -->", " ")
        raw = re.sub(r"(\d)\s+([.,])\s*(\d)", r"\1\2\3", raw)    # OCR: "11450 .00" -> "11450.00"
        if re.fullmatch(r"\s*\|?[\s:\-|]+\|?\s*", raw):          # separador de tabela
            continue
        partes = [p for p in raw.split("|")] if "|" in raw else [raw]
        # Docling/OCR põem rótulo e valor na mesma linha separados por 2+ espaços
        partes = [q for p in partes for q in re.split(r"\s{2,}|\t", p)]
        for p in partes:
            p = re.sub(r"^[#>*\-\s]+|[*_`]+", " ", p)
            p = re.sub(r"\s+", " ", p).strip(" ·.")
            # OCR troca o ponto decimal por espaço ou barra: "1130 00", "1130 \ 00" -> "1130.00"
            p = re.sub(r"^(\d+)\s*[\\/ ]\s*(\d{2})$", r"\1.\2", p)
            if p and not re.fullmatch(r"[=\-_*·.]+", p):
                out.append(p)
    # tabelas do Docling repetem células mescladas: remove repetições seguidas
    return [l for i, l in enumerate(out) if i == 0 or l != out[i - 1]]


def _k(s: str) -> str:
    return _sem_acento(s).lower()


def _valor(s: str) -> float | None:
    m = RE_VALOR.search(s)
    if not m:
        return None
    t = m.group(1).replace(" ", "")
    t = t.replace(".", "").replace(",", ".") if "," in t else t
    try:
        return round(float(t), 2)
    except ValueError:
        return None


def _valor_inteiro(s: str) -> float | None:
    """Zaply mostra 'R$ 6.070' sem centavos."""
    m = re.search(r"R\s?[\$S5]\s*(\d{1,3}(?:\.\d{3})*|\d+)(?:,(\d{2}))?\b", s)
    if not m:
        return None
    return round(float(m.group(1).replace(".", "") + "." + (m.group(2) or "00")), 2)


def _data(s: str, ano_padrao: int | None = None) -> date | None:
    t = _k(s)
    for rx, ordem in ((r"(\d{4})-(\d{2})-(\d{2})", "ymd"), (r"(\d{1,2})/(\d{1,2})/(\d{4})", "dmy"),
                      (r"(\d{1,2})/(\d{1,2})/(\d{2})\b", "dmy2")):
        m = re.search(rx, t)
        if m:
            a, b, c = (int(x) for x in m.groups())
            try:
                return date(a, b, c) if ordem == "ymd" else date(c + (2000 if ordem == "dmy2" else 0), b, a)
            except ValueError:
                return None
    m = re.search(r"(\d{1,2}) de ([a-z]+) de (\d{4})", t)
    if m and m.group(2) in MESES:
        return _seguro(int(m.group(3)), MESES[m.group(2)], int(m.group(1)))
    m = re.search(r"aos (\d{1,2}) dias do mes de ([a-z]+) de (\d{4})", t)
    if m and m.group(2) in MESES:
        return _seguro(int(m.group(3)), MESES[m.group(2)], int(m.group(1)))
    m = re.search(r"\b(\d{1,2}) ([a-z]{3}) (\d{4})", t)
    if m and m.group(2) in MES3:
        return _seguro(int(m.group(3)), MES3[m.group(2)], int(m.group(1)))
    m = re.search(r"\b(\d{1,2})/(\d{1,2})\b", t)
    if m and ano_padrao:
        return _seguro(ano_padrao, int(m.group(2)), int(m.group(1)))
    return None


def _seguro(a, m, d):
    try:
        return date(a, m, d)
    except ValueError:
        return None


def _forma(s: str) -> str | None:
    t = _k(s)
    if "pix" in t:
        return "Pix"
    if re.search(r"\bted\b", t):
        return "TED"
    if "transferencia" in t:
        return "Transferência"
    if re.search(r"boleto|titulo|cobranca", t):
        return "Boleto"
    if "deposito" in t:
        return "Depósito"
    return None


def _apos(ls: list[str], rotulo: str, n: int = 1, inicio: int = 0) -> str | None:
    """Valor de 'Rótulo: valor' na mesma linha, ou na(s) linha(s) seguinte(s)."""
    r = _k(rotulo)
    for i in range(inicio, len(ls)):
        li = _k(ls[i])
        if li.startswith(r):
            resto = ls[i][len(rotulo):].strip(" :.")
            if resto and len(_k(resto)) > 1:
                return resto
            if i + n < len(ls):
                return ls[i + n]
    return None


def _idx(ls, rotulo, inicio=0):
    r = _k(rotulo)
    for i in range(inicio, len(ls)):
        if _k(ls[i]).startswith(r):
            return i
    return -1


def _pagador_ok(nome: str | None) -> str | None:
    if not nome:
        return None
    nome = re.split(r"\b(?:cnpj|cpf)\b", nome, flags=re.I)[0]     # OCR junta o CNPJ ao nome
    nome = re.sub(r"\s+", " ", nome).strip(" ,.:;-")
    k = _k(nome)
    if len(k) < 3 or AURORA in k or re.fullmatch(r"[\d./\- ]+", k) or k.startswith(("cnpj", "cpf", "banco ")):
        return None
    if len(re.findall(r"[a-z]{2,}", k)) < 2:      # nome de 1 palavra = provável corte do OCR
        return None
    return nome


def _campo(ls, rotulo, valido):
    """Valor de um rótulo aceitando as duas ordens que o OCR produz:
    'Rótulo' -> valor (normal) ou valor -> 'Rótulo' (foto com colunas trocadas)."""
    r = _k(rotulo)
    for i, l in enumerate(ls):
        if _k(l) != r and not _k(l).startswith(r + " ") and not _k(l).startswith(r + ":"):
            continue
        resto = l[len(rotulo):].strip(" :.")
        for cand in ([resto] if resto else []) + ([ls[i + 1]] if i + 1 < len(ls) else []) + ([ls[i - 1]] if i else []):
            if cand and valido(cand):
                return cand
    return None


# ------------------------------------------------------------------ leitores por layout
def _ocr_k(s: str) -> str:
    """Chave tolerante às trocas típicas do OCR em letras maiúsculas (T->I, O->0, L->1)."""
    return _k(s).replace("1", "l").replace("0", "o").replace("i", "t")


def _rotulo(ls, rx, inicio=0):
    """Índice da primeira linha cujo texto (tolerante a OCR) casa com a regex do rótulo."""
    r = re.compile(rx)
    for i in range(inicio, len(ls)):
        if r.search(_ocr_k(ls[i])):
            return i
    return -1


def _meridiano(ls):
    tipo = (_campo(ls, "Tipo de operacao", _forma)
            or next((l for l in ls if re.search(r"comprovante de .*(recebid|boleto|deposito)", _k(l))), ""))
    monetario = lambda s: bool(re.search(r"R\s?[\$S5]\s*\d|\d,\d{2}\b", s)) and _valor(s)   # nunca a hora "13.53.40"
    return dict(data=_data(_campo(ls, "Data", _data) or ""), valor=_valor(_campo(ls, "Valor", monetario) or ""),
                cliente=_campo(ls, "Origem", _pagador_ok), forma=_forma(tipo))


def _serra(ls):
    i = _idx(ls, "VALOR DA OPERACAO")
    v = next((_valor(l) for l in ls[i + 1:i + 3] if _valor(l)), None) if i >= 0 else None
    d = next((_data(l) for l in ls[:8] if _data(l)), None) or _data(_apos(ls, "Data contabil") or "")
    return dict(data=d, valor=v, cliente=_apos(ls, "CONTA DE ORIGEM"),
                forma=_forma(_apos(ls, "Modalidade") or ""))


def _credisolar(ls):
    txt = " ".join(ls)
    m = re.search(r"recebeu de\s+(.+?),\s*inscrit", txt, re.I)
    mv = re.search(r"importancia de\s+(R\s?[\$S5]\s*[\d.]+,\d{2})", _sem_acento(txt), re.I)
    mf = re.search(r"por meio de\s+([^,]+)", txt, re.I)
    return dict(data=_data(txt[txt.lower().find("aos "):] if "aos " in txt.lower() else ""),
                valor=_valor(mv.group(1)) if mv else None,
                cliente=m.group(1) if m else None, forma=_forma(mf.group(1)) if mf else None)


def _paglesto(ls):
    num = lambda s: (float(m.group(1)) if (m := re.search(r"(?:^|[\s=.])(\d+\.\d{2})\s*$", s)) else None)
    # 1) rótulo TOTAL PAGO com o valor na mesma linha ou na seguinte
    i = _rotulo(ls, r"^total pago")
    v = (num(ls[i]) or (num(ls[i + 1]) if i < len(ls) - 1 else None)) if i >= 0 else None
    # 2) foto com ordem embaralhada: confere a conta valor doc - desconto + juros = total
    if v is None:
        j = _rotulo(ls, r"^valor doc")
        nums = [n for n in (num(l) for l in ls[j:]) if n is not None] if j >= 0 else []
        # doc - desconto (+ juros) tem que fechar com o último número (total); senão não chuta
        if len(nums) >= 4 and abs(nums[0] - nums[1] + nums[2] - nums[-1]) < 0.01:
            v = nums[-1]
        elif len(nums) == 3 and abs(nums[0] - nums[1] - nums[2]) < 0.01:
            v = nums[2]
    texto = _ocr_k(" ".join(ls))
    forma = ("Boleto" if re.search(r"tttulo|boleto", texto)
             else "Depósito" if re.search(r"dep.?stto|deposito", texto) else None)
    d = next((_data(l) for l in ls if re.search(r"\d{2}/\d{2}/\d{2}", l) and _data(l)), None)
    k = _rotulo(ls, r"^cl.?en.?e$")       # CLIENTE (OCR: CLIENIE, CL1ENTE...)
    nome = []                             # o nome pode vir partido em várias linhas até o CNPJ
    for l in ls[k + 1:k + 4] if k >= 0 else []:
        if re.match(r"(cnpj|cpf|favorecido)", _k(l)):
            break
        nome.append(l)
    return dict(data=d, valor=v, cliente=" ".join(nome) or None, forma=forma)


def _valeclaro(ls):
    per = _apos(ls, "Periodo") or ""
    anos = re.findall(r"\d{2}/\d{2}/(\d{4})", per)
    ano = int(anos[0]) if anos else None
    creditos = []
    for i, l in enumerate(ls):
        # formato 1: lançamento inteiro numa linha (texto embutido do PDF)
        m1 = re.match(r"(\d{2}/\d{2})\s+(.+?)\s*-\s*Remetente:\s*(.+?)\s+\d{4,}\s+([\d.]+,\d{2})\s*C\b", l, re.I)
        if m1:
            creditos.append(dict(data=_data(m1.group(1), ano), valor=_valor(m1.group(4)),
                                 cliente=m1.group(3), forma=_forma(m1.group(2))))
            continue
        # formato 2: uma célula por linha (pypdf / Docling)
        m = re.search(r"remetente:\s*(.+)$", l, re.I)
        if not m:
            continue
        # data: linha anterior com dd/mm; valor: próxima linha terminada em ' C'
        d = next((_data(ls[j], ano) for j in range(i - 1, max(i - 3, -1), -1) if re.fullmatch(r"\d{2}/\d{2}", ls[j])), None)
        v = next((_valor(ls[j]) for j in range(i + 1, min(i + 4, len(ls))) if re.search(r"\bC$", ls[j])), None)
        creditos.append(dict(data=d, valor=v, cliente=m.group(1), forma=_forma(l.split("-")[0])))
    if len(creditos) == 1:
        return creditos[0]
    return dict(data=None, valor=None, cliente=None, forma=None,
                _motivo=f"extrato com {len(creditos)} créditos de clientes")


def _pontal(ls):
    i = _idx(ls, "Detalhes do credito")
    cliente = ls[i + 1] if 0 <= i < len(ls) - 1 else None
    # "Pix · 11 MAR 2026 · 14:43" pode vir numa linha só ou quebrado em várias
    janela = _k(" ".join(ls[i + 1:i + 9])) if i >= 0 else ""
    m = re.search(r"\b(pix|ted|transferencia|boleto|deposito)\W+(\d{1,2} [a-z]{3} \d{4})", janela)
    return dict(data=_data(m.group(2)) if m else _data(_apos(ls, "Assunto") or ""),
                valor=_valor(_apos(ls, "Total creditado") or ""),
                cliente=cliente, forma=_forma(m.group(1)) if m else None)


def _rumocerto(ls):
    v = _valor(_apos(ls, "VALOR") or "") or next(
        (_valor(l) for l in ls[:10] if re.match(r"R\s?[\$S5]", l) and _valor(l)), None)
    # foto: o rótulo "Nome do pagador:" pode vir partido ("pagador: Fulano" / "Nome do")
    cliente = _apos(ls, "Nome do pagador") or next(
        (m.group(1) for l in ls if (m := re.match(r"pagador:\s*(.+)$", l, re.I)) and _pagador_ok(m.group(1))), None) or next(
        (ls[i + 1] for i, l in enumerate(ls[:-1]) if _k(l) == "pagador:" and _pagador_ok(ls[i + 1])), None)
    d = _data(_campo(ls, "Data", lambda s: bool(re.fullmatch(r"\d{1,2}/\d{1,2}/\d{4}", s.strip()))) or "")
    return dict(data=d, valor=v, cliente=cliente,
                forma=_forma(_apos(ls, "Forma de recebimento") or ""))


def _zaply(ls):
    # foto/print: a ordem de leitura pode vir trocada, então procura no documento todo
    tipo = next((l for l in ls if re.search(r"(pix|transferencia|ted|deposito)\s+recebid", _k(l))), "")
    v = next((_valor_inteiro(l) for l in ls
              if re.fullmatch(r"R\s?[\$S5]\s*[\d.]+(,\d{2})?", l.strip()) and _valor_inteiro(l)), None)
    d = next((_data(l) for l in ls if re.search(r"\d{1,2} de [a-z]+ de \d{4}", _k(l)) and _data(l)), None)
    return dict(data=d, valor=v, cliente=_apos(ls, "Debitado de"), forma=_forma(tipo))


LAYOUTS = [  # (marca no CABEÇALHO, nome, leitor) — o corpo cita bancos de origem, por isso só o topo
    ("bancomeridiano", "Meridiano", _meridiano),
    ("serradourada", "Serra Dourada", _serra),
    ("credisolar", "CrediSolar", _credisolar),
    ("cooperativadecreditosolar", "CrediSolar", _credisolar),
    ("paglesto", "PagLesto", _paglesto),
    ("valeclaro", "Vale Claro", _valeclaro),
    ("bancopontal", "Pontal", _pontal),
    ("rumocerto", "Rumo Certo", _rumocerto),
    ("zaply", "Zaply", _zaply),
]


def identificar(ls: list[str]):
    # 1º a estrutura (combinação de rótulos única de cada layout): não se confunde com o
    #    banco de origem citado no corpo quando o cabeçalho foi cortado na foto
    tudo = re.sub(r"[^a-z]", "", _k(" ".join(ls)))
    for marcas, nome, f in IMPRESSOES:
        if all(m in tudo for m in marcas):
            return nome, f
    # 2º a marca do banco no cabeçalho
    topo = re.sub(r"[^a-z]", "", _k(" ".join(ls[:4])))
    achados = [(topo.find(chave), nome, f) for chave, nome, f in LAYOUTS if chave in topo]
    if achados:                         # a marca que aparece PRIMEIRO é o emissor
        _, nome, f = min(achados, key=lambda x: x[0])
        return nome, f
    return None, None


IMPRESSOES = [  # combinações de rótulos que só um layout tem
    (("valordaoperacao", "contadeorigem", "datacontabil"), "Serra Dourada", _serra),
    (("tipodeoperacao", "instituicaodeorigem", "protocolo"), "Meridiano", _meridiano),
    (("comprovantedepixrecebido", "instituicaodeorigem"), "Meridiano", _meridiano),
    (("idzaply",), "Zaply", _zaply),
    (("debitadode", "creditadoem"), "Zaply", _zaply),
    (("recebeude", "aimportanciade"), "CrediSolar", _credisolar),
    (("nomedopagador", "formaderecebimento"), "Rumo Certo", _rumocerto),
    (("detalhesdocredito", "totalcreditado"), "Pontal", _pontal),
    (("extratodeconta", "remetente"), "Vale Claro", _valeclaro),
    (("autenticacaomecanica", "favorecido"), "PagLesto", _paglesto),
]


def extrair(md: str) -> dict:
    ls = linhas(md)
    nome, leitor = identificar(ls)
    if not leitor:
        return {"status": "revisar", "obs": "layout não reconhecido", "layout": ""}
    try:
        r = leitor(ls)
    except Exception as e:  # texto de OCR muito quebrado
        return {"status": "revisar", "obs": f"{nome}: falha ao interpretar ({type(e).__name__})", "layout": nome}
    cliente = _pagador_ok(r.get("cliente"))
    faltando = [c for c, v in (("data", r.get("data")), ("cliente", cliente), ("valor", r.get("valor")),
                               ("forma", r.get("forma"))) if not v]
    if faltando:
        motivo = r.get("_motivo") or f"não encontrado: {', '.join(faltando)}"
        return {"status": "revisar", "obs": f"{nome}: {motivo}", "layout": nome}
    return {"status": "ok", "layout": nome, "data": r["data"].isoformat(), "cliente": cliente,
            "valor": f"{r['valor']:.2f}", "forma": r["forma"], "obs": f"regras: {nome}"}
