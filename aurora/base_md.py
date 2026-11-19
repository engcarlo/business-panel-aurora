"""Camada intermediária em Markdown: base_md/AAAA/MM-mes/<comprovante>.md + resumos.

Por que existe: ler 230 comprovantes (imagens/PDFs) a cada pergunta é caro. Aqui cada
comprovante vira um .md pequeno (dados conferidos + trecho do texto lido) e cada mês ganha
um _resumo.md com tabelas e totais. O chat de análise lê primeiro os resumos e só abre
arquivos individuais quando precisa — muito menos tokens.

Organização obrigatória:  base_md/<ano>/<MM-mes>/<arquivo>.md
  README.md                visão geral + índice
  <ano>/_resumo_<ano>.md   ano por mês
  <ano>/<MM-mes>/_resumo.md
  _pendencias/             ilegíveis, duplicados e fora do cadastro
"""
from __future__ import annotations

import re
import shutil
from collections import defaultdict
from datetime import date, datetime
from pathlib import Path

from . import leituras as L, nomes, planilha
from .config import MESES, Caminhos

MARCA = "origem: aurora"          # arquivos gerados pela rotina (podem ser recriados)
PADRAO_PASTA = re.compile(r"^\d{4}$")
PADRAO_MES = re.compile(r"^(\d{2})-[a-zç]+$")


def raiz(cam: Caminhos) -> Path:
    return cam.base / "base_md"


def pasta_mes(base: Path, d: date) -> Path:
    return base / f"{d.year}" / f"{d.month:02d}-{_sem_acento(MESES[d.month - 1]).lower()}"


def _sem_acento(s):
    return nomes.sem_acento(s)


def brl(v) -> str:
    return "R$ " + f"{float(v):,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")


def _texto_ocr(cam: Caminhos, original: str, limite=40) -> str:
    """Trecho do texto lido (cache do OCR), só as linhas úteis — o suficiente para auditoria."""
    for suf in (".raw.txt", ".md"):
        p = cam.dados / "ocr_md" / (original + suf)
        if p.exists():
            ls = [l.strip() for l in p.read_text(encoding="utf-8").splitlines()]
            ls = [l for l in ls if l and "<!-- image -->" not in l and not re.fullmatch(r"[|\-:\s]+", l)]
            return "\n".join(ls[:limite])
    return ""


def _frontmatter(txt: str) -> dict:
    m = re.match(r"^---\n(.*?)\n---", txt, re.S)
    if not m:
        return {}
    out = {}
    for l in m.group(1).splitlines():
        if ":" in l:
            k, v = l.split(":", 1)
            out[k.strip()] = v.strip().strip('"')
    return out


# ------------------------------------------------------------------ geração
def gerar(cam: Caminhos) -> dict:
    wb = planilha.abrir(cam.planilha)
    cad = planilha.cadastro(wb)
    ap = nomes.carregar_apelidos(cam.apelidos)
    lts = L.carregar(cam.leituras, cam.comprovantes, list(cad), ap)
    base = raiz(cam)
    base.mkdir(exist_ok=True)

    # remove só o que a própria rotina gerou antes (arquivos feitos à mão são preservados)
    for p in base.rglob("*.md"):
        if MARCA in p.read_text(encoding="utf-8", errors="ignore")[:400]:
            p.unlink()

    itens, pend = [], defaultdict(list)
    for lt in lts:
        cas = nomes.casar(lt.cliente, list(cad), ap) if lt.cliente else None
        if lt.duplicado_de:
            pend["duplicados"].append(lt)
            continue
        if lt.status == "ilegivel" or lt.erros:
            pend["ilegiveis"].append(lt)
            continue
        cli = cas.cliente if cas and cas.cliente else lt.cliente
        reg, cat = cad.get(cli, (None, None))
        sit = "lancado" if reg else "fora_do_cadastro"
        if sit == "fora_do_cadastro":
            pend["fora"].append(lt)
        itens.append(dict(lt=lt, cliente=cli, regiao=reg, categoria=cat, situacao=sit))

    rel_comp = lambda p: Path(*[".."] * (len(p.relative_to(cam.base).parts) - 1)) / "Comprovantes"
    for it in itens:
        lt = it["lt"]
        destino = pasta_mes(base, lt.data)
        destino.mkdir(parents=True, exist_ok=True)
        arq = destino / (Path(lt.arquivo).stem + ".md")
        link = (rel_comp(arq) / lt.arquivo).as_posix()
        ocr = _texto_ocr(cam, lt.arquivo_original)
        arq.write_text(
            f"---\n{MARCA}\ntipo: comprovante\ndata: {lt.data.isoformat()}\ncliente: \"{it['cliente']}\"\n"
            f"cliente_no_comprovante: \"{lt.cliente}\"\nvalor: {lt.valor:.2f}\nforma: {lt.forma}\n"
            f"regiao_uf: {it['regiao'] or ''}\ncategoria: {it['categoria'] or ''}\nsituacao: {it['situacao']}\n"
            f"arquivo: \"{lt.arquivo}\"\narquivo_original: \"{lt.arquivo_original}\"\n---\n\n"
            f"# {lt.data:%d/%m/%Y} · {it['cliente']} · {brl(lt.valor)}\n\n"
            f"| Campo | Valor |\n|---|---|\n| Forma | {lt.forma} |\n| Região/UF | {it['regiao'] or 'Não identificado'} |\n"
            f"| Categoria | {it['categoria'] or 'Não identificado'} |\n| Situação | {it['situacao'].replace('_', ' ')} |\n"
            f"| Comprovante | [{lt.arquivo}]({link.replace(' ', '%20')}) |\n"
            + (f"\n## Texto lido (resumo)\n\n```text\n{ocr}\n```\n" if ocr else ""),
            encoding="utf-8")

    _pendencias(base, pend)
    resumo = indices(cam)
    resumo.update(comprovantes=len(itens), pendencias={k: len(v) for k, v in pend.items()})
    return resumo


def _pendencias(base: Path, pend):
    p = base / "_pendencias"
    p.mkdir(exist_ok=True)
    titulos = {"ilegiveis": "Comprovantes ilegíveis (conferir à mão)",
               "duplicados": "Comprovantes duplicados (reenvios, lançados uma vez só)",
               "fora": "Pagadores fora do cadastro (lançados, sem região/categoria)"}
    for k, t in titulos.items():
        linhas = [f"---\n{MARCA}\ntipo: pendencia\n---\n\n# {t}\n", f"Total: {len(pend[k])}\n",
                  "| Arquivo | Data | Pagador | Valor | Observação |", "|---|---|---|---|---|"]
        for lt in pend[k]:
            linhas.append(f"| {lt.arquivo} | {lt.data or ''} | {lt.cliente or ''} | "
                          f"{brl(lt.valor) if lt.valor else ''} | {lt.duplicado_de and 'reenvio de ' + lt.duplicado_de or lt.obs or ''} |")
        (p / f"{k}.md").write_text("\n".join(linhas) + "\n", encoding="utf-8")


# ------------------------------------------------------------------ índices
def _ler_comprovantes(base: Path) -> list[tuple[Path, dict]]:
    out = []
    for p in base.rglob("*.md"):
        if p.name.startswith("_") or p.name == "README.md" or "_pendencias" in p.parts:
            continue
        fm = _frontmatter(p.read_text(encoding="utf-8", errors="ignore"))
        if fm.get("tipo") == "comprovante" and fm.get("data"):
            out.append((p, fm))
    return out


def indices(cam: Caminhos) -> dict:
    """(Re)gera _resumo.md de cada mês, _resumo_<ano>.md e o README.md a partir dos .md existentes."""
    base = raiz(cam)
    docs = _ler_comprovantes(base)
    por_mes = defaultdict(list)
    for p, fm in docs:
        d = date.fromisoformat(fm["data"])
        por_mes[(d.year, d.month)].append((p, fm))

    def tabela_soma(lista, chave, titulo):
        s = defaultdict(float)
        for _, fm in lista:
            s[fm.get(chave) or "Não identificado"] += float(fm["valor"])
        tot = sum(s.values()) or 1
        linhas = [f"| {titulo} | Valor | % |", "|---|---:|---:|"]
        linhas += [f"| {k} | {brl(v)} | {v / tot:.0%} |" for k, v in sorted(s.items(), key=lambda kv: -kv[1])]
        return "\n".join(linhas)

    anos = defaultdict(dict)
    for (a, m), lista in sorted(por_mes.items()):
        pasta = pasta_mes(base, date(a, m, 1))
        total = sum(float(fm["valor"]) for _, fm in lista)
        anos[a][m] = (total, len(lista))
        det = ["| Data | Cliente | Valor | Forma | Situação | Arquivo |", "|---|---|---:|---|---|---|"]
        for p, fm in sorted(lista, key=lambda x: (x[1]["data"], x[1]["cliente"])):
            det.append(f"| {fm['data'][8:]}/{fm['data'][5:7]} | {fm['cliente']} | {brl(fm['valor'])} | "
                       f"{fm['forma']} | {fm['situacao'].replace('_', ' ')} | [{p.name}]({p.name.replace(' ', '%20')}) |")
        (pasta / "_resumo.md").write_text(
            f"---\n{MARCA}\ntipo: resumo_mes\nano: {a}\nmes: {m}\n---\n\n"
            f"# {MESES[m - 1]} de {a}\n\n**Total recebido:** {brl(total)} em {len(lista)} recebimentos "
            f"(ticket médio {brl(total / len(lista))}).\n\n"
            f"## Por cliente\n\n{tabela_soma(lista, 'cliente', 'Cliente')}\n\n"
            f"## Por forma de pagamento\n\n{tabela_soma(lista, 'forma', 'Forma')}\n\n"
            f"## Por região/UF\n\n{tabela_soma(lista, 'regiao_uf', 'Região/UF')}\n\n"
            f"## Por categoria\n\n{tabela_soma(lista, 'categoria', 'Categoria')}\n\n"
            f"## Recebimentos\n\n" + "\n".join(det) + "\n", encoding="utf-8")

    for a, meses in anos.items():
        linhas = ["| Mês | Recebimentos | Total |", "|---|---:|---:|"]
        linhas += [f"| [{MESES[m - 1]}]({pasta_mes(base, date(a, m, 1)).name}/_resumo.md) | {n} | {brl(t)} |"
                   for m, (t, n) in sorted(meses.items())]
        (base / str(a) / f"_resumo_{a}.md").write_text(
            f"---\n{MARCA}\ntipo: resumo_ano\nano: {a}\n---\n\n# Recebimentos de {a}\n\n"
            f"**Total:** {brl(sum(t for t, _ in meses.values()))} em {sum(n for _, n in meses.values())} recebimentos.\n\n"
            + "\n".join(linhas) + "\n", encoding="utf-8")

    total = sum(float(fm["valor"]) for _, fm in docs)
    (base / "README.md").write_text(
        f"---\n{MARCA}\ntipo: indice\n---\n\n# Base de recebimentos · Distribuidora Aurora\n\n"
        f"Atualizada em {datetime.now():%d/%m/%Y %H:%M}. **{len(docs)} recebimentos, {brl(total)}.**\n\n"
        "## Como está organizada\n\n"
        "- `<ano>/_resumo_<ano>.md` — totais do ano por mês (comece por aqui)\n"
        "- `<ano>/<MM-mes>/_resumo.md` — totais do mês por cliente, forma, região e categoria\n"
        "- `<ano>/<MM-mes>/<arquivo>.md` — um comprovante: dados conferidos + trecho do texto lido\n"
        "- `_pendencias/` — ilegíveis, duplicados e pagadores fora do cadastro\n\n"
        "## Anos\n\n" + "\n".join(f"- [{a}]({a}/_resumo_{a}.md)" for a in sorted(anos)) + "\n",
        encoding="utf-8")
    return {"recebimentos": len(docs), "total": round(total, 2), "meses": sum(len(m) for m in anos.values())}


# ------------------------------------------------------------------ organização
def organizar(cam: Caminhos) -> dict:
    """Garante a estrutura <ano>/<MM-mes>/: move .md de comprovante que estiverem fora do lugar
    (pela data do frontmatter), remove pastas vazias e regenera os resumos."""
    base = raiz(cam)
    movidos, sem_data = [], []
    for p in list(base.rglob("*.md")):
        if p.name.startswith("_") or p.name == "README.md" or "_pendencias" in p.parts:
            continue
        fm = _frontmatter(p.read_text(encoding="utf-8", errors="ignore"))
        try:
            d = date.fromisoformat(fm.get("data", ""))
        except ValueError:
            sem_data.append(p.relative_to(base).as_posix())
            continue
        destino_dir = pasta_mes(base, d)
        if p.parent != destino_dir:
            destino_dir.mkdir(parents=True, exist_ok=True)
            alvo = destino_dir / p.name
            n = 2
            while alvo.exists():
                alvo = destino_dir / f"{p.stem}_{n}{p.suffix}"
                n += 1
            shutil.move(str(p), str(alvo))
            movidos.append(f"{p.relative_to(base).as_posix()} -> {alvo.relative_to(base).as_posix()}")
    # pastas vazias e pastas com nome fora do padrão que ficaram vazias
    for d in sorted((x for x in base.rglob("*") if x.is_dir()), key=lambda x: -len(x.parts)):
        if not any(d.iterdir()):
            d.rmdir()
    fora_padrao = [d.relative_to(base).as_posix() for d in base.iterdir() if d.is_dir()
                   and d.name != "_pendencias" and not PADRAO_PASTA.match(d.name)]
    fora_padrao += [m.relative_to(base).as_posix() for a in base.iterdir() if a.is_dir() and PADRAO_PASTA.match(a.name)
                    for m in a.iterdir() if m.is_dir() and not PADRAO_MES.match(m.name)]
    r = indices(cam)
    r.update(movidos=movidos, sem_data=sem_data, pastas_fora_do_padrao=fora_padrao)
    return r
