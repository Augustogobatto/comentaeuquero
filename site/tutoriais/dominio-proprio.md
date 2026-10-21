# Domínio próprio

Usar `ceq.sualoja.com.br` em vez do endereço que veio na instalação.

## Instalação pelo chão

1. Na página do instalador ([ia.augustogobatto.com/members/instalar](https://ia.augustogobatto.com/members/instalar)), em **Domínio próprio**, digite o domínio.
2. A página mostra o registro de DNS a criar no seu provedor de domínio:
   - Domínio inteiro (`sualoja.com.br`): registro `A` apontando para o IP da sua VPS.
   - Subdomínio (`ceq.sualoja.com.br`): registro `CNAME` apontando para o seu endereço `.perola.app`.
3. Crie o registro e espere. A VPS confere o DNS sozinha, tira o certificado HTTPS e mostra o estado na página: Aguardando o DNS, Emitindo certificado, No ar.

Não precisa de registro TXT: apontar o domínio para a sua VPS já prova que ele é seu.

O endereço `.perola.app` continua funcionando junto. Os webhooks da Meta podem continuar nele, então nada quebra na troca.

<!-- PRINT: seção "Domínio próprio" da página do instalador, com o registro de DNS e o estado "No ar" -->
<Print>Seção "Domínio próprio" da página do instalador, com o registro de DNS e o estado "No ar".</Print>

## Docker manual ou computador

1. Crie o registro DNS (`A` para o IP da VPS, ou a rota do túnel da Cloudflare com `cloudflared tunnel route dns`).
2. Ponha o domínio no Caddy (ou nginx) e recarregue. Veja o [Docker manual](/instalar/docker#_4-coloque-o-https-na-frente).
3. Troque o `BASE_URL` no `.env` e rode `docker compose up -d`.
4. Na Meta, troque o endereço nos três lugares:
   - **URL de callback do webhook** (e do webhook do WhatsApp, se usar): `https://NOVO-ENDERECO/webhook`
   - **URI de redirecionamento** em "Configurar o login da empresa": `https://NOVO-ENDERECO/auth/callback`
   - **URL da Política de Privacidade**: `https://NOVO-ENDERECO/privacy`
5. Entre no painel pelo endereço novo. O login antigo não vale no domínio novo; é só entrar de novo.

::: warning Ordem importa
Só troque na Meta depois que o endereço novo abrir no navegador com HTTPS. A Meta testa a URL do webhook na hora de salvar.
:::
