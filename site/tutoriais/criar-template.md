# Criar um template

::: info Recurso novo, em construção
Parte do canal WhatsApp, que chega numa próxima versão. Nomes podem mudar até o lançamento.
:::

Template é uma mensagem com texto fixo que a Meta aprova antes do uso. É o único jeito de iniciar conversa no WhatsApp com quem não te mandou mensagem nas últimas 24 horas. Transmissões e a [ponte do Instagram](./ponte-ig-wa) usam templates.

::: v-pre

## Categorias

A Meta classifica cada template, e a categoria define o preço por mensagem:

| Categoria | Para quê | Exemplo |
|---|---|---|
| **Marketing** | Oferta, novidade, convite, reengajamento | "Abrimos as vagas da turma de novembro" |
| **Utilidade** | Algo que a pessoa pediu ou já contratou | `Seu material está pronto: {{1}}` |
| **Autenticação** | Código de verificação | `Seu código é {{1}}` |

Se você cadastrar como utilidade algo que é marketing, a Meta reclassifica. Na dúvida, é marketing. Valores no [FAQ](/faq#quanto-custa-cada-mensagem-de-whatsapp).

## Criando pelo painel

1. No painel, abra **Templates** e clique em criar.
2. Preencha:
   - **Nome:** só minúsculas, números e `_`. Ex.: `material_pronto`.
   - **Idioma:** português (BR).
   - **Categoria.**
   - **Corpo:** o texto, com variáveis numeradas `{{1}}`, `{{2}}` onde entra o que muda.
   - **Botões** (opcional): resposta rápida ou link.
3. Envie para aprovação. A aprovação é da Meta, não nossa: costuma sair em minutos, às vezes leva horas.

O painel lista os templates da sua conta, sincronizados com a Meta, com o estado de cada um (em análise, aprovado, recusado). Também dá pra criar direto no [Gerenciador do WhatsApp](https://business.facebook.com/wa/manage/message-templates/); eles aparecem no painel do mesmo jeito.


:::

<!-- PRINT: Gerenciador do WhatsApp, tela de criação de modelo de mensagem com categoria e corpo preenchidos -->
<Print>Gerenciador do WhatsApp, tela de criação de modelo de mensagem com categoria e corpo preenchidos.</Print>

::: v-pre

## Variáveis

Na hora de usar o template (num fluxo ou numa transmissão), cada `{{1}}`, `{{2}}` é ligada a um campo do lead: `{{1}}` = primeiro nome, `{{2}}` = link do material.

## Para ser aprovado

- Diga quem está falando e por que a pessoa está recebendo.
- Não comece nem termine o corpo com uma variável.
- Nada de texto que pareça golpe: encurtador de link desconhecido, promessa de dinheiro fácil, pedido de senha.
- Dê um exemplo de valor para cada variável quando a Meta pedir.

## Botões que continuam o fluxo

Um botão de resposta rápida no template pode disparar um fluxo quando clicado (gatilho de resposta a template). Exemplo: transmissão com os botões "Quero a vaga" e "Agora não", cada um levando para um fluxo diferente.

:::
