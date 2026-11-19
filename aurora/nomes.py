"""Normalização de nomes e casamento pagador -> cliente do cadastro.

Regra: só padroniza quando é *claramente* o mesmo cliente. Na dúvida,
devolve 'revisar' em vez de forçar o cliente mais parecido."""
import csv
import difflib
import re
import unicodedata
from dataclasses import dataclass
from pathlib import Path

STOP = {"ltda", "me", "epp", "eireli", "sa", "s", "a", "de", "do", "da", "dos",
        "das", "e", "cia", "comercio", "com", "industria", "servicos", "the"}

ACEITA = 0.70      # pontuação mínima para padronizar automaticamente
REVISAR = 0.45     # entre REVISAR e ACEITA: não padroniza, mas avisa
MARGEM = 0.15      # o melhor precisa ganhar do segundo com folga


def sem_acento(s: str) -> str:
    return "".join(c for c in unicodedata.normalize("NFKD", s)
                   if not unicodedata.combining(c))


def tokens(s: str) -> list[str]:
    s = re.sub(r"[^a-z0-9 ]+", " ", sem_acento(s).lower())
    return [t for t in s.split() if t not in STOP]


def chave(s: str) -> str:
    """Forma canônica para comparar nomes iguais escritos de jeitos diferentes."""
    return " ".join(tokens(s))


def _tok_igual(a: str, b: str) -> bool:
    if a == b:
        return True
    if len(a) >= 3 and b.startswith(a) or len(b) >= 3 and a.startswith(b):
        return True                                  # abreviação: "farm" ~ "farmacias"
    curto, longo = sorted((a, b), key=len)
    if 2 <= len(curto) <= 3 and len(longo) >= 4 and curto[0] == longo[0] and _subseq(curto, longo):
        return True                                  # abreviação por consoantes: "pt" ~ "ponto"
    return (len(a) >= 4 and len(b) >= 4 and
            difflib.SequenceMatcher(None, a, b).ratio() >= 0.8)   # erro de digitação


def _subseq(curto: str, longo: str) -> bool:
    it = iter(longo)
    return all(c in it for c in curto)


def pontuar(pagador: str, cliente: str) -> float:
    tp, tc = tokens(pagador), tokens(cliente)
    if not tp or not tc:
        return 0.0
    cob_cli = sum(any(_tok_igual(p, c) for p in tp) for c in tc) / len(tc)
    cob_pag = sum(any(_tok_igual(p, c) for c in tc) for p in tp) / len(tp)
    if cob_cli < 0.6:          # precisa cobrir a maior parte do nome cadastrado
        return min(cob_cli, (cob_cli + cob_pag) / 2)
    return (cob_cli + cob_pag) / 2


@dataclass
class Casamento:
    pagador: str
    cliente: str | None      # nome do cadastro, ou None
    status: str              # exato | padronizado | apelido | revisar | nao_encontrado
    pontuacao: float
    sugestao: str | None = None
    motivo: str = ""


def carregar_apelidos(caminho: Path) -> dict[str, str]:
    """dados/apelidos.csv (pagador;cliente) — correções manuais para razões
    sociais que não se parecem com o nome usual."""
    if not caminho.exists():
        return {}
    with caminho.open(encoding="utf-8-sig", newline="") as f:
        return {chave(r["pagador"]): r["cliente"].strip()
                for r in csv.DictReader(f, delimiter=";") if r.get("pagador")}


def casar(pagador: str, cadastro: list[str], apelidos: dict[str, str]) -> Casamento:
    k = chave(pagador)
    for c in cadastro:
        if pagador.strip() == c:
            return Casamento(pagador, c, "exato", 1.0)
    if k in apelidos:
        return Casamento(pagador, apelidos[k], "apelido", 1.0, motivo="definido em apelidos.csv")
    for c in cadastro:
        if chave(c) == k:
            return Casamento(pagador, c, "padronizado", 1.0,
                             motivo="mesmo nome com diferença de acento, caixa ou sufixo (Ltda/ME)")
    notas = sorted(((pontuar(pagador, c), c) for c in cadastro), reverse=True)
    (n1, c1), (n2, _) = notas[0], notas[1]
    if n1 >= ACEITA and n1 - n2 >= MARGEM:
        return Casamento(pagador, c1, "padronizado", n1,
                         motivo=f"abreviação, razão social ou erro de digitação (similaridade {n1:.0%})")
    if n1 >= REVISAR:
        return Casamento(pagador, None, "revisar", n1, sugestao=c1,
                         motivo=f"parecido com '{c1}' ({n1:.0%}), mas não o suficiente para padronizar")
    return Casamento(pagador, None, "nao_encontrado", n1)
