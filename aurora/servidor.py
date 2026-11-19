"""Servidor local do painel: serve o Painel_Aurora.html e a API do chat/configuração.

  python -m aurora servidor            ->  http://127.0.0.1:8765

Só escuta em 127.0.0.1 (nada fica exposto na rede), recusa requisições de outros sites
(Origin/Host diferentes) e só serve arquivos de Comprovantes/ e base_md/."""
from __future__ import annotations

import json
import mimetypes
import threading
import webbrowser
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import unquote, urlparse

from . import base_md, ia_config
from .config import Caminhos

PASTAS_PUBLICAS = ("Comprovantes", "base_md")
MAX_CORPO = 2_000_000


def _handler(cam: Caminhos, porta: int):
    hosts_ok = {f"127.0.0.1:{porta}", f"localhost:{porta}"}
    trava_chat = threading.Lock()          # uma análise por vez (evita duas IAs mexendo na base juntas)

    class H(BaseHTTPRequestHandler):
        server_version = "Aurora/1.0"

        def log_message(self, fmt, *args):  # log enxuto
            print(f"  {self.command} {self.path.split('?')[0]} -> {args[1] if len(args) > 1 else ''}")

        # ---------------------------------------------------------- utilidades
        def _seguro(self) -> bool:
            if self.headers.get("Host") not in hosts_ok:
                return False
            origem = self.headers.get("Origin")
            return origem is None or urlparse(origem).netloc in hosts_ok

        def _json(self, obj, status=200):
            dados = json.dumps(obj, ensure_ascii=False).encode("utf-8")
            self.send_response(status)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Content-Length", str(len(dados)))
            self.send_header("Cache-Control", "no-store")
            self.end_headers()
            self.wfile.write(dados)

        def _corpo(self) -> dict:
            n = int(self.headers.get("Content-Length") or 0)
            if n > MAX_CORPO:
                raise ValueError("requisição grande demais")
            return json.loads(self.rfile.read(n) or b"{}")

        def _arquivo(self, p: Path):
            if not p.is_file():
                return self._json({"erro": "não encontrado"}, 404)
            dados = p.read_bytes()
            self.send_response(200)
            tipo = mimetypes.guess_type(p.name)[0] or "application/octet-stream"
            if tipo.startswith("text/") or p.suffix == ".md":
                tipo = ("text/markdown" if p.suffix == ".md" else tipo) + "; charset=utf-8"
            self.send_header("Content-Type", tipo)
            self.send_header("Content-Length", str(len(dados)))
            self.end_headers()
            self.wfile.write(dados)

        # ---------------------------------------------------------- GET
        def do_GET(self):
            if not self._seguro():
                return self._json({"erro": "origem não permitida"}, 403)
            rota = unquote(urlparse(self.path).path)
            if rota in ("/", "/Painel_Aurora.html"):
                return self._arquivo(cam.painel)
            if rota == "/api/status":
                apis = ia_config.listar(cam.dados)
                return self._json({"ok": True, "apis": len(apis), "provedores": ia_config.PROVEDORES,
                                   "base_md": base_md.raiz(cam).exists()})
            if rota == "/api/apis":
                return self._json({"apis": ia_config.listar(cam.dados)})
            partes = rota.strip("/").split("/", 1)
            if len(partes) == 2 and partes[0] in PASTAS_PUBLICAS:
                raiz = (cam.base / partes[0]).resolve()
                p = (raiz / partes[1]).resolve()
                if raiz in p.parents:
                    return self._arquivo(p)
            return self._json({"erro": "não encontrado"}, 404)

        # ---------------------------------------------------------- POST / DELETE
        def do_POST(self):
            if not self._seguro():
                return self._json({"erro": "origem não permitida"}, 403)
            rota = urlparse(self.path).path
            try:
                corpo = self._corpo()
                if rota == "/api/apis":
                    api = ia_config.adicionar(cam.dados, corpo.get("nome", ""), corpo.get("provedor", "anthropic"),
                                              corpo.get("modelo", ""), corpo.get("chave", ""), bool(corpo.get("padrao")))
                    return self._json({"api": api}, 201)
                if rota.startswith("/api/apis/") and rota.endswith("/padrao"):
                    ok = ia_config.definir_padrao(cam.dados, rota.split("/")[3])
                    return self._json({"ok": ok}, 200 if ok else 404)
                if rota.startswith("/api/apis/") and rota.endswith("/testar"):
                    from . import chat
                    return self._json(chat.testar(cam, rota.split("/")[3]))
                if rota == "/api/chat":
                    from . import chat
                    if not trava_chat.acquire(timeout=1):
                        return self._json({"erro": "Já há uma análise em andamento. Aguarde."}, 409)
                    try:
                        return self._json(chat.responder(cam, corpo.get("mensagens", []), corpo.get("api_id")))
                    finally:
                        trava_chat.release()
                if rota == "/api/organizar":
                    r = base_md.organizar(cam)
                    return self._json(r)
            except ValueError as e:
                return self._json({"erro": str(e)}, 400)
            except Exception as e:  # nunca derruba o servidor
                return self._json({"erro": f"{type(e).__name__}: {e}"}, 500)
            return self._json({"erro": "rota desconhecida"}, 404)

        def do_DELETE(self):
            if not self._seguro():
                return self._json({"erro": "origem não permitida"}, 403)
            rota = urlparse(self.path).path
            if rota.startswith("/api/apis/"):
                ok = ia_config.remover(cam.dados, rota.split("/")[3])
                return self._json({"ok": ok}, 200 if ok else 404)
            return self._json({"erro": "rota desconhecida"}, 404)

    return H


def rodar(cam: Caminhos, porta: int = 8765, abrir: bool = True):
    if not cam.painel.exists():
        raise SystemExit("Painel_Aurora.html não existe: rode `python -m aurora painel` antes.")
    if not base_md.raiz(cam).exists():
        print("Gerando a base Markdown pela primeira vez...")
        base_md.gerar(cam)
    srv = ThreadingHTTPServer(("127.0.0.1", porta), _handler(cam, porta))
    url = f"http://127.0.0.1:{porta}/"
    print(f"Painel Aurora com chat em {url}  (Ctrl+C para encerrar)")
    if abrir:
        threading.Timer(0.8, lambda: webbrowser.open(url)).start()
    try:
        srv.serve_forever()
    except KeyboardInterrupt:
        print("\nServidor encerrado.")
    finally:
        srv.server_close()
