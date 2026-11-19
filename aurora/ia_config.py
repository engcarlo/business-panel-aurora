"""Cadastro das APIs usadas pelo chat de análise (dados/config_ia.json).

A chave fica só neste arquivo local, nunca vai para o HTML: o navegador recebe a chave
mascarada (sk-ant-…a1b2). Quem tiver acesso à pasta do projeto consegue ler o arquivo —
trate a pasta como confidencial."""
from __future__ import annotations

import json
import uuid
from pathlib import Path

PROVEDORES = {
    "anthropic": {
        "nome": "Anthropic (Claude)",
        "modelos": ["claude-opus-5-5", "claude-sonnet-5-5", "claude-haiku-5-5", "claude-fable-5-2"],
        "padrao": "claude-opus-5-5",
    },
}


def _arquivo(dados: Path) -> Path:
    return dados / "config_ia.json"


def _ler(dados: Path) -> dict:
    p = _arquivo(dados)
    if p.exists():
        return json.loads(p.read_text(encoding="utf-8"))
    return {"apis": []}


def _gravar(dados: Path, cfg: dict):
    dados.mkdir(exist_ok=True)
    tmp = _arquivo(dados).with_suffix(".tmp")
    tmp.write_text(json.dumps(cfg, ensure_ascii=False, indent=2), encoding="utf-8")
    tmp.replace(_arquivo(dados))


def mascarar(chave: str) -> str:
    return (chave[:7] + "…" + chave[-4:]) if len(chave) > 14 else "…"


def listar(dados: Path) -> list[dict]:
    return [{**{k: v for k, v in a.items() if k != "chave"}, "chave": mascarar(a.get("chave", ""))}
            for a in _ler(dados)["apis"]]


def adicionar(dados: Path, nome: str, provedor: str, modelo: str, chave: str, padrao: bool = False) -> dict:
    if provedor not in PROVEDORES:
        raise ValueError(f"provedor não suportado: {provedor}")
    if modelo not in PROVEDORES[provedor]["modelos"]:
        raise ValueError(f"modelo não suportado: {modelo}")
    chave = (chave or "").strip()
    if len(chave) < 20:
        raise ValueError("chave da API inválida")
    cfg = _ler(dados)
    api = {"id": uuid.uuid4().hex[:8], "nome": (nome or "").strip() or f"{provedor} · {modelo}",
           "provedor": provedor, "modelo": modelo, "chave": chave,
           "padrao": padrao or not cfg["apis"]}
    if api["padrao"]:
        for a in cfg["apis"]:
            a["padrao"] = False
    cfg["apis"].append(api)
    _gravar(dados, cfg)
    return {**api, "chave": mascarar(chave)}


def remover(dados: Path, api_id: str) -> bool:
    cfg = _ler(dados)
    antes = len(cfg["apis"])
    cfg["apis"] = [a for a in cfg["apis"] if a["id"] != api_id]
    if cfg["apis"] and not any(a["padrao"] for a in cfg["apis"]):
        cfg["apis"][0]["padrao"] = True
    _gravar(dados, cfg)
    return len(cfg["apis"]) < antes


def definir_padrao(dados: Path, api_id: str) -> bool:
    cfg = _ler(dados)
    if not any(a["id"] == api_id for a in cfg["apis"]):
        return False
    for a in cfg["apis"]:
        a["padrao"] = a["id"] == api_id
    _gravar(dados, cfg)
    return True


def obter(dados: Path, api_id: str | None = None) -> dict | None:
    """A API pedida, ou a padrão. Inclui a chave (uso interno do servidor)."""
    apis = _ler(dados)["apis"]
    if api_id:
        return next((a for a in apis if a["id"] == api_id), None)
    return next((a for a in apis if a.get("padrao")), apis[0] if apis else None)
