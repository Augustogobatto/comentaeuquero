# Criar o app da Meta

Cada instalação conversa com o Instagram por um app que é seu, criado no painel de desenvolvedores da Meta. Como o app é seu e você só usa na sua própria conta, não precisa passar pela análise da Meta.

Você vai precisar de três coisas abertas: o painel da Meta, o painel do seu comenta EU QUERO e o Instagram no celular.

::: tip Este app é só do Instagram
O WhatsApp usa outro app, criado do zero e **não publicado**. Não adicione o WhatsApp neste. Veja [Conectar o WhatsApp](./conectar-whatsapp).
:::

::: info Os nomes das telas
A Meta muda nomes e posições com frequência. Os nomes abaixo são os da interface em português em outubro de 2026. Se algo estiver diferente, procure pelo termo mais próximo e [conte pra gente](https://github.com/Augustogobatto/comentaeuquero/issues).
:::

## 1. Crie o app

1. Entre em [developers.facebook.com](https://developers.facebook.com) com a sua conta do Facebook.
2. Vá em **Meus apps** e clique em **Criar aplicativo**.
3. No caso de uso, escolha **Gerenciar mensagens e conteúdo no Instagram**.
4. No tipo, escolha **Empresa**.
5. Dê um nome. O nome **não pode conter** "Instagram", "Insta", "IG", "Meta" nem "Facebook". "Respostas da Loja Maria" serve.

<!-- PRINT: tela "Criar aplicativo" com o caso de uso "Gerenciar mensagens e conteúdo no Instagram" selecionado -->
<Print>Tela "Criar aplicativo" com o caso de uso "Gerenciar mensagens e conteúdo no Instagram" selecionado.</Print>

## 2. Adicione as permissões

1. No painel do app, vá em **Casos de uso**, clique em **Personalizar** e abra **Configuração da API com login do Instagram**.
2. Clique em **Add all required permissions**. Entram as três permissões que o app usa: perfil básico, mensagens e comentários.

<!-- PRINT: página "Configuração da API com login do Instagram" com o botão "Add all required permissions" -->
<Print>Página "Configuração da API com login do Instagram" com o botão "Add all required permissions".</Print>

## 3. Copie o ID e a chave secreta

Na mesma página aparecem o **ID do app do Instagram** e a **Chave secreta do app do Instagram**.

::: warning Use os do Instagram
O app tem dois pares de ID e chave: o do app geral (em Configurações do app → Básico) e o do Instagram (nesta página). O comenta EU QUERO usa **o do Instagram**. Com o par errado, o login dá erro e os eventos são recusados.
:::

Cole os dois no seu painel, em **Configurações → App da Meta**, e salve. Vale na hora, sem reiniciar. (Se você preferir, dá pra pôr em `META_APP_ID` e `META_APP_SECRET` no `.env`; o que estiver no `.env` vale mais que o painel.)

<!-- PRINT: onde ficam "ID do app do Instagram" e "Chave secreta do app do Instagram" na página da Meta -->
<Print>Onde ficam o "ID do app do Instagram" e a "Chave secreta do app do Instagram" na página da Meta.</Print>

A chave secreta não é opcional. É com ela que a sua instância confere que cada evento veio mesmo da Meta. Enquanto ela estiver vazia, a instância recusa todos os eventos de propósito e o painel mostra um aviso.

## 4. Vire testador do seu próprio app

Sem isso, o login dá o erro "Função de desenvolvedor é insuficiente".

1. No painel do app: **Funções do app → Funções → Adicionar pessoas**.
2. Escolha **Testador do Instagram** e digite o @ da sua conta.
3. No Instagram (app ou site): **Configurações → Site e apps → Convites de testador → Aceitar**.

<!-- PRINT: convite de testador no Instagram (Configurações → Site e apps → Convites de testador) -->
<Print>Convite de testador no Instagram, em Configurações → Site e apps → Convites de testador.</Print>

## 5. Configure o webhook

É por aqui que a Meta avisa a sua instância de cada comentário e mensagem.

Na página **Configuração da API com login do Instagram**, seção **Configurar webhooks**:

- **URL de callback:** `https://SEU-ENDERECO/webhook`
- **Verificar token:** o mesmo texto do `WEBHOOK_VERIFY_TOKEN` do seu `.env` (na instalação pelo chão, o painel mostra qual é).

Clique em **Verificar e salvar**. Tem que dar certo na hora. Se der erro, confira se o endereço abre no navegador e se o token é idêntico, sem espaço no fim.

<!-- PRINT: seção "Configurar webhooks" preenchida, com URL de callback e token de verificação -->
<Print>Seção "Configurar webhooks" preenchida, com a URL de callback e o token de verificação.</Print>

Não precisa marcar os campos do webhook (comentários, mensagens) à mão: quando você conectar a conta, a instância assina os campos que usa.

## 6. Login da empresa e política de privacidade

1. Na seção **Configurar o login da empresa**, clique em **Configurar** e adicione a URI de redirecionamento: `https://SEU-ENDERECO/auth/callback`
2. Em **Configurações do app → Básico**, no campo **URL da Política de Privacidade**, coloque `https://SEU-ENDERECO/privacy`. A sua instância já serve essa página. Salve.

<!-- PRINT: campo de URI de redirecionamento em "Configurar o login da empresa" -->
<Print>Campo de URI de redirecionamento em "Configurar o login da empresa".</Print>

## 7. Publique o app

No menu lateral, clique em **Publicar** e publique.

::: danger A pegadinha mais comum
Sem publicar, **os comentários não chegam**. As mensagens de direct até chegam, o que confunde. Publicar não exige análise da Meta para usar na sua própria conta.
:::

O app do WhatsApp é o contrário: fica **sem publicar**. Por isso são dois apps.

<!-- PRINT: botão "Publicar" no menu lateral do app e a confirmação de app publicado -->
<Print>Botão "Publicar" no menu lateral do app e a confirmação de app publicado.</Print>

## Pronto

Agora [conecte o Instagram](./conectar-instagram).
