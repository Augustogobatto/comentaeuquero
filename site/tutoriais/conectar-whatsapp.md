# Conectar o WhatsApp

::: info Recurso novo, em construção
O canal WhatsApp está sendo desenvolvido e chega numa próxima versão. Esta página descreve como ele vai funcionar. A parte da Meta (criar o número e o token) já pode ser feita hoje. Nomes de botões no painel podem mudar até o lançamento. Acompanhe em [Próximos upgrades](/upgrades).
:::

O comenta EU QUERO usa a **WhatsApp Cloud API**, a API oficial da Meta, no mesmo app que você já criou para o Instagram. Nada de QR code nem de WhatsApp Web automatizado: isso viola os termos do WhatsApp e derruba números.

## O que você vai juntar

Três informações, que vão para o painel em **Configurações**:

| Dado | O que é | Onde achar |
|---|---|---|
| **WABA ID** | O ID da sua conta do WhatsApp Business na Meta | Configuração da API do WhatsApp, no app |
| **Phone Number ID** | O ID do número (não é o número de telefone) | Mesma página |
| **Token permanente** | A chave que deixa a instância enviar pelo número, sem vencer | Usuário do sistema, no Gerenciador de Negócios |

As três ficam cifradas no banco, como a chave secreta do app do Instagram.

## Antes de começar

- Um número de telefone que **não esteja em uso** no app WhatsApp ou WhatsApp Business. Se estiver, você vai precisar apagar a conta do app nesse número antes. Um chip novo é o caminho mais simples.
- Um **portfólio empresarial** (Gerenciador de Negócios) na Meta. Se não tiver, a Meta cria um no processo.
- Um **cartão de crédito** cadastrado na conta do WhatsApp, para as mensagens cobradas. Veja [quanto custa](/faq#quanto-custa-cada-mensagem-de-whatsapp).

## 1. Adicione o WhatsApp ao app

1. Em [developers.facebook.com](https://developers.facebook.com), abra o seu app.
2. Em **Casos de uso**, clique em **Adicionar caso de uso** e escolha **Conectar-se com os clientes pelo WhatsApp**.
3. Siga o assistente: ele liga o app a um portfólio empresarial e cria uma conta do WhatsApp Business (WABA).

<!-- PRINT: lista de casos de uso com "Conectar-se com os clientes pelo WhatsApp" -->
<Print>Lista de casos de uso com "Conectar-se com os clientes pelo WhatsApp".</Print>

## 2. Adicione o seu número

1. No caso de uso do WhatsApp, abra **Configuração da API**.
2. A Meta já oferece um **número de teste**, que só manda mensagem para até 5 números que você cadastrar. Bom para o primeiro teste.
3. Para o número de verdade, clique em **Adicionar número de telefone**, informe o nome de exibição (o nome que aparece para os clientes, revisado pela Meta) e confirme o código por SMS ou ligação.

Nessa mesma página aparecem o **Phone Number ID** e o **WhatsApp Business Account ID** (o WABA ID). Copie os dois.

<!-- PRINT: página "Configuração da API" do WhatsApp mostrando Phone Number ID e WhatsApp Business Account ID -->
<Print>Página "Configuração da API" do WhatsApp mostrando o Phone Number ID e o WhatsApp Business Account ID.</Print>

## 3. Crie o token permanente

O token que aparece na página Configuração da API vence em 24 horas. Para a instância, você precisa de um token de **usuário do sistema**, que não vence.

1. Abra [business.facebook.com/settings](https://business.facebook.com/settings) no portfólio do app.
2. Vá em **Usuários → Usuários do sistema** e clique em **Adicionar**. Dê um nome ("ceq") e a função **Administrador**.
3. Com o usuário selecionado, clique em **Atribuir ativos**:
   - **Apps:** o seu app, com controle total.
   - **Contas do WhatsApp:** a sua WABA, com controle total.
4. Clique em **Gerar novo token**:
   - Escolha o seu app.
   - Validade: **Nunca**.
   - Permissões: `whatsapp_business_messaging` e `whatsapp_business_management`.
5. Copie o token. Ele só aparece uma vez.

<!-- PRINT: "Usuários do sistema" com o botão "Gerar novo token" e as permissões whatsapp_business_messaging e whatsapp_business_management marcadas -->
<Print>"Usuários do sistema" com o botão "Gerar novo token" e as permissões whatsapp_business_messaging e whatsapp_business_management marcadas.</Print>

::: danger Trate o token como senha
Quem tem esse token manda mensagem pelo seu número. Não cole em chat, e-mail nem print. Ele vai direto para o painel, que guarda cifrado. Se vazar, gere outro na mesma tela e revogue o antigo.
:::

## 4. Webhook do WhatsApp

O WhatsApp usa o mesmo endereço do Instagram.

1. No caso de uso do WhatsApp, abra **Configuração** (webhooks).
2. **URL de callback:** `https://SEU-ENDERECO/webhook`. **Verificar token:** o mesmo do Instagram. **Verificar e salvar**.
3. Em **Campos do webhook**, assine **messages**. É por ele que chegam as mensagens recebidas e os avisos de entregue, lido e falhou.

<!-- PRINT: configuração de webhook do WhatsApp com o campo "messages" assinado -->
<Print>Configuração de webhook do WhatsApp com o campo "messages" assinado.</Print>

## 5. Cole no painel

No painel do comenta EU QUERO, em **Configurações**, na parte do WhatsApp, cole o WABA ID, o Phone Number ID e o token permanente. Salve.

O painel mostra o estado do número: o número, o nome verificado, a **qualidade** (verde, amarela ou vermelha, como a Meta avalia) e o **limite de mensagens** atual.

Cada número fica ligado à conta do Instagram conectada na instalação. Um número por conta nesta primeira versão.

## Próximos passos

- [Ponte Instagram → WhatsApp](./ponte-ig-wa)
- [Criar um template](./criar-template)
- [Primeira transmissão](./primeira-transmissao)
