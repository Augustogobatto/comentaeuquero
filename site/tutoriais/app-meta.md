# Criar o app da Meta

Cada instalação conversa com o Instagram por um app que é seu, criado no painel de desenvolvedores da Meta. Como o app é seu e você só usa na sua própria conta, não precisa passar pela análise da Meta.

Você vai precisar de três coisas abertas: o painel da Meta, o painel do seu comenta EU QUERO e o Instagram (no navegador do computador, de preferência).

::: tip Este app é só do Instagram
O WhatsApp usa outro app, criado do zero e **não publicado**. Não adicione o WhatsApp neste. Veja [Conectar o WhatsApp](./conectar-whatsapp).
:::

::: warning App novo ou app antigo?
Desde o fim de outubro de 2026, a Meta só oferece aos apps novos o **login unificado**. Se a página do seu app diz *"A configuração da API com login do Instagram não está disponível para apps mais recentes. Seu app usa a configuração da API com login unificado"*, siga este passo a passo (precisa da versão 1.11.0 ou mais nova do comenta EU QUERO).

Se o seu app é de antes e tem **ID do app do Instagram** e **Chave secreta do app do Instagram**, ele continua funcionando como sempre: veja [Se seu app é antigo](#se-seu-app-e-antigo-login-do-instagram) no fim da página.
:::

::: info Os nomes das telas
A Meta muda nomes e posições com frequência. Os nomes abaixo são os da interface em português em novembro de 2026. Se algo estiver diferente, procure pelo termo mais próximo e [conte pra gente](https://github.com/Augustogobatto/comentaeuquero/issues).
:::

## 1. Crie o app

Antes de tudo, você precisa de um **portfólio empresarial** (o antigo Gerenciador de Negócios) com a sua conta do Instagram dentro. Sem portfólio, a opção de login unificado nem aparece. Se ainda não tem, crie em [business.facebook.com](https://business.facebook.com) e adicione a conta do Instagram lá.

1. Entre em [developers.facebook.com](https://developers.facebook.com) com a sua conta do Facebook.
2. Vá em **Meus apps** e clique em **Criar aplicativo**.
3. No caso de uso, escolha **Gerenciar mensagens e conteúdo no Instagram**.
4. Ligue o app ao seu **portfólio empresarial** quando a Meta perguntar.
5. Dê um nome. O nome **não pode conter** "Instagram", "Insta", "IG", "Meta" nem "Facebook". "Respostas da Loja Maria" serve.

<!-- PRINT: tela "Criar aplicativo" com o caso de uso "Gerenciar mensagens e conteúdo no Instagram" selecionado -->
<Print>Tela "Criar aplicativo" com o caso de uso "Gerenciar mensagens e conteúdo no Instagram" selecionado.</Print>

## 2. Crie a configuração do login

A configuração é a lista do que o seu app pede quando você conecta a conta. Ela ganha um número, o **ID da configuração** (`config_id`), que o comenta EU QUERO usa no botão Conectar Instagram.

1. No painel do app: **Casos de uso → Gerenciar mensagens e conteúdo no Instagram → Personalizar** e abra **Configuração da API com login unificado**.
2. Em **Configurar seu app**, clique em **Criar nova configuração**.
3. Na prévia da configuração, confira a **validade do token**. Escolha **Nunca** se a opção aparecer. (Se ficar 60 dias, o painel avisa quando estiver perto de vencer e você reconecta.)
4. Clique em **Editar permissões** e deixe marcadas:
   - `instagram_basic`
   - `instagram_manage_messages`
   - `instagram_manage_comments`
   - `business_management`

   As de anúncio (`ads_management`, `ads_read`) e publicação (`instagram_content_publish`) podem sair: o comenta EU QUERO não usa.
5. Clique em **Usar esta configuração**.
6. Em **URL de redirecionamento**, coloque `https://SEU-ENDERECO/auth/callback` e salve.
7. Copie o **ID da configuração**. Ele aparece na configuração e também dentro do **link de login** que a Meta mostra, depois de `config_id=`.

::: warning Não esqueça o business_management
Sem ele, a Meta autoriza, mas não entrega a conta do Instagram pro app, e o comenta EU QUERO mostra "nenhuma conta profissional do Instagram veio junto". Se a permissão não aparece em **Editar permissões**, edite a mesma configuração em **Login do Facebook para Empresas → Configurações** (adicione esse produto ao app, se pedir).
:::

<!-- PRINT: prévia da configuração com "Editar permissões" e o campo "URL de redirecionamento" -->
<Print>Prévia da configuração com "Editar permissões" e o campo "URL de redirecionamento".</Print>

## 3. Copie o ID e a chave secreta

No login unificado, o ID e a chave são os do **app geral**:

1. No painel do app: **Configurações do app → Básico**.
2. Copie o **ID do aplicativo** e a **Chave secreta do aplicativo** (clique em **Mostrar**).
3. Nessa mesma tela, no campo **URL da Política de Privacidade**, coloque `https://SEU-ENDERECO/privacy` (a sua instância já serve essa página) e salve.

No seu painel do comenta EU QUERO, em **Configurações → App da Meta**:

1. Marque **Login unificado**.
2. Cole o **ID do aplicativo**, a **Chave secreta do aplicativo** e o **ID da configuração**.
3. Salve. Vale na hora, sem reiniciar.

(Se preferir o `.env`: `META_LOGIN_MODO=facebook_login`, `META_FB_APP_ID`, `META_FB_APP_SECRET` e `META_FB_CONFIG_ID`. O que estiver no `.env` vale mais que o painel.)

A chave secreta não é opcional. É com ela que a sua instância confere que cada evento veio mesmo da Meta. Enquanto ela estiver vazia, a instância recusa todos os eventos de propósito e o painel mostra um aviso.

<!-- PRINT: Configurações → App da Meta no painel do comenta EU QUERO, com "Login unificado" marcado -->
<Print>Configurações → App da Meta no painel do comenta EU QUERO, com "Login unificado" marcado.</Print>

## 4. Vire testador do seu próprio app

Enquanto o app é só seu, a conta do Instagram precisa ter um papel nele.

1. Na página **Configuração da API com login unificado**, abra **Gerar tokens de acesso** e clique em **Adicionar conta**.
2. Convide o @ da sua conta como **Testador do Instagram**.
3. Aceite o convite no Instagram **pelo navegador do computador** (no app do celular o convite costuma não aparecer): **Configurações → Permissões do site → Apps e sites → Convites de testador → Aceitar**.

Não precisa gerar token nessa tela: o comenta EU QUERO pega o dele quando você conecta.

<!-- PRINT: convite de testador no Instagram pelo navegador -->
<Print>Convite de testador no Instagram, aberto pelo navegador.</Print>

## 5. Configure o webhook

É por aqui que a Meta avisa a sua instância de cada comentário e mensagem.

Na página **Configuração da API com login unificado**, seção **Configurar webhooks**:

- **URL de callback:** `https://SEU-ENDERECO/webhook`
- **Verificar token:** o mesmo texto do `WEBHOOK_VERIFY_TOKEN` do seu `.env` (na instalação pelo chão, o painel mostra qual é, em Configurações).

Clique em **Verificar e salvar**. Tem que dar certo na hora. Se der erro, confira se o endereço abre no navegador e se o token é idêntico, sem espaço no fim.

Depois, **marque os campos** `comments`, `live_comments`, `messages` e `messaging_postbacks`. No login unificado, a conta só recebe o que estiver marcado aqui. Quando você conectar, a instância liga a sua conta a esses campos sozinha.

<!-- PRINT: seção "Configurar webhooks" preenchida, com os quatro campos marcados -->
<Print>Seção "Configurar webhooks" preenchida, com os quatro campos marcados.</Print>

## 6. Conecte a conta

Agora [conecte o Instagram](./conectar-instagram). A tela da Meta pede o login (pode ser com o Instagram ou com o Facebook), o portfólio empresarial e a conta do Instagram.

## 7. Publique o app

No menu lateral, clique em **Publicar** e publique.

::: danger A pegadinha mais comum
Sem publicar, **os comentários podem não chegar**. As mensagens de direct até chegam, o que confunde. Publicar não exige análise da Meta para usar na sua própria conta.
:::

O app do WhatsApp é o contrário: fica **sem publicar**. Por isso são dois apps.

<!-- PRINT: botão "Publicar" no menu lateral do app e a confirmação de app publicado -->
<Print>Botão "Publicar" no menu lateral do app e a confirmação de app publicado.</Print>

## Se seu app é antigo (login do Instagram)

Vale para app criado antes do fim de outubro de 2026, que tem a página **Configuração da API com login do Instagram**. Nada muda pra você: siga como sempre.

1. **Permissões:** em **Casos de uso → Personalizar → Configuração da API com login do Instagram**, clique em **Add all required permissions**.
2. **ID e chave:** nessa página aparecem o **ID do app do Instagram** e a **Chave secreta do app do Instagram**. Use **esses**, não os do app geral. No painel do comenta EU QUERO, em **Configurações → App da Meta**, marque **Login do Instagram** e cole os dois (ou `META_APP_ID` e `META_APP_SECRET` no `.env`).
3. **Testador:** **Funções do app → Funções → Adicionar pessoas → Testador do Instagram** com o @ da sua conta, e aceite no Instagram em **Configurações → Site e apps → Convites de testador**. Sem isso, o login dá "Função de desenvolvedor é insuficiente".
4. **Webhook:** na seção **Configurar webhooks** dessa página, URL `https://SEU-ENDERECO/webhook` e o token de verificação. Aqui não precisa marcar campos: a instância assina sozinha ao conectar.
5. **Login e privacidade:** em **Configurar o login da empresa**, adicione a URI `https://SEU-ENDERECO/auth/callback`. Em **Configurações do app → Básico**, URL da Política de Privacidade `https://SEU-ENDERECO/privacy`.
6. **Publique** o app, como no passo 7.

No login do Instagram o acesso dura 60 dias e a instância renova sozinha.

## Pronto

Agora [conecte o Instagram](./conectar-instagram).
