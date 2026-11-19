"""Contrato entre o leitor (OCR) e o resto do pipeline: dados/leituras.csv.
Veja dados/LEITURAS_FORMATO.md. Aqui: carregar, validar e achar duplicados."""
import csv
import hashlib
import re
from dataclasses import dataclass, field
from datetime import date, datetime
from decimal import Decimal, InvalidOperation
from pathlib import Path

from .config import FORMAS
from . import nomes

CAMPOS = ["arquivo", "data", "cliente", "valor", "forma", "status", "obs", "arquivo_original"]


@dataclass
class Leitura:
    linha: int
    arquivo: str                 # nome atual na pasta Comprovantes
    arquivo_original: str        # nome antes da etapa 2 (para rastrear)
    data: date | None
    cliente: str
    valor: Decimal | None
    forma: str
    status: str                  # ok | ilegivel
    obs: str = ""
    duplicado_de: str | None = None
    erros: list[str] = field(default_factory=list)
    bruto: dict = field(default_factory=dict)    # linha original do CSV, preservada

    @property
    def lancavel(self) -> bool:
        return self.status == "ok" and not self.erros and self.duplicado_de is None


def _valor(txt: str) -> Decimal:
    t = re.sub(r"[^\d,.\-]", "", txt.strip())
    if "," in t:                         # padrão BR: 15.550,00
        t = t.replace(".", "").replace(",", ".")
    elif t.count(".") > 1:               # 15.550.000 sem centavos
        t = t.replace(".", "")
    return Decimal(t).quantize(Decimal("0.01"))


def _data(txt: str) -> date:
    for fmt in ("%Y-%m-%d", "%d/%m/%Y"):
        try:
            return datetime.strptime(txt.strip(), fmt).date()
        except ValueError:
            pass
    raise ValueError(txt)


def _hash(p: Path) -> str | None:
    if not p.exists():
        return None
    return hashlib.sha256(p.read_bytes()).hexdigest()


def carregar(caminho: Path, pasta: Path | None = None, cadastro: list[str] | None = None,
             apelidos: dict | None = None) -> list[Leitura]:
    if not caminho.exists():
        raise SystemExit(f"Arquivo de leituras não encontrado: {caminho}\n"
                         "Gere-o com o seu leitor OCR (formato em dados/LEITURAS_FORMATO.md).")
    with caminho.open(encoding="utf-8-sig", newline="") as f:
        linhas = list(csv.DictReader(f, delimiter=";"))
    out = []
    for i, r in enumerate(linhas, start=2):
        r = {k: (v or "").strip() for k, v in r.items() if k}
        status = (r.get("status") or "ok").lower()
        status = "ilegivel" if status.startswith("ileg") else "ok"
        lt = Leitura(i, r.get("arquivo", ""), r.get("arquivo_original") or r.get("arquivo", ""),
                     None, r.get("cliente", ""), None, "", status, r.get("obs", ""), bruto=r)
        if not lt.arquivo:
            lt.erros.append("sem nome de arquivo")
        if status == "ok":
            try:
                lt.data = _data(r.get("data", ""))
            except ValueError:
                lt.erros.append(f"data inválida '{r.get('data')}'")
            try:
                lt.valor = _valor(r.get("valor", ""))
                if lt.valor <= 0:
                    lt.erros.append("valor não positivo")
            except InvalidOperation:
                lt.erros.append(f"valor inválido '{r.get('valor')}'")
            fk = nomes.sem_acento(r.get("forma", "")).lower()
            lt.forma = FORMAS.get(fk, "")
            if not lt.forma:
                lt.erros.append(f"forma de pagamento desconhecida '{r.get('forma')}'")
            if not lt.cliente:
                lt.erros.append("sem cliente")
        out.append(lt)
    _marcar_duplicados(out, pasta, cadastro or [], apelidos or {})
    return out


def _marcar_duplicados(lts: list[Leitura], pasta, cadastro, apelidos):
    """Mesmo pagamento em dois arquivos = reenvio. Critérios:
    (1) arquivos idênticos byte a byte; (2) mesmo cliente + mesma data + mesmo valor.
    Mesmo cliente e valor em datas diferentes NÃO é duplicado."""
    vistos_hash, vistos_chave = {}, {}
    for lt in sorted(lts, key=lambda x: x.arquivo_original.lower()):
        h = _hash(pasta / lt.arquivo) if pasta else None
        if h and h in vistos_hash:
            lt.duplicado_de = vistos_hash[h]
            continue
        if h:
            vistos_hash[h] = lt.arquivo
        if not (lt.status == "ok" and not lt.erros):
            continue
        cas = nomes.casar(lt.cliente, cadastro, apelidos) if cadastro else None
        quem = cas.cliente if cas and cas.cliente else nomes.chave(lt.cliente)
        k = (quem, lt.data, lt.valor)
        if k in vistos_chave:
            lt.duplicado_de = vistos_chave[k]
        else:
            vistos_chave[k] = lt.arquivo


def salvar(caminho: Path, lts: list[Leitura]):
    """Regrava o CSV (usado pela etapa 2 para atualizar o nome atual dos arquivos)."""
    with caminho.open("w", encoding="utf-8-sig", newline="") as f:
        w = csv.DictWriter(f, fieldnames=CAMPOS, delimiter=";", extrasaction="ignore")
        w.writeheader()
        for lt in lts:
            w.writerow({**lt.bruto, "arquivo": lt.arquivo, "arquivo_original": lt.arquivo_original})
