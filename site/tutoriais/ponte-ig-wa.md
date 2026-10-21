# Ponte Instagram → WhatsApp

::: info Recurso novo, em construção
Parte do canal WhatsApp, que chega numa próxima versão. Nomes podem mudar até o lançamento.
:::

A pessoa comenta no Instagram, recebe a resposta no direct e, no mesmo fluxo, deixa o WhatsApp. A conversa continua lá, onde a mensagem é lida com mais frequência e não depende da janela do Instagram.

Precisa do [WhatsApp conectado](./conectar-whatsapp) e de um [template aprovado](./criar-template).

## Os dois nós novos

**Pedir WhatsApp.** No direct, pede o número da pessoa, confere se é um número válido (com ou sem o 9, com ou sem DDI) e guarda no campo `whatsapp` do lead. O nó tem um **texto de consentimento**, que a pessoa vê antes de mandar o número. Dar o número ali conta como autorização para receber mensagens no WhatsApp.

**Template WhatsApp.** Envia um template aprovado para o número do lead e passa a conversa para o WhatsApp. Quando a pessoa responde, o fluxo continua de onde parou, agora pelo WhatsApp.

## Montando o fluxo

1. Gatilho: comentário com `quero`.
2. Mensagem no direct: "Te mando o material no WhatsApp. Qual o seu número com DDD?"
3. **Pedir WhatsApp**, com o texto de consentimento: "Ao enviar seu número, você aceita receber nossas mensagens no WhatsApp. Para sair, é só responder SAIR."
4. **Template WhatsApp**, com o template de boas-vindas.
5. Daqui em diante, os passos saem pelo WhatsApp: Mensagem com o link, botões, Esperar, IA, etiquetas.

## Um lead, dois canais

O lead é o mesmo: a mesma linha, com o Instagram e o WhatsApp. Etiquetas e campos valem para os dois canais.

Se alguém do Instagram informar um número que já falou com você pelo WhatsApp, os dois registros se juntam no lead do Instagram (etiquetas e campos somados; em conflito, vale o do Instagram).

## Regras que valem

- O primeiro contato no WhatsApp com quem não te mandou mensagem por lá precisa ser um template. Por isso o nó Template WhatsApp vem logo depois do Pedir WhatsApp.
- Depois que a pessoa responde, abre a janela de 24 horas do WhatsApp, e os passos de texto livre funcionam.
- Se a pessoa responder **SAIR** ou **PARAR**, o lead é marcado e não recebe mais transmissões.
