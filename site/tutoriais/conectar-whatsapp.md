# Conectar o WhatsApp

O comenta EU QUERO usa a **WhatsApp Cloud API**, a API oficial da Meta. Nada de QR code nem de WhatsApp Web automatizado: isso viola os termos do WhatsApp e derruba números.

O WhatsApp usa um **app da Meta só pra ele**, separado do app do Instagram. Leva uns 30 minutos.

::: info Os nomes das telas
Os nomes abaixo são os da interface da Meta em português em outubro de 2026. Se algo estiver diferente, procure pelo termo mais próximo e [conte pra gente](https://github.com/Augustogobatto/comentaeuquero/issues).
:::

## O que você vai juntar

Quatro informações, que vão para o painel em **Configurações → WhatsApp (API oficial)**:

| Dado | O que é | Onde achar |
|---|---|---|
| **WABA ID** | O ID da sua conta do WhatsApp Business na Meta | Configuração da API, no app do WhatsApp |
| **Phone Number ID** | O ID do número (não é o número de telefone) | Mesma página |
| **Token permanente** | A chave que deixa a instância enviar pelo número, sem vencer | Usuário do sistema, no portfólio empresarial |
| **Chave secreta do app** | Confere que cada evento veio mesmo da Meta | Configurações do app → Básico, no app do WhatsApp |

Tudo fica cifrado no banco.

## Antes de começar

- Um número que **não esteja em uso** no app WhatsApp ou WhatsApp Business. Se estiver, apague a conta do app nesse número antes. Um chip novo é o caminho mais simples.
- Um número que **não esteja conectado ao ManyChat** nem a outra plataforma de WhatsApp. Número ligado a outra ferramenta pode recusar todo envio pelo seu app, mesmo com tudo certo. Use outro número ou desconecte da ferramenta antes.
- Um **portfólio empresarial** (Gerenciador de Negócios) na Meta. Se não tiver, a Meta cria um no processo.
- Um **cartão de crédito** cadastrado na conta do WhatsApp. Sem cartão, responder quem te chamou funciona, mas template e transmissão não saem. Veja [quanto custa](/faq#quanto-custa-cada-mensagem-de-whatsapp).

## 1. Crie um app novo para o WhatsApp

1. Em [developers.facebook.com](https://developers.facebook.com), vá em **Meus apps** e clique em **Criar aplicativo**.
2. No caso de uso, escolha **Conectar-se com clientes pelo WhatsApp**.
3. Ligue o app ao seu **portfólio empresarial**. O assistente cria a conta do WhatsApp Business (WABA).
4. Dê um nome. O nome **não pode conter** "WhatsApp", "Meta", "Facebook" nem "Instagram": a Meta bloqueia. "CEQ Mensagens" serve.

<!-- PRINT: tela "Criar aplicativo" com o caso de uso "Conectar-se com clientes pelo WhatsApp" selecionado -->
<Print>Tela "Criar aplicativo" com o caso de uso "Conectar-se com clientes pelo WhatsApp" selecionado.</Print>

::: danger Não publique este app
Deixe o app do WhatsApp **não publicado** (modo desenvolvimento). Assim ele envia pelo número da sua empresa sem passar pela Análise do App.

Um app **publicado** precisa de acesso avançado a `whatsapp_business_messaging`, que só vem com a Análise do App. Sem isso (aparece "Pronto para teste"), a Meta recusa todo envio com o erro **"Application does not have permission for this action"** (código 10).

Por isso não reaproveite o app do Instagram: ele precisa ficar publicado, e o do WhatsApp não.
:::

## 2. Adicione o seu número

1. No caso de uso do WhatsApp, abra **Configuração da API**.
2. A Meta já oferece um **número de teste**, que só manda mensagem para até 5 números que você cadastrar. Bom para o primeiro teste.
3. Para o número de verdade, clique em **Adicionar número de telefone**, informe o nome de exibição (o nome que aparece para os clientes) e confirme o código por SMS ou ligação.

Nessa mesma página aparecem o **Phone Number ID** e o **WhatsApp Business Account ID** (o WABA ID). Copie os dois.

O nome de exibição passa por revisão da Meta. Se for rejeitado, o número continua enviando; corrija com calma.

<!-- PRINT: página "Configuração da API" do WhatsApp mostrando Phone Number ID e WhatsApp Business Account ID -->
<Print>Página "Configuração da API" do WhatsApp mostrando o Phone Number ID e o WhatsApp Business Account ID.</Print>

## 3. Cadastre o cartão

Em [business.facebook.com/billing_hub](https://business.facebook.com/billing_hub), adicione uma forma de pagamento à conta do WhatsApp. Sem ela, template e transmissão não saem.

## 4. Crie o token permanente

O token que aparece na Configuração da API vence em 24 horas. A instância precisa de um token de **usuário do sistema**, que não vence. Faça na ordem abaixo: pular um passo dá erro.

1. Abra [business.facebook.com/settings](https://business.facebook.com/settings) no portfólio do app.
2. Vá em **Usuários → Usuários do sistema** e clique em **Adicionar**. Dê um nome ("ceq") e a função **Administrador**.
3. **Atribua o app.** No usuário, clique em **⋯ → Atribuir ativos → Apps**, escolha o app do WhatsApp e marque **controle total**. Sem isso, o **Gerar token** mostra "Nenhuma permissão disponível".
4. **Atribua a conta do WhatsApp.** Vá em **Contas → Contas de mensagens** (ou **Contas do WhatsApp**), abra a sua WABA, clique em **Atribuir pessoas**, escolha o usuário do sistema e marque **controle total**. Atribuir só pela lista de Contas do WhatsApp, sem passar por aqui, não basta.
5. Volte ao usuário do sistema e clique em **Gerar token**:
   - Escolha o app do WhatsApp.
   - Validade: **Nunca**.
   - Permissões: as três que começam com `whatsapp_business_` (`whatsapp_business_messaging`, `whatsapp_business_management` e `whatsapp_business_manage_events`).
6. Copie o token. Ele só aparece uma vez.

<!-- PRINT: "Usuários do sistema" com o botão "Gerar token" e as permissões whatsapp_business_* marcadas -->
<Print>"Usuários do sistema" com o botão "Gerar token" e as permissões whatsapp_business_* marcadas.</Print>

::: danger Trate o token como senha
Quem tem esse token manda mensagem pelo seu número. Não cole em chat, e-mail nem print. Ele vai direto para o painel, que guarda cifrado. Se vazar, gere outro na mesma tela e revogue o antigo.
:::

## 5. Copie a chave secreta do app

1. No app do WhatsApp, vá em **Configurações do app → Básico**.
2. Em **Chave secreta do aplicativo**, clique em **Mostrar**. A Meta pede a sua senha do Facebook.
3. Copie. São **32 caracteres**, letras e números.

É uma chave diferente da do Instagram, porque o app é outro.

## 6. Webhook do WhatsApp

O app do WhatsApp aponta para o mesmo endereço do Instagram.

1. No caso de uso do WhatsApp, abra **Configuração** (webhooks).
2. **URL de callback:** `https://SEU-ENDERECO/webhook`. **Verificar token:** o mesmo do Instagram. **Verificar e salvar**.
3. Em **Campos do webhook**, assine **messages**. É por ele que chegam as mensagens recebidas e os avisos de entregue, lido e falhou.

<!-- PRINT: configuração de webhook do WhatsApp com o campo "messages" assinado -->
<Print>Configuração de webhook do WhatsApp com o campo "messages" assinado.</Print>

## 7. Cole no painel

No painel do comenta EU QUERO, em **Configurações → WhatsApp (API oficial)**, cole o WABA ID, o Phone Number ID, o token permanente e a chave secreta do app. Salve.

::: warning Cole uma vez só
Clique no campo, cole **uma vez** e salve. Colar duas vezes gruda os dois tokens e a Meta responde "token malformado". Na dúvida, apague tudo e cole de novo.
:::

O painel mostra o estado do número: o número, o nome verificado, a **qualidade** (alta, média ou baixa, como a Meta avalia) e o **limite de mensagens** atual.

Cada número fica ligado à conta do Instagram conectada na instalação. Um número por conta nesta versão.

## 8. Teste de verdade

"Ligado" no painel não prova que o número envia. Faça o teste:

1. Crie (ou use) um fluxo com gatilho **mensagem no WhatsApp** e uma palavra-chave.
2. Do seu **celular pessoal**, mande essa palavra para o número da empresa.
3. A resposta tem que chegar no seu celular em segundos.

Chegou? Pronto. Não chegou? Veja abaixo.

## Deu erro?

### "Application does not have permission for this action" (código 10)

Na ordem do mais comum:

1. **O app está publicado.** Crie um app novo e não publique (passo 1). Não dá pra "despublicar" o do Instagram, e ele precisa ficar publicado.
2. **O número está em outra ferramenta** (ManyChat ou outra plataforma que conectou o número por ela). Desconecte lá ou use outro número.
3. **O token é de outro app.** Gere de novo escolhendo o app do WhatsApp.

### "Nenhuma permissão disponível" ao gerar o token

Falta atribuir o **app** ao usuário do sistema, com controle total (passo 4, item 3).

### O token não envia, mesmo gerado

Confira se a conta foi atribuída em **Contas de mensagens → Atribuir pessoas**, com controle total (passo 4, item 4).

### "Token malformado"

O token foi colado duas vezes ou com espaço. Apague o campo, cole uma vez e salve.

### O cliente me chama e eu respondo, mas template não sai

Falta forma de pagamento na conta do WhatsApp (passo 3). Conversa iniciada pelo cliente é grátis e funciona sem cartão por 24 horas; mensagem iniciada por você, não.

### Chegou a mensagem no painel, mas não chega resposta

Confira o fluxo (está ligado? a palavra bate?) e a **Atividade recente**. Se aparecer erro da Meta ali, procure o código nesta lista.

## Próximos passos

- [Ponte Instagram → WhatsApp](./ponte-ig-wa)
- [Criar um template](./criar-template)
- [Primeira transmissão](./primeira-transmissao)
