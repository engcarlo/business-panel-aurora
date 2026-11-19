"""Etapa 5 — Painel_Aurora.html: arquivo único, dados embutidos.
O Python calcula os dados e os Insights (nenhum número digitado à mão);
o visual vem de aurora/painel_template.html, que recebe o JSON no marcador."""
import json
from collections import defaultdict
from pathlib import Path

from . import planilha
from .config import MESES, NAO_IDENT, Caminhos
from .etapas_dados import brl as _brl

TEMPLATE = Path(__file__).with_name("painel_template.html")
MARCADOR = "/*__DADOS_AURORA__*/null"


def brl(v):
    """R$ com espaço não separável: o valor nunca quebra de linha no meio."""
    return _brl(v).replace(" ", " ")


def _pct(x):
    casas = 1 if 0 < abs(x) < 0.1 else 0          # evita "−0%" e "0%" para variações pequenas
    return f"{x * 100:.{casas}f}%".replace("-", "−").replace(".", ",")


def _soma(rows, chave):
    d = defaultdict(float)
    for r in rows:
        d[chave(r)] += r.valor
    return dict(sorted(d.items(), key=lambda kv: -kv[1]))


def insights(rows) -> list[dict]:
    total = sum(r.valor for r in rows)
    ano = min(r.data for r in rows).year
    meses = sorted({r.data.month for r in rows})
    por_mes = {m: sum(r.valor for r in rows if r.data.month == m) for m in meses}
    out = []

    # 1. variação mês a mês e o que explica
    melhor = max(por_mes, key=por_mes.get)
    pior = min(por_mes, key=por_mes.get)
    deltas = [(m, por_mes[m] - por_mes[m - 1]) for m in meses[1:] if m - 1 in por_mes]
    salto = max(deltas, key=lambda x: x[1])
    queda = min(deltas, key=lambda x: x[1])

    def motor(m):
        a = _soma([r for r in rows if r.data.month == m - 1], lambda r: r.cliente)
        b = _soma([r for r in rows if r.data.month == m], lambda r: r.cliente)
        var = sorted(((c, b.get(c, 0) - a.get(c, 0)) for c in set(a) | set(b)), key=lambda x: -abs(x[1]))
        return var[0]

    c_s, v_s = motor(salto[0])
    txt = (f"{MESES[melhor - 1]} foi o pico ({brl(por_mes[melhor])}) e {MESES[pior - 1].lower()} o vale "
           f"({brl(por_mes[pior])}), uma amplitude de {_pct(por_mes[melhor] / por_mes[pior] - 1)}. "
           f"O maior salto veio em {MESES[salto[0] - 1].lower()} (+{brl(salto[1])}), puxado por {c_s} "
           f"({'+' if v_s >= 0 else '−'}{brl(abs(v_s))} sobre o mês anterior).")
    if queda[1] < 0:
        c_q, v_q = motor(queda[0])
        txt += (f" A maior queda foi em {MESES[queda[0] - 1].lower()} (−{brl(-queda[1])}), "
                f"com {c_q} respondendo por {'−' if v_q < 0 else '+'}{brl(abs(v_q))}.")
    out.append({"tema": "Caixa mês a mês", "destaque": MESES[melhor - 1], "texto": txt})

    # 2. regiões: quem puxou, quem perdeu força (1º tri x 2º tri do período)
    meio = meses[len(meses) // 2]
    reg = _soma([r for r in rows if r.regiao], lambda r: r.regiao)
    lider = next(iter(reg))
    tend = {}
    for g in reg:
        a = sum(r.valor for r in rows if r.regiao == g and r.data.month < meio)
        b = sum(r.valor for r in rows if r.regiao == g and r.data.month >= meio)
        tend[g] = (b / a - 1) if a else 0
    fraca = min(tend, key=tend.get)
    forte = max(tend, key=tend.get)
    out.append({"tema": "Regiões", "destaque": lider,
                "texto": f"{lider} puxou o semestre com {_pct(reg[lider] / total)} do caixa ({brl(reg[lider])}). "
                         f"Comparando a 2ª metade com a 1ª, {forte} foi a que mais acelerou "
                         f"({'+' if tend[forte] >= 0 else ''}{_pct(tend[forte])}) e {fraca} a que "
                         f"{'mais perdeu força' if tend[fraca] < 0 else 'menos cresceu'} "
                         f"({_pct(tend[fraca])})."})

    # 3. categoria que sustenta o caixa
    cat = _soma([r for r in rows if r.categoria], lambda r: r.categoria)
    c1, c2 = list(cat)[:2]
    out.append({"tema": "Categorias", "destaque": c1,
                "texto": f"{c1} e {c2} sustentam o caixa: juntas somam {_pct((cat[c1] + cat[c2]) / total)} "
                         f"do recebido ({brl(cat[c1] + cat[c2])}). {list(cat)[-1]} é a menor fatia, "
                         f"com {_pct(cat[list(cat)[-1]] / total)}."})

    # 4. concentração
    cli = _soma(rows, lambda r: r.cliente)
    top = list(cli.items())
    top3 = sum(v for _, v in top[:3])
    out.append({"tema": "Concentração", "destaque": _pct(top3 / total),
                "texto": f"Os 3 maiores clientes concentram {_pct(top3 / total)} do caixa; só {top[0][0]} responde por "
                         f"{_pct(top[0][1] / total)}. Perder um deles muda o semestre."})

    # 5. pagadores fora do cadastro
    fora = [r for r in rows if not r.regiao]
    v_fora = sum(r.valor for r in fora)
    nomes_fora = sorted({r.cliente for r in fora})
    out.append({"tema": "Fora do cadastro", "destaque": brl(v_fora),
                "texto": (f"{len(fora)} recebimentos ({_pct(v_fora / total)} do caixa) vieram de {len(nomes_fora)} "
                          f"pagadores sem cadastro: {', '.join(nomes_fora)}. O dinheiro entrou, mas não tem região "
                          f"nem categoria." if fora else "Todos os pagadores do período estão no cadastro.")})

    # 6. recomendações (regras sobre os próprios números)
    rec = []
    if fora:
        rec.append(f"Cadastrar ou identificar os {len(nomes_fora)} pagadores avulsos ({brl(v_fora)}) antes do próximo fechamento.")
    if top3 / total > 0.4:
        rec.append(f"Reduzir dependência: {_pct(top3 / total)} do caixa está em 3 clientes; prospectar contas médias em {forte}.")
    if tend[fraca] < 0:
        rec.append(f"Investigar a desaceleração em {fraca} ({_pct(tend[fraca])}) com a equipe comercial da região.")
    rec.append(f"Usar {MESES[melhor - 1].lower()} como referência de capacidade: entender o que se repetiu e o que foi pontual.")
    out.append({"tema": "Recomendações", "destaque": f"{len(rec)} ações", "texto": "", "itens": rec})
    return out


def dados(cam: Caminhos) -> dict:
    wb = planilha.abrir(cam.planilha)
    rows = planilha.linhas(wb)
    if not rows:
        raise SystemExit("Aba Recebimentos vazia: rode as etapas anteriores.")
    cad = planilha.cadastro(wb)
    ano = min(r.data for r in rows).year
    return {
        "empresa": "Distribuidora Aurora Ltda",
        "periodo": f"{MESES[min(r.data for r in rows).month - 1]} – {MESES[max(r.data for r in rows).month - 1]} {ano}",
        "meses": [MESES[m - 1] for m in range(min(r.data.month for r in rows), max(r.data.month for r in rows) + 1)],
        "regioes": sorted({v[0].split("/")[0] for v in cad.values()}),
        "categorias": sorted({v[1] for v in cad.values()}),
        "naoIdent": NAO_IDENT,
        "recebimentos": [{"d": r.data.isoformat(), "c": r.cliente, "v": round(r.valor, 2), "f": r.forma,
                          "r": r.regiao or NAO_IDENT, "uf": (r.regiao_uf or "").split("/")[-1] or None,
                          "k": r.categoria or NAO_IDENT} for r in rows],
        "insights": insights(rows),
        "comprovantes": comprovantes(cam, cad),
    }


def comprovantes(cam: Caminhos, cad: dict) -> list[dict]:
    """Um item por arquivo da pasta Comprovantes, com a situação de cada um,
    para a aba 'Comprovantes' do painel (link relativo ao Painel_Aurora.html)."""
    from urllib.parse import quote

    from . import leituras as L, nomes

    if not cam.leituras.exists():
        return []
    ap = nomes.carregar_apelidos(cam.apelidos)
    lts = L.carregar(cam.leituras, cam.comprovantes, list(cad), ap)
    rel = cam.comprovantes.relative_to(cam.painel.parent).as_posix()
    out = []
    for lt in sorted(lts, key=lambda x: (x.data or __import__("datetime").date.max, x.arquivo.lower())):
        cas = nomes.casar(lt.cliente, list(cad), ap) if lt.cliente else None
        if lt.duplicado_de:
            sit = "duplicado"
        elif lt.status == "ilegivel" or lt.erros:
            sit = "ilegivel"
        elif cas and cas.cliente:
            sit = "lancado"
        else:
            sit = "fora"           # lançado, mas pagador fora do cadastro
        reg = cad.get(cas.cliente) if cas and cas.cliente else None
        out.append({
            "a": lt.arquivo, "o": lt.arquivo_original,
            "u": f"{rel}/{quote(lt.arquivo)}",
            "d": lt.data.isoformat() if lt.data else None,
            "c": (cas.cliente if cas and cas.cliente else lt.cliente) or None,
            "cl": lt.cliente or None,
            "v": float(lt.valor) if lt.valor is not None else None,
            "f": lt.forma or None,
            "s": sit,
            "r": reg[0].split("/")[0] if reg else None, "k": reg[1] if reg else None,
            "dup": lt.duplicado_de,
            "obs": "; ".join(filter(None, [lt.obs, *lt.erros])) or None,
        })
    return out


def gerar(cam: Caminhos):
    d = dados(cam)
    js = json.dumps(d, ensure_ascii=False, separators=(",", ":"))
    print("=== ETAPA 5 · Painel ===")
    if not TEMPLATE.exists():
        destino = cam.dados / "painel_dados.json"
        destino.write_text(json.dumps(d, ensure_ascii=False, indent=1), encoding="utf-8")
        print(f"Template visual ainda não criado; dados salvos em {destino}")
        return
    html = TEMPLATE.read_text(encoding="utf-8")
    assert MARCADOR in html, "template sem marcador de dados"
    cam.painel.write_text(html.replace(MARCADOR, js.replace("</", "<\\/")), encoding="utf-8")
    print(f"Painel gerado: {cam.painel}  ({len(d['recebimentos'])} recebimentos)")
