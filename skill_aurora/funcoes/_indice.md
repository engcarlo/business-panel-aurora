---
tipo: indice_funcoes
atualizado: 2026-11-19 17:03
---

# Índice de funções de negócio · Aurora

12 funções. Para usar: `executar_funcao(nome, parametros)`. Para ver fórmula e parâmetros: `ler_funcao(nome)`.

Filtros aceitos por TODAS as funções (dentro de `parametros`): `ano`, `mes_inicio`, `mes_fim`, `cliente`, `regiao`, `categoria`, `forma`.

## Receita

| Função | O que faz | Parâmetros próprios |
|---|---|---|
| [`ticket_medio`](ticket_medio.md) | Ticket médio (valor médio por recebimento), geral ou por cliente, forma, região, categoria ou mês. | agrupar_por: nenhum \| cliente \| forma \| regiao \| categoria \| mes (padrão: nenhum) |

## Clientes

| Função | O que faz | Parâmetros próprios |
|---|---|---|
| [`clientes_em_queda`](clientes_em_queda.md) | Lista clientes cuja receita caiu mais que um limite entre dois períodos (alerta de churn). | limite: queda mínima em fração (padrão 0.20 = 20%); a_inicio, a_fim, b_inicio, b_fim (padrão 1-3 x 4-6) |
| [`curva_abc_clientes`](curva_abc_clientes.md) | Curva ABC de clientes: classe A (até 80% da receita), B (até 95%) e C (restante). | corte_a: % acumulado da classe A (padrão 0.80); corte_b: % acumulado da classe B (padrão 0.95) |
| [`recorrencia_clientes`](recorrencia_clientes.md) | Frequência de cada cliente: meses ativos, nº de pagamentos, intervalo médio entre pagamentos e último pagamento. | nenhum |

## Concentracao

| Função | O que faz | Parâmetros próprios |
|---|---|---|
| [`concentracao_receita`](concentracao_receita.md) | Mede dependência de poucos clientes: participação do top N e índice HHI (Herfindahl). | top: quantos maiores clientes somar (padrão 3) |

## Tendencia

| Função | O que faz | Parâmetros próprios |
|---|---|---|
| [`comparar_periodos`](comparar_periodos.md) | Compara dois intervalos de meses (ex.: 1º x 2º trimestre) por cliente, região, categoria ou forma. | a_inicio, a_fim, b_inicio, b_fim: meses dos períodos A e B (padrão 1-3 x 4-6); agrupar_por: cliente \| regiao \| categoria \| forma (padrão cliente) |
| [`sazonalidade_mensal`](sazonalidade_mensal.md) | Índice de sazonalidade: quanto cada mês fica acima ou abaixo da média mensal (100 = média). | nenhum |
| [`variacao_mensal`](variacao_mensal.md) | Receita mês a mês com variação absoluta e percentual sobre o mês anterior. | nenhum |

## Pagamentos

| Função | O que faz | Parâmetros próprios |
|---|---|---|
| [`mix_formas_pagamento`](mix_formas_pagamento.md) | Participação de cada forma de pagamento (Pix, boleto, TED...) em valor e quantidade, com ticket médio. | por_cliente: true para detalhar a forma predominante de cada cliente (padrão false) |
| [`participacao_forma_por_categoria`](participacao_forma_por_categoria.md) | Percentual da receita de cada categoria que entrou por uma forma de pagamento (ex.: % de Pix por categoria). | forma: Pix \| TED \| Transferência \| Boleto \| Depósito (padrão Pix) |

## Previsao

| Função | O que faz | Parâmetros próprios |
|---|---|---|
| [`projecao_media_movel`](projecao_media_movel.md) | Projeta a receita dos próximos meses pela média móvel dos últimos N meses (estimativa simples). | janela: nº de meses na média (padrão 3); meses_a_frente: quantos meses projetar (padrão 1) |

## Qualidade

| Função | O que faz | Parâmetros próprios |
|---|---|---|
| [`qualidade_base`](qualidade_base.md) | Mostra quanto da receita está sem região/categoria (pagadores fora do cadastro) e quem são. | nenhum |
