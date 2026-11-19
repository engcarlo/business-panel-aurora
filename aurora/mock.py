"""Gera uma pasta de TESTE com dados FICTÍCIOS que imitam as armadilhas do caso
(nomes variantes, pagadores fora do cadastro, duplicados, ilegíveis).
Nunca toca a pasta real: escreve só em <base>/ (padrão: teste/)."""
import csv
import random
import shutil
from datetime import date, timedelta

from .config import RAIZ_PROJETO, Caminhos

CLIENTES = {  # nome do cadastro: (peso, ticket médio)
    "Atacado Uniao Comercial": (14, 21000), "Rede Supermercados Mais": (13, 19000),
    "Mercadao Central": (11, 14000), "Distribuidora Bebidas Lopes": (10, 12500),
    "Frigorifico Vale Verde": (9, 16000), "Rede Farmacias Popular": (8, 9000),
    "Supermercado Familia": (8, 8500), "Comercial Amazonas": (6, 7000),
    "Hortifruti Natural": (6, 4500), "Adega Ponto do Vinho": (5, 3800),
}
VARIANTES = {  # como o nome aparece em alguns comprovantes
    "Atacado Uniao Comercial": "ATACADO UNIÃO COMERCIAL LTDA",
    "Rede Farmacias Popular": "Rede Farm. Popular",
    "Distribuidora Bebidas Lopes": "Lopes Comercio de Bebidas Ltda",
    "Hortifruti Natural": "Hortifruti Naturall",
    "Frigorifico Vale Verde": "Frigorífico Vale Verde Ltda",
    "Supermercado Familia": "Supermercado Família ME",
}
FORA = ["Padaria Pao Dourado", "Comercial Sao Jose", "Emporio Bom Gosto", "Bar e Lanchonete do Ze"]
FORMAS = ["Pix", "Pix", "Pix", "TED", "Boleto", "Boleto", "Depósito"]
EXT = [".pdf"] * 6 + [".jpg"] * 3 + [".png"]


def gerar(cam: Caminhos, n_pag=222, n_dup=6, n_ileg=2, semente=2026):
    rnd = random.Random(semente)
    if cam.base.exists():
        shutil.rmtree(cam.base)
    cam.comprovantes.mkdir(parents=True)
    cam.dados.mkdir()
    shutil.copy(RAIZ_PROJETO / "modelos" / "Controle_Recebimentos_modelo.xlsx", cam.planilha)

    sazon = [0.85, 0.9, 1.15, 1.0, 1.25, 1.1]          # jan..jun
    nomes, pesos = list(CLIENTES), [p for p, _ in CLIENTES.values()]
    pags = []
    for i in range(n_pag):
        d = date(2026, 1, 1) + timedelta(days=rnd.randrange(181))
        if i < 12:
            cli, tk = FORA[i % 4], 5000
        else:
            cli = rnd.choices(nomes, pesos)[0]
            tk = CLIENTES[cli][1]
        v = round(tk * sazon[d.month - 1] * rnd.uniform(0.55, 1.45), 2)
        escrito = VARIANTES[cli] if cli in VARIANTES and rnd.random() < 0.35 else cli
        pags.append([d, escrito, v, rnd.choice(FORMAS)])

    linhas, usados = [], set()

    def nome_arq():
        while True:
            n = rnd.choice(["anexo({})", "ARQUIVO {}", "baixado ({})", "IMG_{}", "{}"]).format(rnd.randrange(10, 9999))
            n += rnd.choice(EXT)
            if n.lower() not in usados:
                usados.add(n.lower())
                return n

    for k, (d, cli, v, f) in enumerate(pags):
        a = nome_arq()
        (cam.comprovantes / a).write_text(f"MOCK {k} {d} {cli} {v}", encoding="utf-8")
        linhas.append([a, d.isoformat(), cli, f"{v:.2f}", f, "ok", ""])
    for k in range(n_dup):                     # reenvios: metade idêntica byte a byte
        orig = linhas[rnd.randrange(12, len(linhas))]
        a = nome_arq()
        src = cam.comprovantes / orig[0]
        if k % 2 == 0:
            shutil.copy(src, cam.comprovantes / a)
        else:
            (cam.comprovantes / a).write_text("REENVIO " + src.read_text(encoding="utf-8"), encoding="utf-8")
        v = orig[3].replace(".", ",") if k % 2 else orig[3]      # OCR pode trazer 1.234,56
        linhas.append([a, orig[1], orig[2], v, orig[4], "ok", ""])
    for motivo in ["foto escura, valor não legível", "enquadramento cortou o valor"][:n_ileg]:
        a = nome_arq()
        (cam.comprovantes / a).write_text("ILEGIVEL " + motivo, encoding="utf-8")
        linhas.append([a, "", "", "", "", "ilegivel", motivo])
    rnd.shuffle(linhas)
    with cam.leituras.open("w", encoding="utf-8-sig", newline="") as f:
        w = csv.writer(f, delimiter=";")
        w.writerow(["arquivo", "data", "cliente", "valor", "forma", "status", "obs"])
        w.writerows(linhas)
    (cam.apelidos).write_text("pagador;cliente\n", encoding="utf-8-sig")
    print(f"Pasta de teste criada em {cam.base} com {len(linhas)} comprovantes FICTÍCIOS.")
