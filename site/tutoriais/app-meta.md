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
3. Dê um nome. O nome **não pode conter** "Instagram", "Insta", "IG", "Meta" nem "Facebook". "Respostas da Loja Maria" serve.
4. No caso de uso, filtre por **Gerenciamento de conteúdo** e escolha **Gerenciar mensagens e conteúdo no Instagram**.
5. Ligue o app ao seu **portfólio empresarial** e clique em **Criar aplicativo**. A Meta pode pedir a senha do Facebook de novo.

<!-- PRINT: tela "Criar aplicativo" com o caso de uso "Gerenciar mensagens e conteúdo no Instagram" selecionado -->
<Print>Tela "Criar aplicativo" com o caso de uso "Gerenciar mensagens e conteúdo no Instagram" selecionado.</Print>

## 2. Crie a configuração do login

A configuração é a lista do que o seu app pede quando você conecta a conta. Ela ganha um número, o **ID da configuração** (`config_id`), que o comenta EU QUERO usa no botão Conectar Instagram.

1. No painel do app, clique em **Personalizar o caso de uso "Gerenciar mensagens e conteúdo no Instagram"**. Abre a página **API setup with Unified login**, com o aviso de que o login do Instagram não está disponível pra apps novos. É aqui mesmo.
2. Em **1. Configure seu app**, clique em **Criar nova configuração** e depois em **Criar do modelo**. O modelo já vem com token de usuário do sistema que **nunca expira** e as permissões certas. Não precisa mexer.
3. Em **URL de redirecionamento**, coloque `https://SEU-ENDERECO/auth/callback` e clique em **Salvar**.
4. Copie o **Identificação da configuração** (o número que aparece embaixo de "API do Instagram (login unificado)").

<!-- PRINT: configuração criada, com o número da configuração e a URL de redirecionamento salva -->
<Print>Configuração criada, com o número da configuração e a URL de redirecionamento salva.</Print>

## 3. Copie o ID e a chave secreta

No login unificado, o ID e a chave são os do **app geral**:

1. No painel do app: **Configurações do app → Básico**.
2. Copie o **ID do Aplicativo** e a **Chave Secreta do Aplicativo** (clique em **Mostrar**; a Meta pede a senha do Facebook).
3. Nessa mesma tela, preencha **URL da Política de Privacidade** com `https://SEU-ENDERECO/privacy` (a sua instância já serve essa página), escolha uma **Categoria** (Mensagens serve) e clique em **Salvar alterações**. Sem isso o app não publica.

No seu painel do comenta EU QUERO, em **Configurações → App da Meta**:

1. Marque **Login unificado**.
2. Cole o **ID do aplicativo**, a **Chave secreta do aplicativo** e o **ID da configuração**.
3. Salve. Vale na hora, sem reiniciar.

(Se preferir o `.env`: `META_LOGIN_MODO=facebook_login`, `META_FB_APP_ID`, `META_FB_APP_SECRET` e `META_FB_CONFIG_ID`. O que estiver no `.env` vale mais que o painel.)

A chave secreta não é opcional. É com ela que a sua instância confere que cada evento veio mesmo da Meta. Enquanto ela estiver vazia, a instância recusa todos os eventos de propósito e o painel mostra um aviso.

<!-- PRINT: Configurações → App da Meta no painel do comenta EU QUERO, com "Login unificado" marcado -->
<Print>Configurações → App da Meta no painel do comenta EU QUERO, com "Login unificado" marcado.</Print>

## 4. Configure o webhook

É por aqui que a Meta avisa a sua instância de cada comentário e mensagem.

Na página **API setup with Unified login**, seção **3. Configurar webhooks**:

- **URL de callback:** `https://SEU-ENDERECO/webhook`
- **Verificar token:** o mesmo texto do `WEBHOOK_VERIFY_TOKEN` do seu `.env` (na instalação pelo chão, o painel mostra qual é, em Configurações).

Clique em **Verificar e salvar**. Tem que dar certo na hora. Se der erro, confira se o endereço abre no navegador e se o token é idêntico, sem espaço no fim.

Depois, **assine os campos** `comments`, `live_comments`, `messages` e `messaging_postbacks`. No login unificado, a conta só recebe o que estiver assinado aqui. Quando você conectar, a instância liga a sua conta a esses campos sozinha.

<!-- PRINT: seção "Configurar webhooks" preenchida, com os quatro campos assinados -->
<Print>Seção "Configurar webhooks" preenchida, com os quatro campos assinados.</Print>

## 5. Publique o app

No menu lateral, clique em **Publicar** e depois no botão **Publicar** no canto de baixo. Não pede análise da Meta.

::: danger A pegadinha mais comum
Sem publicar, **nada de quem não tem papel no app chega**: o comentário de um seguidor some sem erro nenhum. Publique antes de testar.
:::

O app do WhatsApp é o contrário: fica **sem publicar**. Por isso são dois apps.

<!-- PRINT: botão "Publicar" no menu lateral do app e o selo "Publicado" -->
<Print>Botão "Publicar" no menu lateral do app e o selo "Publicado".</Print>

## 6. Libere as mensagens no Instagram

No login unificado, a Meta só entrega a DM e o clique em botão se a própria conta liberar. **Sem isso, o comenta EU QUERO responde o comentário, mas não recebe a resposta da pessoa nem o clique no botão.**

No **app do Instagram no celular** (no navegador essa opção não existe), logado na conta que você vai conectar:

**Perfil → ☰ → Configurações e privacidade → Mensagens e respostas ao story → Ferramentas conectadas → Permitir acesso às mensagens → ligar**

<!-- PRINT: tela "Ferramentas conectadas" no app do Instagram com "Permitir acesso às mensagens" ligado -->
<Print>Tela "Ferramentas conectadas" no app do Instagram com "Permitir acesso às mensagens" ligado.</Print>

## 7. Conecte a conta

Agora [conecte o Instagram](./conectar-instagram). Na tela da Meta, escolha o **portfólio que é dono da conta do Instagram** e marque a conta.

::: warning Portfólio dono, não portfólio compartilhado
Se a conta do Instagram só está **compartilhada** com o portfólio que você escolher, a Meta recusa com *"The following business assets were not granted the requested permissions"*. Pra saber quem é o dono: em [business.facebook.com](https://business.facebook.com) → **Configurações → Contas do Instagram**, a conta mostra "Isto pertence a ...". Escolha esse portfólio na tela de conectar.
:::

## Se seu app é antigo (login do Instagram)

Vale para app criado antes do fim de outubro de 2026, que tem a página **Configuração da API com login do Instagram**. Nada muda pra você: siga como sempre.

1. **Permissões:** em **Casos de uso → Personalizar → Configuração da API com login do Instagram**, clique em **Add all required permissions**.
2. **ID e chave:** nessa página aparecem o **ID do app do Instagram** e a **Chave secreta do app do Instagram**. Use **esses**, não os do app geral. No painel do comenta EU QUERO, em **Configurações → App da Meta**, marque **Login do Instagram** e cole os dois (ou `META_APP_ID` e `META_APP_SECRET` no `.env`).
3. **Testador:** **Funções do app → Funções → Adicionar pessoas → Testador do Instagram** com o @ da sua conta, e aceite no Instagram em **Configurações → Site e apps → Convites de testador**. Sem isso, o login dá "Função de desenvolvedor é insuficiente".
4. **Webhook:** na seção **Configurar webhooks** dessa página, URL `https://SEU-ENDERECO/webhook` e o token de verificação. Aqui não precisa marcar campos: a instância assina sozinha ao conectar.
5. **Login e privacidade:** em **Configurar o login da empresa**, adicione a URI `https://SEU-ENDERECO/auth/callback`. Em **Configurações do app → Básico**, URL da Política de Privacidade `https://SEU-ENDERECO/privacy`.
6. **Publique** o app, como no passo 5.

No login do Instagram o acesso dura 60 dias e a instância renova sozinha.

## Pronto

Agora [conecte o Instagram](./conectar-instagram).
