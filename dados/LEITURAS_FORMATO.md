# Formato de entrada: `dados/leituras.csv`

É o único ponto de contato entre o **leitor OCR** (etapa 1, a ser plugada) e o
resto do pipeline. O OCR só precisa produzir este arquivo; as etapas 1 a 6
fazem o resto.

## Arquivo

- CSV separado por **ponto e vírgula** (`;`), codificação **UTF-8** (com ou sem BOM).
- Uma linha **por arquivo** da pasta `Comprovantes` (inclusive duplicados e ilegíveis).
- Cabeçalho obrigatório:

```
arquivo;data;cliente;valor;forma;status;obs
```

| coluna    | conteúdo | aceita |
|-----------|----------|--------|
| `arquivo` | nome do arquivo na pasta `Comprovantes`, exatamente como está | `anexo(12).pdf` |
| `data`    | data **do pagamento**, lida de dentro do comprovante | `2026-01-08` ou `08/01/2026` |
| `cliente` | quem pagou, **exatamente como escrito** no comprovante (não padronize) | `Rede Farm. Popular` |
| `valor`   | valor **efetivamente pago** | `15550.00`, `15.550,00`, `R$ 15.550,00` |
| `forma`   | forma de pagamento | `Pix`, `TED`, `Transferência`, `Boleto`, `Depósito` (sem diferença de maiúsculas/acentos) |
| `status`  | `ok` ou `ilegivel` | vazio = `ok` |
| `obs`     | livre; para ilegível, diga o motivo | `foto escura, valor cortado` |

A coluna `arquivo_original` é criada pelo pipeline (etapa 2), não precisa ser preenchida.

## O que o OCR **não** precisa fazer

- **Duplicados:** o pipeline detecta sozinho (arquivo idêntico, ou mesmo cliente + data + valor).
  Basta ler os dois arquivos normalmente.
- **Padronizar nomes:** a etapa 3 casa com o cadastro. Para razões sociais que não se
  parecem com o nome usual, adicione uma linha em `dados/apelidos.csv`:
  `pagador;cliente` → `Comercio de Alimentos XYZ Ltda;Mercadao Central`.

## Regras de leitura (vindas do guia)

- Pagador pode vir como Origem, Debitado de, Cliente, Remetente, Conta de origem, ou sem rótulo.
  Em e-mail, o campo **"De:" é o banco**, não o cliente.
- Valor duplicado no comprovante (documento x pago, parcelas x total) → use o **pago**.
- Data sempre de dentro do comprovante, nunca do nome do arquivo. Em extrato, o ano vem do
  período no cabeçalho.
- Não conseguiu ler? `status=ilegivel` e o motivo em `obs`. **Nunca chute.**

## Rotina semanal (etapa 6)

Para a rotina chamar o OCR sozinha, escreva o comando em `dados/ocr_comando.txt` (uma linha).
Ele é chamado assim:

```
<comando> --saida <caminho>/dados/leituras.csv --pasta <caminho>/Comprovantes arquivo1 arquivo2 ...
```

e deve **acrescentar** (append) uma linha por arquivo recebido, no formato acima,
retornando código 0 em caso de sucesso.
