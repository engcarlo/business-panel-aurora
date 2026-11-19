"""Chat de análise — independente de provedor.

Três camadas:
  1. SKILL      skill_aurora/SKILL.md (texto puro) vira a instrução de sistema.
  2. FERRAMENTAS registro neutro: nome + descrição + JSON Schema + função Python.
                 É o formato que qualquer provedor com "tool calling" entende.
  3. ADAPTADOR  converte o registro para a API do provedor e roda o laço de ferramentas.
                 Implementado: Anthropic (Claude). Novo provedor = novo adaptador em ADAPTADORES.
"""
from __future__ import annotations

import json
import re
from collections import defaultdict
from datetime import date
from pathlib import Path

from . import base_md, funcoes, ia_config
from .config import MESES, RAIZ_PROJETO, Caminhos

SKILL = RAIZ_PROJETO / "skill_aurora" / "SKILL.md"
LIMITE_LEITURA = 30_000
MAX_VOLTAS = 15


def instrucoes() -> str:
    """Corpo do SKILL.md (sem o frontmatter) — a 'skill' que orienta o chat."""
    txt = SKILL.read_text(encoding="utf-8")
    return re.sub(r"^---\n.*?\n---\n", "", txt, count=1, flags=re.S).strip()


# ====================================================================== 2. FERRAMENTAS (neutras)
def _dentro(base: Path, caminho: str) -> Path:
    p = (base / (caminho or "").replace("\\", "/").lstrip("/")).resolve()
    if p != base.resolve() and base.resolve() not in p.parents:
        raise ValueError("caminho fora da base_md")
    return p


def _obj(props: dict, obrig: list[str] | None = None) -> dict:
    return {"type": "object", "properties": props, "required": obrig or [], "additionalProperties": False}


S, I, B = {"type": "string"}, {"type": "integer"}, {"type": "boolean"}
FILTROS_SCHEMA = {"ano": I, "mes_inicio": I, "mes_fim": I, "cliente": S, "regiao": S, "categoria": S, "forma": S}


def ferramentas(cam: Caminhos, registro: list) -> list[dict]:
    base = base_md.raiz(cam)

    def anota(nome, detalhe=""):
        registro.append(f"{nome}{(': ' + detalhe) if detalhe else ''}")

    # ---------------- biblioteca de funções
    def listar_funcoes():
        anota("listar_funcoes")
        funcoes.gerar_indice()
        return (funcoes.PASTA / "_indice.md").read_text(encoding="utf-8")

    def ler_funcao(nome):
        anota("ler_funcao", nome)
        return funcoes.pagina(nome) or f"Função `{nome}` não existe. Veja listar_funcoes."

    def executar_funcao(nome, parametros=None):
        anota("executar_funcao", nome)
        return funcoes.executar(cam, nome, parametros or {})

    def criar_funcao(nome, categoria, descricao, parametros, explicacao, formula, codigo,
                     exemplo_parametros=None, sobrescrever=False):
        anota("criar_funcao", nome)
        return funcoes.criar(cam, nome, categoria, descricao, parametros, explicacao, formula, codigo,
                             exemplo_parametros or {}, sobrescrever)

    # ---------------- base Markdown
    def listar_pasta(caminho=""):
        anota("listar_pasta", caminho or "/")
        p = _dentro(base, caminho)
        if not p.is_dir():
            return f"'{caminho}' não é uma pasta."
        itens = sorted(p.iterdir(), key=lambda x: (x.is_file(), x.name))
        return "\n".join(f"{'[pasta] ' if i.is_dir() else ''}{i.relative_to(base).as_posix()}" for i in itens) or "(vazia)"

    def ler_md(caminho):
        anota("ler_md", caminho)
        p = _dentro(base, caminho)
        if not p.is_file() or p.suffix != ".md":
            return f"Arquivo '{caminho}' não encontrado. Use listar_pasta."
        t = p.read_text(encoding="utf-8")
        return t if len(t) <= LIMITE_LEITURA else t[:LIMITE_LEITURA] + "\n\n[...cortado: arquivo grande]"

    def consultar(agrupar_por="mes", **filtros):
        anota("consultar", f"agrupar_por={agrupar_por}")
        dados = funcoes.filtrar(funcoes.carregar_dados(cam), **{k: v for k, v in filtros.items() if v})
        if not dados:
            return "Nenhum recebimento com esses filtros."
        chave = {"mes": lambda d: f"{d['ano']}-{d['mes']:02d} {MESES[d['mes'] - 1]}", "cliente": lambda d: d["cliente"],
                 "forma": lambda d: d["forma"], "regiao": lambda d: f"{d['regiao']}/{d['uf']}" if d["uf"] else d["regiao"],
                 "categoria": lambda d: d["categoria"], "situacao": lambda d: d["situacao"],
                 "cliente_mes": lambda d: f"{d['cliente']} | {d['ano']}-{d['mes']:02d}", "nenhum": lambda d: "Total"}.get(agrupar_por)
        if not chave:
            return "agrupar_por inválido."
        g = defaultdict(lambda: [0.0, 0])
        for d in dados:
            g[chave(d)][0] += d["valor"]
            g[chave(d)][1] += 1
        total = sum(d["valor"] for d in dados)
        ordem = sorted(g.items()) if agrupar_por in ("mes", "cliente_mes") else sorted(g.items(), key=lambda kv: -kv[1][0])
        pct = lambda x: f"{x * 100:.1f}%".replace(".", ",")
        linhas = [f"Total filtrado: {base_md.brl(total)} em {len(dados)} recebimentos.", "",
                  f"| {agrupar_por} | Valor | Qtd | % | Ticket médio |", "|---|---:|---:|---:|---:|"]
        linhas += [f"| {n} | {base_md.brl(v)} | {q} | {pct(v / total)} | {base_md.brl(v / q)} |" for n, (v, q) in ordem]
        return "\n".join(linhas)

    def organizar_base():
        anota("organizar_base")
        r = base_md.organizar(cam)
        partes = [f"{r['recebimentos']} recebimentos em {r['meses']} meses.",
                  f"Movidos: {len(r['movidos'])}" + "".join(f"\n- {m}" for m in r["movidos"])]
        if r["sem_data"]:
            partes.append("Sem data no frontmatter (não movidos): " + ", ".join(r["sem_data"]))
        if r["pastas_fora_do_padrao"]:
            partes.append("Pastas fora do padrão: " + ", ".join(r["pastas_fora_do_padrao"]))
        return "\n".join(partes)

    def mover_md(origem, pasta_destino):
        anota("mover_md", f"{origem} -> {pasta_destino}")
        if not (re.fullmatch(r"\d{4}/\d{2}-[a-z]+", pasta_destino) or pasta_destino == "_pendencias"):
            return "Destino recusado: use o padrão <ano>/<MM-mes>, ex.: 2026/04-abril."
        o, d = _dentro(base, origem), _dentro(base, pasta_destino)
        if not o.is_file():
            return f"'{origem}' não existe."
        d.mkdir(parents=True, exist_ok=True)
        alvo = d / o.name
        if alvo.exists():
            return f"Já existe {alvo.relative_to(base).as_posix()}; nada foi movido."
        o.replace(alvo)
        base_md.indices(cam)
        return f"Movido para {alvo.relative_to(base).as_posix()} e resumos atualizados."

    def salvar_analise(titulo, conteudo_markdown, ano, mes):
        anota("salvar_analise", titulo)
        if not (1 <= mes <= 12 and 2000 <= ano <= 2100):
            return "ano/mês inválidos."
        pasta = base_md.pasta_mes(base, date(ano, mes, 1))
        pasta.mkdir(parents=True, exist_ok=True)
        slug = re.sub(r"[^a-z0-9]+", "-", base_md._sem_acento(titulo).lower()).strip("-")[:60] or "analise"
        alvo = pasta / f"analise_{slug}.md"
        alvo.write_text(f"---\ntipo: analise\nano: {ano}\nmes: {mes}\ntitulo: \"{titulo}\"\n---\n\n"
                        f"# {titulo}\n\n{conteudo_markdown.strip()}\n", encoding="utf-8")
        return f"Análise salva em base_md/{alvo.relative_to(base).as_posix()}"

    cats = {"type": "string", "enum": funcoes.CATEGORIAS}
    return [
        dict(nome="listar_funcoes", fn=listar_funcoes, schema=_obj({}),
             descricao="Lê o índice da biblioteca de funções de negócio: o que cada uma calcula e seus parâmetros. Consulte antes de calcular indicadores."),
        dict(nome="ler_funcao", fn=ler_funcao, schema=_obj({"nome": S}, ["nome"]),
             descricao="Lê a página de uma função (quando usar, fórmula, parâmetros e código)."),
        dict(nome="executar_funcao", fn=executar_funcao,
             schema=_obj({"nome": S, "parametros": {"type": "object", "description":
                          "Parâmetros próprios da função + filtros (ano, mes_inicio, mes_fim, cliente, regiao, categoria, forma)."}}, ["nome"]),
             descricao="Executa uma função da biblioteca sobre os recebimentos reais e devolve resumo + tabela."),
        dict(nome="criar_funcao", fn=criar_funcao,
             schema=_obj({"nome": S, "categoria": cats, "descricao": S, "parametros": S, "explicacao": S, "formula": S,
                          "codigo": {"type": "string", "description": "Código Python com def calcular(dados, ...): seguindo o contrato da skill."},
                          "exemplo_parametros": {"type": "object"}, "sobrescrever": B},
                         ["nome", "categoria", "descricao", "parametros", "explicacao", "formula", "codigo"]),
             descricao="Cria (ou versiona, com sobrescrever=true) uma função padronizada de cálculo de negócio. O código é validado e testado com os dados reais antes de salvar; o índice é atualizado."),
        dict(nome="consultar", fn=consultar,
             schema=_obj({"agrupar_por": {"type": "string", "enum": ["mes", "cliente", "forma", "regiao", "categoria", "situacao", "cliente_mes", "nenhum"]},
                          **FILTROS_SCHEMA}),
             descricao="Soma rápida e exata dos recebimentos com filtros e agrupamento, para perguntas simples."),
        dict(nome="listar_pasta", fn=listar_pasta, schema=_obj({"caminho": S}),
             descricao="Lista pastas e arquivos .md de uma pasta da base_md (vazio = raiz)."),
        dict(nome="ler_md", fn=ler_md, schema=_obj({"caminho": S}, ["caminho"]),
             descricao="Lê um .md da base (README, resumo de ano/mês, comprovante ou pendência)."),
        dict(nome="organizar_base", fn=organizar_base, schema=_obj({}),
             descricao="Corrige a organização <ano>/<MM-mes>: move comprovantes pela data, remove pastas vazias, aponta pastas fora do padrão e regenera os resumos."),
        dict(nome="mover_md", fn=mover_md, schema=_obj({"origem": S, "pasta_destino": S}, ["origem", "pasta_destino"]),
             descricao="Move um .md dentro da base para <ano>/<MM-mes> (ou _pendencias)."),
        dict(nome="salvar_analise", fn=salvar_analise,
             schema=_obj({"titulo": S, "conteudo_markdown": S, "ano": I, "mes": I}, ["titulo", "conteudo_markdown", "ano", "mes"]),
             descricao="Salva uma análise em .md na pasta do ano/mês de referência."),
    ]


def executar_ferramenta(registro_tools: list[dict], nome: str, entrada: dict) -> tuple[str, bool]:
    """Roda uma ferramenta do registro neutro. Devolve (texto, é_erro)."""
    t = next((x for x in registro_tools if x["nome"] == nome), None)
    if not t:
        return f"Ferramenta desconhecida: {nome}", True
    try:
        return str(t["fn"](**(entrada or {}))), False
    except ValueError as e:
        return f"Recusado: {e}.", True
    except TypeError as e:
        return f"Parâmetros inválidos para {nome}: {e}", True
    except Exception as e:
        return f"Erro em {nome}: {type(e).__name__}: {e}", True


# ====================================================================== 3. ADAPTADORES
def _anthropic(api: dict, sistema: str, tools: list[dict], msgs: list[dict]) -> dict:
    import anthropic

    client = anthropic.Anthropic(api_key=api["chave"])
    defs = [{"name": t["nome"], "description": t["descricao"], "input_schema": t["schema"]} for t in tools]
    extra = {}
    if api["modelo"] != "claude-haiku-5-5":           # Haiku 5.5 não tem fallback no servidor
        extra.update(betas=["server-side-fallback-2026-07-01"], fallbacks="default")
    if api["modelo"] in ("claude-opus-5-5", "claude-haiku-5-5"):
        extra["output_config"] = {"effort": "medium"}
    system = [{"type": "text", "text": sistema, "cache_control": {"type": "ephemeral"}}]   # skill + tools em cache
    conversa = list(msgs)
    entrada = saida = 0
    try:
        for _ in range(MAX_VOLTAS):
            r = client.beta.messages.create(model=api["modelo"], max_tokens=16000, system=system,
                                            tools=defs, messages=conversa, **extra)
            entrada += r.usage.input_tokens
            saida += r.usage.output_tokens
            if r.stop_reason == "refusal":
                return {"erro": "O modelo recusou a solicitação."}
            usos = [b for b in r.content if b.type == "tool_use"]
            if r.stop_reason == "pause_turn":
                conversa.append({"role": "assistant", "content": r.content})
                continue
            if r.stop_reason != "tool_use" or not usos:
                texto = "\n".join(b.text for b in r.content if b.type == "text").strip()
                return {"resposta": texto or "(sem texto na resposta)", "modelo": r.model,
                        "tokens": {"entrada": entrada, "saida": saida}}
            conversa.append({"role": "assistant", "content": r.content})   # devolve os blocos sem alterar
            resultados = []
            for b in usos:                                                 # todos os resultados numa mensagem só
                txt, erro = executar_ferramenta(tools, b.name, b.input if isinstance(b.input, dict) else {})
                resultados.append({"type": "tool_result", "tool_use_id": b.id, "content": txt, "is_error": erro})
            conversa.append({"role": "user", "content": resultados})
        return {"erro": f"A análise passou de {MAX_VOLTAS} etapas de ferramentas; refine a pergunta."}
    except anthropic.AuthenticationError:
        return {"erro": "Chave da API recusada (401). Confira o cadastro em ⚙ Configurações."}
    except anthropic.RateLimitError:
        return {"erro": "Limite de uso da API atingido (429). Tente de novo em instantes."}
    except anthropic.BadRequestError as e:
        return {"erro": f"Requisição recusada pela API (400): {getattr(e, 'message', e)}"}
    except anthropic.APIStatusError as e:
        return {"erro": f"Erro da API ({e.status_code})."}
    except anthropic.APIConnectionError:
        return {"erro": "Sem conexão com a API. Verifique a internet."}


def _anthropic_teste(api: dict) -> dict:
    import anthropic
    try:
        r = anthropic.Anthropic(api_key=api["chave"]).messages.create(
            model=api["modelo"], max_tokens=2000, messages=[{"role": "user", "content": "Responda apenas: OK"}])
        return {"ok": True, "modelo": r.model}
    except anthropic.AuthenticationError:
        return {"ok": False, "erro": "Chave recusada (401)"}
    except anthropic.APIStatusError as e:
        return {"ok": False, "erro": f"Erro da API ({e.status_code})"}
    except anthropic.APIConnectionError:
        return {"ok": False, "erro": "Sem conexão"}


ADAPTADORES = {"anthropic": (_anthropic, _anthropic_teste)}


# ====================================================================== API usada pelo servidor
def responder(cam: Caminhos, historico: list[dict], api_id: str | None = None) -> dict:
    api = ia_config.obter(cam.dados, api_id)
    if not api:
        return {"erro": "Nenhuma API cadastrada. Abra ⚙ Configurações › APIs de IA e cadastre uma chave."}
    adaptador = ADAPTADORES.get(api["provedor"])
    if not adaptador:
        return {"erro": f"Provedor '{api['provedor']}' ainda sem adaptador."}
    msgs = [{"role": m["role"], "content": str(m["content"])[:20_000]}
            for m in historico[-20:] if m.get("role") in ("user", "assistant") and m.get("content")]
    if not msgs or msgs[-1]["role"] != "user":
        return {"erro": "A última mensagem precisa ser do usuário."}
    registro: list[str] = []
    r = adaptador[0](api, instrucoes(), ferramentas(cam, registro), msgs)
    r.update(ferramentas=registro, api=api["nome"])
    return r


def testar(cam: Caminhos, api_id: str) -> dict:
    api = ia_config.obter(cam.dados, api_id)
    if not api:
        return {"ok": False, "erro": "API não encontrada"}
    adaptador = ADAPTADORES.get(api["provedor"])
    return adaptador[1](api) if adaptador else {"ok": False, "erro": "provedor sem adaptador"}
