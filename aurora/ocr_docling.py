"""Leitor OCR da etapa 1: Docling -> extrator híbrido (regras + IA) -> dados/leituras.csv.

Roda no ambiente .venv-ocr (onde o Docling está instalado):

  .venv-ocr\\Scripts\\python -m aurora.ocr_docling --pasta Comprovantes --saida dados/leituras.csv [arquivos...]
  (sem arquivos = todos os da pasta que ainda não estão no CSV)

Opções: --sem-ia (só regras)   --refazer (ignora o cache de Markdown)

Mesmo contrato que a rotina semanal usa (dados/ocr_comando.txt): acrescenta uma linha
por arquivo e nunca chuta — o que não foi lido com segurança sai como status=ilegivel."""
from __future__ import annotations

import argparse
import csv
import sys
import time
from datetime import datetime
from pathlib import Path

from . import extrator

EXTS = {".pdf", ".jpg", ".jpeg", ".png", ".tif", ".tiff", ".bmp", ".webp"}
CAMPOS = ["arquivo", "data", "cliente", "valor", "forma", "status", "obs"]


class LeitorDocling:
    """Um conversor só, criado uma vez (carregar os modelos é o passo caro).
    PDFs com camada de texto: sem OCR (texto exato e rápido). Imagens: OCR em português."""

    def __init__(self):
        import importlib.util

        from docling.datamodel.base_models import InputFormat
        from docling.datamodel import pipeline_options as po
        from docling.document_converter import DocumentConverter, ImageFormatOption, PdfFormatOption

        # Motor de OCR: EasyOCR (tem português) se estiver instalado; senão RapidOCR (padrão do Docling)
        if importlib.util.find_spec("easyocr"):
            ocr = lambda: po.EasyOcrOptions(lang=["pt", "en"], force_full_page_ocr=True)
            self.motor = "EasyOCR"
        else:
            ocr = lambda: po.RapidOcrOptions(force_full_page_ocr=True)
            self.motor = "RapidOCR"
        # Reconhecimento de tabelas desligado: na CPU ele leva minutos por página e, nestes
        # comprovantes, junta rótulo e valor na mesma célula sem ganho para a extração.
        pdf = po.PdfPipelineOptions(do_ocr=False, do_table_structure=False)
        img = po.PdfPipelineOptions(do_ocr=True, do_table_structure=False, ocr_options=ocr())
        self._pdf_ocr = po.PdfPipelineOptions(do_ocr=True, do_table_structure=False, ocr_options=ocr())
        self.conv = DocumentConverter(
            allowed_formats=[InputFormat.PDF, InputFormat.IMAGE],
            format_options={InputFormat.PDF: PdfFormatOption(pipeline_options=pdf),
                            InputFormat.IMAGE: ImageFormatOption(pipeline_options=img)})
        self._conv_pdf_ocr = None

    @staticmethod
    def texto_embutido(caminho: Path) -> str:
        """Camada de texto do PDF via pypdfium2 (backend que já vem com o Docling).
        Para PDFs digitais é exata, preserva a ordem rótulo -> valor e leva milissegundos."""
        import pypdfium2 as pdfium

        doc = pdfium.PdfDocument(str(caminho))
        try:
            return "\n".join(doc[i].get_textpage().get_text_range() for i in range(len(doc)))
        finally:
            doc.close()

    def markdown(self, caminho: Path) -> tuple[str, str]:
        """Devolve (texto, erro). PDF com texto -> texto embutido; imagem/escaneado -> Docling + OCR.
        Usa o status do Docling, não a palavra 'Erro' no texto."""
        from docling.datamodel.base_models import ConversionStatus

        if caminho.suffix.lower() == ".pdf":
            try:
                txt = self.texto_embutido(caminho)
                if len(txt.strip()) >= 40:
                    return txt, ""
            except Exception:
                pass                                   # PDF estranho: segue pelo Docling
        res = self.conv.convert(caminho, raises_on_error=False)
        if res.status not in (ConversionStatus.SUCCESS, ConversionStatus.PARTIAL_SUCCESS):
            return "", f"Docling: {res.status.name}"
        md = res.document.export_to_markdown()
        if caminho.suffix.lower() == ".pdf" and len(md.strip()) < 40:
            md = self._pdf_com_ocr(caminho)      # PDF escaneado sem texto: refaz com OCR
        return md, ""

    def ocr_bruto(self, caminho: Path) -> str:
        """2ª passada para imagens: EasyOCR na imagem inteira, sem a análise de layout do
        Docling (que classifica o 'banner' com o valor em letra grande como figura e o descarta).
        Reconstrói as linhas agrupando as caixas de texto pela altura."""
        import easyocr

        if not hasattr(self, "_easy"):
            self._easy = easyocr.Reader(["pt", "en"], gpu=False, verbose=False)
        caixas = sorted((min(p[1] for p in b), max(p[1] for p in b), min(p[0] for p in b), txt)
                        for b, txt, _conf in self._easy.readtext(str(caminho), detail=1, paragraph=False))
        linhas, atual, base = [], [], None
        for y0, y1, x0, txt in caixas:
            meio = (y0 + y1) / 2
            if base is None or abs(meio - base) > (y1 - y0) * 0.6:
                if atual:
                    linhas.append("  ".join(t for _, t in sorted(atual)))
                atual, base = [], meio
            atual.append((x0, txt))
        if atual:
            linhas.append("  ".join(t for _, t in sorted(atual)))
        return "\n".join(linhas)

    def _pdf_com_ocr(self, caminho: Path) -> str:
        from docling.datamodel.base_models import InputFormat
        from docling.document_converter import DocumentConverter, PdfFormatOption

        if self._conv_pdf_ocr is None:
            self._conv_pdf_ocr = DocumentConverter(
                allowed_formats=[InputFormat.PDF],
                format_options={InputFormat.PDF: PdfFormatOption(pipeline_options=self._pdf_ocr)})
        res = self._conv_pdf_ocr.convert(caminho, raises_on_error=False)
        return res.document.export_to_markdown() if res.document else ""


def _ja_no_csv(saida: Path) -> set[str]:
    if not saida.exists():
        return set()
    with saida.open(encoding="utf-8-sig", newline="") as f:
        return {r["arquivo"] for r in csv.DictReader(f, delimiter=";") if r.get("arquivo")}


def _acrescentar(saida: Path, linhas: list[dict]):
    novo = not saida.exists() or saida.stat().st_size == 0
    with saida.open("a", encoding="utf-8-sig" if novo else "utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=CAMPOS, delimiter=";", extrasaction="ignore")
        if novo:
            w.writeheader()
        w.writerows(linhas)


def _cacheado(path: Path, refazer: bool, gerar) -> str:
    if path.exists() and not refazer:
        return path.read_text(encoding="utf-8")
    txt = gerar() or ""
    if txt:
        path.write_text(txt, encoding="utf-8")
    return txt


def ler_arquivo(leitor: LeitorDocling, caminho: Path, cache: Path, usar_ia: bool, refazer: bool) -> dict:
    """Ordem de leitura, definida pelo comparativo de 18/11/2026 (92 fotos e 16 PDFs contra o gabarito):
    - PDF:    texto embutido (16/16, <0,1s)  ->  Docling (12/16, 4,5s) para PDF escaneado
    - foto:   EasyOCR na imagem inteira (61/92, 20s)  ->  Docling+EasyOCR (55/92, 29s) se falhar
              (combinados: 77/92 — os erros de um não são os do outro)
    - por fim, se configurada, a camada de IA."""
    md_path, raw_path = cache / (caminho.name + ".md"), cache / (caminho.name + ".raw.txt")
    eh_pdf = caminho.suffix.lower() == ".pdf"
    tentativas = []                        # (nome da camada, texto) na ordem de preferência
    if eh_pdf:
        tentativas.append(("texto/Docling", lambda: _cacheado(md_path, refazer, lambda: leitor.markdown(caminho)[0])))
    else:
        tentativas.append(("EasyOCR", lambda: _cacheado(raw_path, refazer, lambda: leitor.ocr_bruto(caminho))))
        tentativas.append(("Docling", lambda: _cacheado(md_path, refazer, lambda: leitor.markdown(caminho)[0])))

    r, md, motivos = {"status": "ilegivel", "obs": "OCR não extraiu texto"}, "", []
    for nome, obter in tentativas:
        texto = obter()
        md = md or texto
        if not texto.strip():
            motivos.append(f"{nome}: sem texto")
            continue
        r = extrator.extrair(texto)
        if r["status"] == "ok":
            r["camada"] = f"regras ({nome})"
            break
        motivos.append(f"{nome}: {r.get('obs')}")
    if r["status"] != "ok":
        r["obs"] = " | ".join(motivos)
        r["camada"] = "regras"
    if r["status"] != "ok" and usar_ia:
        from . import extrator_ia
        if extrator_ia.disponivel():
            r = extrator_ia.extrair(caminho, md)
            r["camada"] = "ia"
        else:
            r["obs"] = (r.get("obs") or "") + " | IA indisponível (sem credenciais)"
    if r["status"] != "ok":
        r["status"] = "ilegivel"        # contrato do leituras.csv: ok | ilegivel (vai para conferência manual)
    r["arquivo"] = caminho.name
    return r


def main(argv=None):
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    ap = argparse.ArgumentParser(prog="aurora.ocr_docling")
    ap.add_argument("--pasta", required=True)
    ap.add_argument("--saida", required=True)
    ap.add_argument("--sem-ia", action="store_true")
    ap.add_argument("--refazer", action="store_true", help="ignora o cache de OCR")
    ap.add_argument("--novo", action="store_true",
                    help="recomeça o CSV de saída do zero (o cache de OCR é reaproveitado)")
    ap.add_argument("arquivos", nargs="*")
    a = ap.parse_args(argv)

    pasta, saida = Path(a.pasta), Path(a.saida)
    saida.parent.mkdir(parents=True, exist_ok=True)
    cache = saida.parent / "ocr_md"
    cache.mkdir(exist_ok=True)
    if a.novo and saida.exists():
        saida.replace(saida.with_suffix(".anterior.csv"))       # guarda a versão anterior
    conhecidos = _ja_no_csv(saida)
    nomes = a.arquivos or sorted(p.name for p in pasta.iterdir()
                                 if p.is_file() and p.suffix.lower() in EXTS)
    nomes = [n for n in nomes if n not in conhecidos]
    if not nomes:
        print("Nada novo para ler.")
        return 0

    print(f"Carregando Docling... ({len(nomes)} arquivo(s))")
    leitor = LeitorDocling()
    print(f"OCR de imagens: {leitor.motor}")
    t0, linhas = time.time(), []
    for i, nome in enumerate(nomes, 1):
        t = time.time()
        try:
            r = ler_arquivo(leitor, pasta / nome, cache, not a.sem_ia, a.refazer)
        except Exception as e:                       # um arquivo ruim não derruba o lote
            r = {"arquivo": nome, "status": "ilegivel", "obs": f"falha: {type(e).__name__}: {e}"[:200], "camada": "-"}
        linhas.append(r)
        _acrescentar(saida, [r])                     # grava a cada arquivo: interrupção não perde o feito
        print(f"[{i}/{len(nomes)}] {nome}: {r['status']} ({r.get('camada')}, {time.time() - t:.1f}s)"
              + (f" — {r.get('obs')}" if r["status"] != "ok" else
                 f" — {r.get('data')} | {r.get('cliente')} | {r.get('valor')} | {r.get('forma')}"))
    ok = sum(r["status"] == "ok" for r in linhas)
    print(f"\nConcluído em {time.time() - t0:.0f}s: {ok} lidos, {len(linhas) - ok} para revisão. "
          f"Markdown em {cache}  ({datetime.now():%d/%m %H:%M})")
    return 0


if __name__ == "__main__":
    sys.exit(main())
