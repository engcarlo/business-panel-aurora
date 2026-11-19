"""Camada de IA do extrator híbrido: só é chamada quando as regras por layout
não leram o comprovante com segurança. Usa Claude com saída estruturada.

Requer o pacote `anthropic` e credenciais (ANTHROPIC_API_KEY ou `ant auth login`).
Sem isso, `disponivel()` devolve False e o comprovante fica para revisão manual."""
from __future__ import annotations

import base64
import mimetypes
import os
from pathlib import Path
from typing import Literal, Optional

MODELO = "claude-opus-5-5"

INSTRUCOES = """Você lê comprovantes de pagamento recebidos pela Distribuidora Aurora Ltda
(a Aurora é sempre quem RECEBE; nunca é o pagador). Extraia um único pagamento.

Regras:
- pagador: quem pagou. Pode vir como Pagador, Origem, Debitado de, Cliente, Remetente,
  Conta de origem, Nome do pagador, ou solto no texto sem rótulo. Em e-mails, o campo
  "De:" é o banco que enviou o aviso, NÃO o pagador. Copie o nome exatamente como escrito.
- valor: o valor efetivamente pago. Se houver valor do documento e valor pago, ou parcelas
  e total, use o valor pago/total. Número com ponto decimal, sem separador de milhar.
- data: a data do pagamento, de dentro do comprovante (nunca do nome do arquivo). Em
  extratos, dia/mês vêm da linha do lançamento e o ano do período no cabeçalho. AAAA-MM-DD.
- forma: Pix, TED, Transferência (quando o comprovante diz só "transferência"), Boleto ou Depósito.
- Se algum campo não puder ser lido com certeza (foto escura, valor cortado, borrado),
  use legivel=false e explique em motivo. Nunca invente nem estime um valor."""


try:
    from pydantic import BaseModel, Field

    class LeituraIA(BaseModel):
        legivel: bool
        pagador: Optional[str] = None
        valor: Optional[float] = None
        data: Optional[str] = Field(None, description="AAAA-MM-DD")
        forma: Optional[Literal["Pix", "TED", "Transferência", "Boleto", "Depósito"]] = None
        motivo: str = Field("", description="por que não foi possível ler, se legivel=false")
except ImportError:  # pydantic vem junto com o anthropic
    LeituraIA = None


def disponivel() -> bool:
    if os.environ.get("AURORA_SEM_IA"):
        return False
    try:
        import anthropic  # noqa: F401
    except ImportError:
        return False
    return bool(os.environ.get("ANTHROPIC_API_KEY") or os.environ.get("ANTHROPIC_AUTH_TOKEN")
                or Path.home().joinpath(".config", "anthropic").exists())


def _bloco_arquivo(caminho: Path) -> dict:
    """O próprio arquivo vai para o modelo: imagem como imagem, PDF como documento.
    Ver o original é mais confiável que reler um OCR ruim."""
    dados = base64.standard_b64encode(caminho.read_bytes()).decode()
    if caminho.suffix.lower() == ".pdf":
        return {"type": "document", "source": {"type": "base64", "media_type": "application/pdf", "data": dados}}
    mime = mimetypes.guess_type(caminho.name)[0] or "image/jpeg"
    if mime == "image/jpg":
        mime = "image/jpeg"
    return {"type": "image", "source": {"type": "base64", "media_type": mime, "data": dados}}


def extrair(caminho: Path, markdown_ocr: str = "") -> dict:
    """Devolve {'data','cliente','valor','forma','status','obs'} no formato do leituras.csv."""
    import anthropic

    client = anthropic.Anthropic()
    conteudo = [_bloco_arquivo(caminho)]
    if markdown_ocr.strip():
        conteudo.append({"type": "text", "text": "Texto extraído pelo OCR (pode ter erros):\n\n" + markdown_ocr[:20000]})
    conteudo.append({"type": "text", "text": "Extraia o pagamento deste comprovante."})
    try:
        resp = client.beta.messages.parse(
            model=MODELO,
            max_tokens=4000,
            system=INSTRUCOES,
            betas=["server-side-fallback-2026-07-01"],
            fallbacks="default",   # se o modelo recusar por política, o servidor tenta outro modelo
            output_config={"effort": "medium"},
            messages=[{"role": "user", "content": conteudo}],
            output_format=LeituraIA,
        )
    except anthropic.RateLimitError as e:
        return _falha(f"IA: limite de requisições ({e.status_code}); tente de novo depois")
    except anthropic.APIStatusError as e:
        return _falha(f"IA: erro da API {e.status_code}")
    except anthropic.APIConnectionError:
        return _falha("IA: sem conexão com a API")

    if resp.stop_reason == "refusal" or resp.parsed_output is None:
        return _falha("IA não devolveu leitura (recusa ou resposta vazia)")
    r = resp.parsed_output
    if not r.legivel or not (r.pagador and r.valor and r.data and r.forma):
        return _falha(r.motivo or "IA não conseguiu ler todos os campos")
    return {"data": r.data, "cliente": r.pagador.strip(), "valor": f"{r.valor:.2f}",
            "forma": r.forma, "status": "ok", "obs": "lido por IA"}


def _falha(motivo: str) -> dict:
    return {"data": "", "cliente": "", "valor": "", "forma": "", "status": "ilegivel", "obs": motivo}
