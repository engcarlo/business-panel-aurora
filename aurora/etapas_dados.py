"""Etapas 1 (lançar), 2 (renomear) e 3 (cadastro)."""
import csv
import re
from collections import defaultdict
from datetime import datetime

from . import leituras as L
from . import nomes, planilha
from .config import ABA_REC, LINHA_INI, Caminhos

PADRAO_NOME = re.compile(r"^\d{4}-\d{2}-\d{2}_.+_\d+,\d{2}(_copia\d*)?\.[^.]+$")
PREFIXO_ILEG = "ILEGIVEL_"


def brl(v) -> str:
    return "R$ " + f"{float(v):,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")


def _carregar(cam: Caminhos, wb):
    cad = list(planilha.cadastro(wb))
    ap = nomes.carregar_apelidos(cam.apelidos)
    return L.carregar(cam.leituras, cam.comprovantes, cad, ap)


# ---------------------------------------------------------------- etapa 1
def etapa1_lancar(cam: Caminhos):
    wb = planilha.abrir(cam.planilha)
    lts = _carregar(cam, wb)
    ok = sorted((x for x in lts if x.lancavel), key=lambda x: (x.data, x.cliente.lower()))
    ws = wb[ABA_REC]
    planilha.limpar_recebimentos(ws)
    for i, lt in enumerate(ok):
        planilha.escrever_linha(ws, LINHA_INI + i, lt.data, lt.cliente, lt.valor, lt.forma)
    planilha.ajustar_larguras(ws)
    wb.save(cam.planilha)

    ileg = [x for x in lts if x.status == "ilegivel"]
    erro = [x for x in lts if x.status == "ok" and x.erros]
    dup = [x for x in lts if x.duplicado_de]
    no_csv = {x.arquivo for x in lts}
    sem_leitura = sorted(p.name for p in cam.comprovantes.iterdir()
                         if p.is_file() and p.name not in no_csv) if cam.comprovantes.exists() else []
    faltando = sorted(x.arquivo for x in lts if not (cam.comprovantes / x.arquivo).exists())

    print("=== ETAPA 1 · Lançamento ===")
    print(f"Lançamentos: {len(ok)}   Total recebido: {brl(sum(x.valor for x in ok))}")
    print(f"Arquivos lidos: {len(lts)}  (ilegíveis {len(ileg)}, duplicados {len(dup)}, com erro {len(erro)})")
    if ileg:
        print("\nIlegíveis (não lançados):")
        for x in ileg:
            print(f"  - {x.arquivo}: {x.obs or 'sem motivo informado'}")
    if dup:
        print("\nDuplicados (lançados uma vez só):")
        for x in dup:
            print(f"  - {x.arquivo}  =  {x.duplicado_de}")
    if erro:
        print("\nLinhas do CSV com problema (não lançadas, confira):")
        for x in erro:
            print(f"  - linha {x.linha} {x.arquivo}: {'; '.join(x.erros)}")
    if sem_leitura:
        print(f"\nAtenção: {len(sem_leitura)} arquivo(s) na pasta sem leitura no CSV: {', '.join(sem_leitura[:10])}"
              + (" ..." if len(sem_leitura) > 10 else ""))
    if faltando:
        print(f"\nAtenção: {len(faltando)} arquivo(s) do CSV não estão na pasta: {', '.join(faltando[:10])}")
    return ok


# ---------------------------------------------------------------- etapa 2
def _limpo(s: str) -> str:
    s = re.sub(r'[<>:"/\\|?*\x00-\x1f]', "-", s)
    return re.sub(r"\s+", " ", s).strip(" .")


def ja_organizado(nome: str) -> bool:
    return nome.startswith(PREFIXO_ILEG) or bool(PADRAO_NOME.match(nome))


def etapa2_renomear(cam: Caminhos, aplicar=False):
    wb = planilha.abrir(cam.planilha)
    lts = _carregar(cam, wb)
    planos, duvidas, copias = [], [], defaultdict(int)
    destinos = set()
    for lt in sorted(lts, key=lambda x: x.arquivo_original.lower()):
        atual = cam.comprovantes / lt.arquivo
        if not atual.exists():
            duvidas.append((lt.arquivo, "arquivo não está na pasta"))
            continue
        if lt.status == "ilegivel":
            novo = lt.arquivo if lt.arquivo.startswith(PREFIXO_ILEG) else PREFIXO_ILEG + lt.arquivo
        elif lt.erros:
            duvidas.append((lt.arquivo, "; ".join(lt.erros)))
            continue
        else:
            valor = f"{lt.valor:.2f}".replace(".", ",")
            base = f"{lt.data.isoformat()}_{_limpo(lt.cliente)}_{valor}"
            if lt.duplicado_de:
                copias[base] += 1
                base += "_copia" + (str(copias[base]) if copias[base] > 1 else "")
            novo = base + atual.suffix
        if novo == lt.arquivo:
            continue
        alvo = cam.comprovantes / novo
        if novo.lower() in destinos or (alvo.exists() and alvo.resolve() != atual.resolve()):
            duvidas.append((lt.arquivo, f"já existe um arquivo chamado '{novo}'"))
            continue
        destinos.add(novo.lower())
        planos.append((lt, novo))

    print(f"=== ETAPA 2 · Renomear ({'APLICANDO' if aplicar else 'simulação — nada foi alterado'}) ===")
    for lt, novo in planos[:15]:
        print(f"  {lt.arquivo}  ->  {novo}")
    if len(planos) > 15:
        print(f"  ... e mais {len(planos) - 15}")
    print(f"Total a renomear: {len(planos)}")
    if duvidas:
        print("\nNão renomeados (dúvida):")
        for a, m in duvidas:
            print(f"  - {a}: {m}")
    if not aplicar:
        print("\nPara aplicar: python -m aurora renomear --aplicar")
        return planos

    novo_log = not cam.log_renomeacao.exists()
    with cam.log_renomeacao.open("a", encoding="utf-8-sig", newline="") as f:
        w = csv.writer(f, delimiter=";")
        if novo_log:
            w.writerow(["quando", "de", "para"])
        quando = datetime.now().isoformat(timespec="seconds")
        for lt, novo in planos:
            (cam.comprovantes / lt.arquivo).rename(cam.comprovantes / novo)
            w.writerow([quando, lt.arquivo, novo])
            lt.arquivo = novo
    L.salvar(cam.leituras, lts)
    print(f"\n{len(planos)} arquivo(s) renomeados. Log: {cam.log_renomeacao}")
    print("Para desfazer: python -m aurora desfazer-renomeacao")
    return planos


def desfazer_renomeacao(cam: Caminhos):
    if not cam.log_renomeacao.exists():
        print("Nada a desfazer.")
        return
    with cam.log_renomeacao.open(encoding="utf-8-sig", newline="") as f:
        reg = list(csv.DictReader(f, delimiter=";"))
    mapa = {}
    for r in reversed(reg):
        de, para = cam.comprovantes / r["para"], cam.comprovantes / r["de"]
        if de.exists() and not para.exists():
            de.rename(para)
            mapa[r["para"]] = r["de"]
    if cam.leituras.exists():
        wb = planilha.abrir(cam.planilha)
        lts = _carregar(cam, wb)
        for lt in lts:
            lt.arquivo = mapa.get(lt.arquivo, lt.arquivo)
        L.salvar(cam.leituras, lts)
    cam.log_renomeacao.rename(cam.log_renomeacao.with_suffix(".desfeito.csv"))
    print(f"{len(mapa)} arquivo(s) voltaram ao nome original.")


# ---------------------------------------------------------------- etapa 3
def etapa3_cadastro(cam: Caminhos):
    wb = planilha.abrir(cam.planilha)
    cad = planilha.cadastro(wb)
    ap = nomes.carregar_apelidos(cam.apelidos)
    ws = wb[ABA_REC]
    padron, fora = defaultdict(list), defaultdict(list)
    for ln in planilha.linhas(wb):
        c = nomes.casar(ln.cliente, list(cad), ap)
        if c.cliente:
            reg, cat = cad[c.cliente]
            if c.status != "exato":
                padron[(ln.cliente, c.cliente, c.motivo)].append(ln.n)
                ws.cell(ln.n, 2, c.cliente)
            ws.cell(ln.n, 5, reg)
            ws.cell(ln.n, 6, cat)
            planilha.marcar(ws, ln.n, None)
        else:
            ws.cell(ln.n, 5, None)
            ws.cell(ln.n, 6, None)
            nota = "Pagador não encontrado no cadastro"
            if c.status == "revisar":
                nota += f" (parecido com '{c.sugestao}' — confirme em dados/apelidos.csv)"
            planilha.marcar(ws, ln.n, nota)
            fora[(ln.cliente, c.sugestao if c.status == "revisar" else None)].append((ln.n, ln.valor))
    planilha.ajustar_larguras(ws)
    wb.save(cam.planilha)

    print("=== ETAPA 3 · Cadastro ===")
    if padron:
        print("Nomes padronizados pelo cadastro:")
        for (de, para, mot), ns in sorted(padron.items()):
            print(f"  - '{de}' -> '{para}'  [{len(ns)} linha(s): {', '.join(map(str, ns))}]  motivo: {mot}")
    if fora:
        total = sum(v for lst in fora.values() for _, v in lst)
        print(f"\nPagadores fora do cadastro (linhas marcadas em amarelo, Região/Categoria em branco) — {brl(total)}:")
        for (nome, sug), lst in sorted(fora.items()):
            extra = f"  ⚠ parecido com '{sug}', confirme" if sug else ""
            print(f"  - '{nome}': {len(lst)} linha(s), {brl(sum(v for _, v in lst))}{extra}")
    if not padron and not fora:
        print("Todos os nomes bateram exatamente com o cadastro.")
