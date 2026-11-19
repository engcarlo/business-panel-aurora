"""Caminhos e constantes do pipeline. Tudo é relativo a uma pasta-base,
para o mesmo código rodar na pasta real ou na pasta de teste (teste/)."""
from dataclasses import dataclass
from pathlib import Path

RAIZ_PROJETO = Path(__file__).resolve().parent.parent

ABA_REC = "Recebimentos"
ABA_CAD = "Cadastro de Clientes"
ABA_DASH = "Dashboard"
LINHA_CAB = 4      # cabeçalho das abas
LINHA_INI = 5      # primeira linha de dados

FORMAS = {"pix": "Pix", "ted": "TED", "boleto": "Boleto",
          "deposito": "Depósito", "depósito": "Depósito",
          "transferencia": "Transferência", "transferência": "Transferência"}

MESES = ["Janeiro", "Fevereiro", "Março", "Abril", "Maio", "Junho",
         "Julho", "Agosto", "Setembro", "Outubro", "Novembro", "Dezembro"]

NAO_IDENT = "Não identificado"
FMT_MOEDA = '"R$" #,##0.00'
FMT_DATA = "dd/mm/yyyy"


@dataclass
class Caminhos:
    base: Path

    @property
    def comprovantes(self): return self.base / "Comprovantes"
    @property
    def planilha(self): return self.base / "Controle_Recebimentos.xlsx"
    @property
    def dados(self): return self.base / "dados"
    @property
    def leituras(self): return self.dados / "leituras.csv"
    @property
    def apelidos(self): return self.dados / "apelidos.csv"
    @property
    def log_renomeacao(self): return self.dados / "renomeacao_log.csv"
    @property
    def log_rotina(self): return self.dados / "rotina_log.txt"
    @property
    def painel(self): return self.base / "Painel_Aurora.html"
