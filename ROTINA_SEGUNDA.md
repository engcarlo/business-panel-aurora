# Rotina de segunda-feira · Controle de Recebimentos Aurora

> Instruções para quem nunca viu este trabalho. Roda toda **segunda-feira às 9h**
> pelo Agendador de Tarefas do Windows, com o comando
> `python -m aurora semana`, dentro da pasta `Projeto 1`.

## O que ela faz

Mantém em dia o controle de recebimentos da Distribuidora Aurora:

1. Procura comprovantes **novos** na pasta `Comprovantes`.
2. Lê os novos com o leitor OCR configurado em `dados/ocr_comando.txt`, que acrescenta
   as leituras em `dados/leituras.csv`.
3. Lança tudo na aba **Recebimentos** de `Controle_Recebimentos.xlsx` (data, cliente, valor, forma).
4. Renomeia os arquivos novos para `AAAA-MM-DD_Cliente_Valor.ext`.
5. Completa Região/UF e Categoria a partir da aba **Cadastro de Clientes**.
6. Recria a aba **Dashboard** e o arquivo `Painel_Aurora.html`.
7. Registra tudo o que fez em `dados/rotina_log.txt`.

## Como sabe o que é novo

Todo arquivo já processado tem nome no padrão `AAAA-MM-DD_Cliente_Valor.ext`
(reenvios terminam em `_copia`) ou começa com `ILEGIVEL_`. **Qualquer outro nome é novo.**
Nenhuma memória da execução anterior é necessária: o estado está nos nomes dos arquivos e
em `dados/leituras.csv`.

## Situações sem ninguém olhando

| situação | o que acontece |
|---|---|
| Nenhum arquivo novo | Não altera nada. Escreve "Nenhum comprovante novo" no log. |
| Arquivo novo, mas OCR não configurado | Não altera nada. Lista os arquivos pendentes no log. |
| OCR falhou | Não lança nada. Registra o erro. Na próxima segunda tenta de novo. |
| Comprovante ilegível | Não lança e não inventa valor. Renomeia para `ILEGIVEL_<nome>` para conferência manual. |
| Mesmo pagamento reenviado | Lança uma vez só. O segundo arquivo ganha `_copia`. |
| Pagador fora do cadastro | Lança o valor (entra no total), deixa Região/Categoria em branco, pinta a linha de amarelo com comentário. No dashboard e no painel aparece como "Não identificado". |
| Nome parecido, mas sem certeza | Não força o cliente. Trata como fora do cadastro e avisa no comentário: "parecido com X". Para confirmar, acrescente em `dados/apelidos.csv`. |
| Planilha aberta no Excel | Não consegue gravar. Avisa no log e não perde nada. Basta fechar o Excel e rodar de novo. |

## O que conferir depois

Abra `dados/rotina_log.txt` e procure por **Ilegíveis**, **fora do cadastro** e **Atenção**.
Esses são os únicos casos que precisam de uma pessoa.

## Desfazer

- Nomes de arquivo: `python -m aurora desfazer-renomeacao` (usa `dados/renomeacao_log.csv`).
- A planilha é recriada a partir de `dados/leituras.csv`. Corrigiu uma leitura no CSV?
  Basta rodar `python -m aurora tudo --aplicar`.
