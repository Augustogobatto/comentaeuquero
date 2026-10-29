---
title: Próximos upgrades
---

# Próximos upgrades

O que está sendo feito e o que vem depois. A lista é curada: entra o que resolve problema de quem usa.

<p>
<Estado v="planejado" /> ainda não começou &nbsp; <Estado v="andamento" /> sendo construído &nbsp; <Estado v="feito" /> já está na versão estável
</p>

## Tem uma ideia?

Abra uma issue no GitHub com o rótulo **sugestao**. Conte o problema que você quer resolver, não só a solução: "perco leads quando a pessoa comenta 'quero!!!'" ajuda mais que "aceitar pontuação".

[Sugerir um upgrade](https://github.com/Augustogobatto/comentaeuquero/issues/new?labels=sugestao) · [Ver as sugestões abertas](https://github.com/Augustogobatto/comentaeuquero/issues?q=is%3Aissue+label%3Asugestao)

Antes de abrir, procure se já existe. Se existir, deixe um joinha na issue: é assim que a gente mede o que mais importa.

## WhatsApp

| Upgrade | Estado |
|---|---|
| **Vários números de WhatsApp por instalação.** Hoje: um número por conta do Instagram. | <Estado v="planejado" /> |

## Fluxos e mensagens

| Upgrade | Estado |
|---|---|
| **Palavra-chave casando plural e variações.** Hoje "livro" não dispara em "livros". | <Estado v="planejado" /> |
| **Teste A/B de mensagem com resultado.** O passo Teste A/B já sorteia; falta comparar a conversão de cada lado no painel. | <Estado v="planejado" /> |
| **Gatilho por webhook externo.** Começar um fluxo a partir de uma compra na Hotmart, um pagamento no Stripe ou qualquer sistema que mande um webhook. | <Estado v="planejado" /> |

## Painel e dados

| Upgrade | Estado |
|---|---|
| **Métricas por fluxo à prova de renomear.** Hoje o histórico de um fluxo se liga pelo nome; renomear separa os números. | <Estado v="planejado" /> |
| **CRM de leads em quadro (kanban).** Ver os leads por etapa e mover entre colunas. | <Estado v="planejado" /> |
| **Integração com o Chatwoot.** Passar a conversa para atendimento humano numa caixa de entrada. | <Estado v="planejado" /> |
| **Domínio próprio pelo painel.** Ligar o domínio sem mexer em arquivo, em qualquer tipo de instalação. Na instalação pelo chão já existe pela página do instalador. | <Estado v="planejado" /> |

## Infraestrutura

| Upgrade | Estado |
|---|---|
| **Fila única de webhooks.** Todos os eventos da Meta numa fila só, para aguentar picos (live com muita gente) sem perder ordem. | <Estado v="planejado" /> |
| **Site e documentação em inglês.** | <Estado v="planejado" /> |
| **Canal Telegram.** | <Estado v="planejado" /> |

## Já entregue

| Upgrade | Estado |
|---|---|
| **Instalador de 1 comando (chão)** com HTTPS, senha, backup diário e atualização automática assinada. | <Estado v="feito" /> |
| **Imagens assinadas.** Cada versão publicada é assinada no GitHub; a atualização automática recusa imagem sem assinatura. | <Estado v="feito" /> |
| **Editor visual de fluxos** com mensagem, botões, opções rápidas, mídia e carrossel, IA, esperas, condição, teste A/B, etiquetas, campos e webhook. | <Estado v="feito" /> |
| **WhatsApp pela Cloud API oficial.** Conexão do número, fluxos por palavra-chave, ponte Instagram → WhatsApp, templates em pastas e transmissões com relatório por pessoa. [Tutorial](/tutoriais/conectar-whatsapp). | <Estado v="feito" /> |
| **Conectar ao Claude (MCP).** Peça ao Claude pra montar fluxo, ver leads e preparar transmissão. Ele não liga fluxo nem dispara sozinho. [Tutorial](/tutoriais/conectar-claude). | <Estado v="feito" /> |
| **Proteção contra prompt injection no passo de IA.** A instrução fica separada do texto da pessoa, que vai como dado e não muda o comportamento da IA. [Tutorial](/tutoriais/ia-no-fluxo). | <Estado v="feito" /> |
| **Credenciais cifradas pelo painel**, sem precisar editar arquivo. | <Estado v="feito" /> |
