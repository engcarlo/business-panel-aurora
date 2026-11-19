"""Biblioteca de funções de negócio da skill (skill_aurora/funcoes/).

Cada função é uma PÁGINA .md: frontmatter (nome, categoria, descrição, parâmetros) +
explicação + fórmula + um bloco ```python com `def calcular(dados, **p)`.
O índice (_indice.md) é gerado a partir das páginas.

Execução segura: o código roda sem `import`, sem acesso a arquivos/rede/atributos internos,
só com funções puras e os auxiliares abaixo. Toda função nova é validada (análise do código +
execução de teste com os dados reais) ANTES de ser salva.

Contrato da função:
    def calcular(dados, **p):
        # dados: lista de dicts {data (date), ano, mes, cliente, valor (float), forma,
        #                        regiao, uf, categoria, situacao}
        return {"resumo": "texto", "tabela": [ {coluna: valor, ...}, ... ]}   # ou só uma str
"""
from __future__ import annotations

import ast
import re
import statistics
import threading
from collections import defaultdict
from datetime import date, datetime
from pathlib import Path

from . import base_md
from .config import MESES, RAIZ_PROJETO, Caminhos

PASTA = RAIZ_PROJETO / "skill_aurora" / "funcoes"
NOME_OK = re.compile(r"^[a-z][a-z0-9_]{2,40}$")
CATEGORIAS = ["receita", "clientes", "concentracao", "tendencia", "pagamentos", "previsao", "qualidade", "outros"]
PROIBIDOS = {"open", "exec", "eval", "compile", "__import__", "globals", "locals", "vars", "getattr",
             "setattr", "delattr", "input", "breakpoint", "exit", "quit", "help", "memoryview", "type", "object"}
TEMPO_MAX = 5.0


# ------------------------------------------------------------------ auxiliares disponíveis às funções
def _brl(v):
    return base_md.brl(v)


def _pct(x, casas=1):
    return f"{x * 100:.{casas}f}%".replace(".", ",")


def _agrupar(dados, chave):
    g = defaultdict(list)
    for d in dados:
        g[chave(d) if callable(chave) else d.get(chave)].append(d)
    return dict(g)


def _soma(dados):
    return round(sum(d["valor"] for d in dados), 2)


AUXILIARES = {
    "brl": _brl, "pct": _pct, "agrupar": _agrupar, "soma": _soma,
    "media": statistics.fmean, "mediana": statistics.median,
    "desvio": lambda xs: statistics.pstdev(xs) if len(xs) > 1 else 0.0,
    "date": date, "MESES": MESES,
    "data_br": lambda d: f"{d.day:02d}/{d.month:02d}/{d.year}",   # use no lugar de strftime (bloqueado)
    "num": lambda x, casas=1: f"{x:,.{casas}f}".replace(",", "X").replace(".", ",").replace("X", "."),
}
BUILTINS_SEGUROS = {n: __builtins__[n] if isinstance(__builtins__, dict) else getattr(__builtins__, n) for n in (
    "len", "sum", "min", "max", "sorted", "round", "abs", "enumerate", "zip", "dict", "list", "set",
    "tuple", "str", "int", "float", "bool", "any", "all", "map", "filter", "isinstance", "reversed")}


def _range_limitado(*a):
    r = range(*a)
    if len(r) > 1_000_000:
        raise ValueError("range acima de 1.000.000 itens não é permitido")
    return r


BUILTINS_SEGUROS["range"] = _range_limitado


# ------------------------------------------------------------------ dados
def carregar_dados(cam: Caminhos) -> list[dict]:
    """Recebimentos lançados, lidos da base_md (mesma fonte do chat)."""
    out = []
    for _, fm in base_md._ler_comprovantes(base_md.raiz(cam)):
        d = date.fromisoformat(fm["data"])
        ru = fm.get("regiao_uf") or ""
        out.append({"data": d, "ano": d.year, "mes": d.month, "cliente": fm["cliente"],
                    "valor": float(fm["valor"]), "forma": fm["forma"],
                    "regiao": ru.split("/")[0] or "Não identificado", "uf": ru.split("/")[-1] if ru else "",
                    "categoria": fm.get("categoria") or "Não identificado", "situacao": fm["situacao"]})
    return sorted(out, key=lambda x: (x["data"], x["cliente"]))


def filtrar(dados, ano=0, mes_inicio=0, mes_fim=0, cliente="", regiao="", categoria="", forma=""):
    k = lambda s: base_md._sem_acento(str(s or "")).lower()
    return [d for d in dados
            if (not ano or d["ano"] == ano) and (not mes_inicio or d["mes"] >= mes_inicio)
            and (not mes_fim or d["mes"] <= mes_fim) and (not cliente or k(cliente) in k(d["cliente"]))
            and (not regiao or k(regiao) in k(d["regiao"] + "/" + d["uf"]))
            and (not categoria or k(categoria) in k(d["categoria"])) and (not forma or k(forma) == k(d["forma"]))]


# ------------------------------------------------------------------ páginas
def _frontmatter(txt):
    m = re.match(r"^---\n(.*?)\n---", txt, re.S)
    fm = {}
    if m:
        for l in m.group(1).splitlines():
            if ":" in l:
                k, v = l.split(":", 1)
                fm[k.strip()] = v.strip().strip('"')
    return fm


def _codigo(txt):
    m = re.search(r"```python\n(.*?)```", txt, re.S)
    return m.group(1) if m else ""


def listar() -> list[dict]:
    out = []
    for p in sorted(PASTA.glob("*.md")):
        if p.name.startswith("_"):
            continue
        fm = _frontmatter(p.read_text(encoding="utf-8"))
        if fm.get("nome"):
            out.append({**fm, "arquivo": p.name})
    return out


def pagina(nome: str) -> str | None:
    if not NOME_OK.match(nome or ""):
        return None
    p = PASTA / f"{nome}.md"
    return p.read_text(encoding="utf-8") if p.exists() else None


def gerar_indice() -> Path:
    fs = listar()
    por_cat = defaultdict(list)
    for f in fs:
        por_cat[f.get("categoria", "outros")].append(f)
    linhas = ["---", "tipo: indice_funcoes", f"atualizado: {datetime.now():%Y-%m-%d %H:%M}", "---", "",
              "# Índice de funções de negócio · Aurora", "",
              f"{len(fs)} funções. Para usar: `executar_funcao(nome, parametros)`. "
              "Para ver fórmula e parâmetros: `ler_funcao(nome)`.", "",
              "Filtros aceitos por TODAS as funções (dentro de `parametros`): "
              "`ano`, `mes_inicio`, `mes_fim`, `cliente`, `regiao`, `categoria`, `forma`.", ""]
    for cat in CATEGORIAS:
        if not por_cat.get(cat):
            continue
        linhas += [f"## {cat.capitalize()}", "", "| Função | O que faz | Parâmetros próprios |", "|---|---|---|"]
        cel = lambda s: str(s or "—").replace("|", "\\|")
        linhas += [f"| [`{f['nome']}`]({f['arquivo']}) | {cel(f.get('descricao'))} | {cel(f.get('parametros'))} |"
                   for f in sorted(por_cat[cat], key=lambda x: x["nome"])]
        linhas.append("")
    alvo = PASTA / "_indice.md"
    alvo.write_text("\n".join(linhas), encoding="utf-8")
    return alvo


# ------------------------------------------------------------------ validação e execução
def validar_codigo(codigo: str) -> list[str]:
    erros = []
    try:
        arvore = ast.parse(codigo)
    except SyntaxError as e:
        return [f"erro de sintaxe na linha {e.lineno}: {e.msg}"]
    defs = [n for n in arvore.body if isinstance(n, ast.FunctionDef) and n.name == "calcular"]
    if not defs:
        erros.append("o código precisa definir `def calcular(dados, **p):`")
    for n in ast.walk(arvore):
        if isinstance(n, (ast.Import, ast.ImportFrom)):
            erros.append("`import` não é permitido (use os auxiliares disponíveis)")
        elif isinstance(n, (ast.Global, ast.Nonlocal)):
            erros.append("`global`/`nonlocal` não são permitidos")
        elif isinstance(n, ast.While):
            erros.append("`while` não é permitido (use `for` sobre os dados)")
        elif isinstance(n, ast.Attribute) and n.attr.startswith("_"):
            erros.append(f"acesso a atributo interno `{n.attr}` não é permitido")
        elif isinstance(n, ast.Attribute) and n.attr in ("format", "format_map"):
            erros.append("`.format()` não é permitido (use f-strings ou os auxiliares brl/pct)")
        elif isinstance(n, ast.Name) and (n.id in PROIBIDOS or n.id.startswith("__")):
            erros.append(f"`{n.id}` não é permitido")
    return sorted(set(erros))


def _executar_codigo(codigo: str, dados: list[dict], params: dict):
    ambiente = {"__builtins__": BUILTINS_SEGUROS, **AUXILIARES}
    exec(compile(codigo, "<funcao>", "exec"), ambiente)   # noqa: S102 — código já validado por AST
    resultado, erro = {}, {}

    def alvo():
        try:
            resultado["v"] = ambiente["calcular"]([dict(d) for d in dados], **params)
        except Exception as e:  # erro da função vira mensagem
            erro["e"] = f"{type(e).__name__}: {e}"

    t = threading.Thread(target=alvo, daemon=True)
    t.start()
    t.join(TEMPO_MAX)
    if t.is_alive():
        raise TimeoutError(f"a função passou de {TEMPO_MAX:.0f}s")
    if erro:
        raise RuntimeError(erro["e"])
    return resultado.get("v")


def formatar(res) -> str:
    if isinstance(res, str):
        return res
    if not isinstance(res, dict):
        return str(res)
    partes = [str(res["resumo"])] if res.get("resumo") else []
    tab = res.get("tabela") or []
    if tab and isinstance(tab, list) and isinstance(tab[0], dict):
        cols = list(tab[0].keys())
        partes += ["", "| " + " | ".join(cols) + " |", "|" + "---|" * len(cols)]
        partes += ["| " + " | ".join(str(r.get(c, "")) for c in cols) + " |" for r in tab[:200]]
        if len(tab) > 200:
            partes.append(f"(+{len(tab) - 200} linhas)")
    return "\n".join(partes) or "(sem resultado)"


FILTROS = ("ano", "mes_inicio", "mes_fim", "cliente", "regiao", "categoria", "forma")


def executar(cam: Caminhos, nome: str, parametros: dict | None = None) -> str:
    txt = pagina(nome)
    if txt is None:
        return f"Função `{nome}` não existe. Consulte o índice com listar_funcoes."
    codigo = _codigo(txt)
    erros = validar_codigo(codigo)
    if erros:
        return "Função com código inválido: " + "; ".join(erros)
    parametros = dict(parametros or {})
    filtros = {k: parametros.pop(k) for k in FILTROS if k in parametros}
    dados = filtrar(carregar_dados(cam), **filtros)
    if not dados:
        return "Nenhum recebimento com esses filtros."
    try:
        return formatar(_executar_codigo(codigo, dados, parametros))
    except (TimeoutError, RuntimeError) as e:
        return f"Erro ao executar `{nome}`: {e}"


def criar(cam: Caminhos, nome: str, categoria: str, descricao: str, parametros: str,
          explicacao: str, formula: str, codigo: str, exemplo_parametros: dict | None = None,
          sobrescrever: bool = False, autor: str = "chat") -> str:
    """Valida e salva uma nova página de função; atualiza o índice."""
    if not NOME_OK.match(nome or ""):
        return "Nome inválido: use snake_case sem acento, 3 a 41 caracteres (ex.: ticket_medio_por_forma)."
    if categoria not in CATEGORIAS:
        return f"Categoria inválida. Use uma de: {', '.join(CATEGORIAS)}."
    if (PASTA / f"{nome}.md").exists() and not sobrescrever:
        return f"Já existe a função `{nome}`. Leia-a com ler_funcao ou use sobrescrever=true para criar nova versão."
    if not descricao or len(descricao) > 200:
        return "A descrição é obrigatória e deve ter até 200 caracteres (é o que aparece no índice)."
    codigo = codigo.strip("\n") + "\n"
    erros = validar_codigo(codigo)
    if erros:
        return "Código recusado: " + "; ".join(erros)
    try:  # teste com os dados reais antes de salvar
        amostra = formatar(_executar_codigo(codigo, carregar_dados(cam), dict(exemplo_parametros or {})))
    except (TimeoutError, RuntimeError) as e:
        return f"Código recusado: falhou no teste com os dados reais — {e}"
    versao = 1
    antigo = pagina(nome)
    if antigo:
        versao = int(_frontmatter(antigo).get("versao", "1")) + 1
    PASTA.mkdir(parents=True, exist_ok=True)
    (PASTA / f"{nome}.md").write_text(
        f"---\nnome: {nome}\ncategoria: {categoria}\ndescricao: \"{descricao.strip()}\"\n"
        f"parametros: \"{(parametros or '').strip()}\"\nversao: {versao}\n"
        f"atualizada: {datetime.now():%Y-%m-%d}\nautor: {autor}\n---\n\n"
        f"# `{nome}`\n\n{descricao.strip()}\n\n## Quando usar\n\n{explicacao.strip()}\n\n"
        f"## Fórmula\n\n{formula.strip()}\n\n## Parâmetros\n\n{(parametros or 'Nenhum além dos filtros padrão.').strip()}\n\n"
        f"## Código\n\n```python\n{codigo}```\n", encoding="utf-8")
    gerar_indice()
    return f"Função `{nome}` salva (versão {versao}) e índice atualizado. Teste com os dados reais:\n\n{amostra[:1500]}"
