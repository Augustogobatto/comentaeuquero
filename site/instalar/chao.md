# Instalar com o chão (1 comando)

O chão é o instalador do comenta EU QUERO. Você cola um comando numa VPS limpa e ele deixa tudo pronto: o app, o HTTPS com certificado, a senha do painel, o backup diário e a atualização automática.

::: info Liberação em etapas
O comando é gerado com um token pessoal na página do instalador, em [ia.augustogobatto.com/members/instalar](https://ia.augustogobatto.com/members/instalar). O acesso a essa página está sendo liberado aos poucos. Se você ainda não tem acesso, use o [Docker manual](./docker): o resultado é o mesmo app.
:::

## Antes de começar

- Uma VPS com **Ubuntu 22.04, Ubuntu 24.04 ou Debian 12**, processador **x86_64** e acesso de administrador (`sudo`). VPS com processador ARM (Oracle Ampere, Hetzner CAX, AWS Graviton) é recusada antes de começar.
- Pelo menos **1 GB de memória livre** e **10 GB de disco livre**.
- As portas **80 e 443 liberadas** no firewall do provedor. Sem elas o certificado HTTPS não sai. Na Hostinger, Oracle, AWS e Hetzner esse firewall fica no painel do provedor, não na VPS.
- Docker não precisa estar instalado: se faltar, o instalador instala.
- Já tem Caddy, nginx, Easypanel ou Traefik ocupando as portas 80 e 443? Acrescente `--atras-de-proxy` no fim do comando. O instalador mostra pra onde apontar o seu proxy.

## O comando

A página do instalador mostra o comando completo, já com o seu token. Ele tem este formato:

```bash
d=$(mktemp -d) && cd "$d" \
  && curl -fsSLo cosign https://github.com/sigstore/cosign/releases/download/v3.1.3/cosign-linux-amd64 \
  && echo "4629c757b7618056f8ddd7e2625ae9fdd94c0372a65049520bc7d9df9efc7f71  cosign" | sha256sum -c --quiet - \
  && chmod +x cosign \
  && curl -fsSLO https://ia.augustogobatto.com/chao/instalador.tar.gz \
  && curl -fsSLO https://ia.augustogobatto.com/chao/instalador.tar.gz.sigstore.json \
  && ./cosign verify-blob --bundle instalador.tar.gz.sigstore.json \
       --certificate-identity https://github.com/Augustogobatto/chao/.github/workflows/canal.yml@refs/heads/main \
       --certificate-oidc-issuer https://token.actions.githubusercontent.com \
       instalador.tar.gz \
  && tar xzf instalador.tar.gz \
  && sudo bash install.sh --token SEU_TOKEN
```

Copie o da página, não este: o token muda para cada instalação.

### O que esse comando faz

1. Baixa o `cosign` (a ferramenta que confere assinaturas) e confere se o arquivo é exatamente o esperado.
2. Baixa o pacote do instalador e a assinatura dele.
3. Confere que o pacote foi assinado pelo processo de publicação oficial no GitHub. Se alguém trocar o arquivo no meio do caminho, a conferência falha e nada roda.
4. Só então roda o instalador.

O instalador termina em 1 a 2 minutos e mostra um link para você criar a senha do painel. O link funciona uma vez: depois que a senha existe, ele deixa de existir.

## O que fica na sua VPS

Tudo mora em `/opt/chao`:

- O comenta EU QUERO e o banco de leads.
- As credenciais da Meta, cifradas.
- O `.env` com a chave que abre essas credenciais.
- Backup diário às 3h (horário de Brasília) em `/opt/chao/backups/`, guardando as últimas 7 cópias.
- O certificado HTTPS (Caddy).
- O agente que confere atualizações.

O seu endereço começa como `seu-nome.perola.app`. Depois dá pra [ligar um domínio seu](/tutoriais/dominio-proprio).

Os seus leads e mensagens não passam por nenhum servidor além do seu. Na instalação, a central recebe o IP, o nome e o sistema da VPS, para criar o seu endereço. Depois disso o agente informa só o básico: versão, se está no ar e contagens. Nenhum dado de lead, nenhuma mensagem, nenhum token da Meta.

## Atualização

O agente confere a cada 10 minutos se saiu versão nova. Ele só aceita uma versão assinada pelo processo de publicação oficial e, se a versão nova não subir direito, volta sozinho para a anterior.

## Comandos úteis

```bash
# retomar uma instalação que parou no meio, ou reaplicar a configuração
sudo bash /opt/chao/install.sh --modo reparar

# atualizar o próprio instalador e o agente
sudo bash /opt/chao/install.sh --modo atualizar

# ver os logs
cd /opt/chao && docker compose logs ceq agente
```

## Próximo passo

[Crie o app da Meta](/tutoriais/app-meta).
