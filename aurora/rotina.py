"""Etapa 6 — rotina de segunda-feira (roda sem ninguém olhando).

Como sabe o que é novo: depois da etapa 2, todo arquivo já processado tem nome
AAAA-MM-DD_Cliente_Valor.ext ou começa com ILEGIVEL_. Qualquer outro nome na
pasta Comprovantes é comprovante novo.
"""
import os
import shlex
import subprocess
import contextlib
import io
import sys
import traceback
from datetime import datetime

from . import dashboard, etapas_dados as E, leituras as L, painel
from .config import Caminhos


def _ocr_comando(cam: Caminhos) -> str | None:
    if os.environ.get("AURORA_OCR"):
        return os.environ["AURORA_OCR"]
    f = cam.dados / "ocr_comando.txt"
    if f.exists():
        linhas = [l.strip() for l in f.read_text(encoding="utf-8-sig").splitlines()
                  if l.strip() and not l.lstrip().startswith("#")]
        return linhas[0] if linhas else None
    return None


def _conhecidos(cam):
    if not cam.leituras.exists():
        return set()
    return {lt.arquivo for lt in L.carregar(cam.leituras)}


class _Tee(io.TextIOBase):
    """Escreve no console e guarda tudo para o log."""
    def __init__(self, orig):
        self.orig, self.buf = orig, io.StringIO()
    def write(self, s):
        self.buf.write(s)
        try:
            self.orig.write(s)
        except Exception:
            pass
        return len(s)


def rodar(cam: Caminhos) -> int:
    tee = _Tee(sys.stdout)
    with contextlib.redirect_stdout(tee):
        return _rodar(cam, tee)


def _rodar(cam: Caminhos, tee) -> int:
    anota = print

    anota(f"--- Rotina Aurora · {datetime.now():%d/%m/%Y %H:%M} ---")
    try:
        arquivos = sorted(p.name for p in cam.comprovantes.iterdir() if p.is_file())
        conhecidos = _conhecidos(cam)
        sem_leitura = [a for a in arquivos if not E.ja_organizado(a) and a not in conhecidos]
        lidos_pendentes = [a for a in arquivos if not E.ja_organizado(a) and a in conhecidos]

        if sem_leitura:
            cmd = _ocr_comando(cam)
            if not cmd:
                anota(f"{len(sem_leitura)} comprovante(s) novo(s) aguardando leitura, mas nenhum leitor OCR "
                      f"configurado (dados/ocr_comando.txt). Nada foi alterado: {', '.join(sem_leitura)}")
                return 2
            anota(f"Lendo {len(sem_leitura)} comprovante(s) novo(s) com o OCR...")
            args = shlex.split(cmd, posix=False) + ["--saida", str(cam.leituras), "--pasta", str(cam.comprovantes), *sem_leitura]
            r = subprocess.run(args, cwd=cam.base, capture_output=True, text=True, encoding="utf-8")
            if r.returncode != 0:
                anota(f"OCR falhou (código {r.returncode}); nada foi lançado. Saída: {r.stderr.strip()[-500:]}")
                return 3
            faltou = [a for a in sem_leitura if a not in _conhecidos(cam)]
            if faltou:
                anota(f"Atenção: o OCR não devolveu leitura para: {', '.join(faltou)} (ficam para a próxima rodada).")

        if not sem_leitura and not lidos_pendentes:
            anota("Nenhum comprovante novo. Planilha, dashboard e painel continuam como estavam.")
            return 0

        E.etapa1_lancar(cam)
        E.etapa2_renomear(cam, aplicar=True)
        E.etapa3_cadastro(cam)
        from . import base_md
        r = base_md.gerar(cam)                      # camada Markdown (ano/mês) para o chat
        print(f"Base Markdown atualizada: {r['comprovantes']} comprovantes em {r['meses']} meses.")
        dashboard.gerar(cam)
        painel.gerar(cam)
        anota("Concluído: planilha, nomes de arquivo, dashboard e painel atualizados. Detalhes acima.")
        return 0
    except PermissionError as e:
        anota(f"Não consegui gravar ({e.filename}). A planilha provavelmente está aberta no Excel: "
              "feche e rode de novo. Nada foi perdido.")
        return 4
    except SystemExit as e:
        anota(f"Interrompido: {e}")
        return 5
    except Exception:
        anota("Erro inesperado:\n" + traceback.format_exc())
        return 1
    finally:
        cam.dados.mkdir(exist_ok=True)
        with cam.log_rotina.open("a", encoding="utf-8") as f:
            f.write(tee.buf.getvalue() + "\n")
