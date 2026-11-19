"""Uso (a partir da pasta 'Projeto 1'):

  python -m aurora lancar                 etapa 1: dados/leituras.csv -> aba Recebimentos
  python -m aurora renomear [--aplicar]   etapa 2: renomeia Comprovantes (simula por padrão)
  python -m aurora desfazer-renomeacao    volta os nomes originais pelo log
  python -m aurora cadastro               etapa 3: Região/UF e Categoria
  python -m aurora dashboard              etapa 4: aba Dashboard
  python -m aurora painel                 etapa 5: Painel_Aurora.html
  python -m aurora tudo [--aplicar]       etapas 1 a 5 em sequência
  python -m aurora semana                 etapa 6: rotina de segunda-feira

  --base PASTA   roda em outra pasta (ex.: --base teste)
  python -m aurora --base teste mock     cria a pasta de teste com dados fictícios
"""
import argparse
import sys
from pathlib import Path

from .config import RAIZ_PROJETO, Caminhos


def main(argv=None):
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    ap = argparse.ArgumentParser(prog="aurora", description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("comando", choices=["mock", "lancar", "renomear", "desfazer-renomeacao",
                                        "cadastro", "markdown", "organizar", "dashboard", "painel",
                                        "tudo", "semana", "servidor", "funcoes"])
    ap.add_argument("--semear", action="store_true", help="funcoes: (re)cria as funções de negócio padrão")
    ap.add_argument("--executar", metavar="NOME", help="funcoes: executa uma função e mostra o resultado")
    ap.add_argument("--porta", type=int, default=8765, help="porta do servidor local (comando servidor)")
    ap.add_argument("--nao-abrir", action="store_true", help="servidor: não abre o navegador")
    ap.add_argument("--base", default=str(RAIZ_PROJETO))
    ap.add_argument("--aplicar", action="store_true", help="renomear de verdade (etapa 2)")
    a = ap.parse_args(argv)
    base = Path(a.base)
    if not base.is_absolute():
        base = (RAIZ_PROJETO / base).resolve()
    cam = Caminhos(base)

    from . import etapas_dados as E
    if a.comando == "mock":
        if base == RAIZ_PROJETO or not base.name.lower().startswith(("teste", "demo")):
            sys.exit("Por segurança, 'mock' só roda numa pasta cujo nome começa com 'teste' ou 'demo' (use --base demo).")
        from . import mock
        mock.gerar(cam)
    elif a.comando == "lancar":
        E.etapa1_lancar(cam)
    elif a.comando == "renomear":
        E.etapa2_renomear(cam, a.aplicar)
    elif a.comando == "desfazer-renomeacao":
        E.desfazer_renomeacao(cam)
    elif a.comando == "cadastro":
        E.etapa3_cadastro(cam)
    elif a.comando == "markdown":
        _markdown(cam)
    elif a.comando == "organizar":
        from . import base_md
        r = base_md.organizar(cam)
        print(f"Base organizada: {len(r['movidos'])} arquivo(s) movido(s); {r['recebimentos']} recebimentos em {r['meses']} meses.")
        for m in r["movidos"]:
            print("  ", m)
    elif a.comando == "funcoes":
        from . import funcoes, funcoes_padrao
        if a.semear:
            for l in funcoes_padrao.semear(cam):
                print(l)
        if a.executar:
            print(funcoes.executar(cam, a.executar, {}))
        if not (a.semear or a.executar):
            funcoes.gerar_indice()
            for f in funcoes.listar():
                print(f"{f['nome']:24} [{f.get('categoria')}] {f.get('descricao')}")
    elif a.comando == "servidor":
        from . import servidor
        servidor.rodar(cam, a.porta, abrir=not a.nao_abrir)
    elif a.comando == "dashboard":
        from . import dashboard
        dashboard.gerar(cam)
    elif a.comando == "painel":
        from . import painel
        painel.gerar(cam)
    elif a.comando == "tudo":
        from . import dashboard, painel
        E.etapa1_lancar(cam); print()
        E.etapa2_renomear(cam, a.aplicar); print()
        E.etapa3_cadastro(cam); print()
        _markdown(cam); print()
        dashboard.gerar(cam); print()
        painel.gerar(cam)
    elif a.comando == "semana":
        from . import rotina
        sys.exit(rotina.rodar(cam))


def _markdown(cam):
    from . import base_md
    r = base_md.gerar(cam)
    p = r["pendencias"]
    print("=== CAMADA MARKDOWN ===")
    from .etapas_dados import brl
    print(f"base_md/: {r['comprovantes']} comprovantes em {r['meses']} meses (ano/mês), total {brl(r['total'])}")
    print(f"Pendências: {p.get('ilegiveis', 0)} ilegíveis, {p.get('duplicados', 0)} duplicados, "
          f"{p.get('fora', 0)} fora do cadastro (em base_md/_pendencias/)")


if __name__ == "__main__":
    main()
