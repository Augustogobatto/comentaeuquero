# Instalar no computador com Cloudflare Tunnel

Dá pra rodar no seu próprio computador (Mac, Windows ou Linux) e expor para a internet com um túnel grátis da Cloudflare. Bom para testar antes de pagar uma VPS. Para uso de verdade, o computador precisa ficar ligado e conectado o tempo todo: desligou, as respostas param.

## 1. Instale o Docker e o cloudflared

- **Docker Desktop:** [docker.com/get-started](https://www.docker.com/get-started/). Abra e deixe rodando.
- **cloudflared:** no Mac, `brew install cloudflared`. No Windows e no Linux, siga a [página de downloads da Cloudflare](https://developers.cloudflare.com/cloudflare-one/connections/connect-networks/downloads/).

## 2. Crie a pasta e os arquivos

Numa pasta qualquer (por exemplo `comentaeuquero` nos seus Documentos), crie o `docker-compose.yml` e o `.env` exatamente como no passo 2 do [Docker manual](./docker#_2-crie-a-pasta-e-os-dois-arquivos). Deixe o `BASE_URL` vazio por enquanto.

Suba:

```bash
docker compose up -d
```

Abra `http://localhost:8080` no navegador. A tela de login aparece. Enquanto o `BASE_URL` estiver vazio, o login funciona por `http://localhost`. Depois que você preencher o `BASE_URL` com um endereço `https`, entre sempre por esse endereço: o painel recusa senha por HTTP para ela não trafegar sem criptografia.

## 3. Teste rápido: túnel temporário

```bash
cloudflared tunnel --url http://localhost:8080
```

Ele mostra um endereço `https://alguma-coisa.trycloudflare.com`. Coloque esse endereço no `BASE_URL` do `.env` e rode:

```bash
docker compose up -d
```

::: warning O endereço temporário muda
Toda vez que o `cloudflared` reinicia, o endereço `trycloudflare.com` é outro, e você teria que trocar o webhook na Meta. Serve para testar. Para usar de verdade, faça o túnel fixo abaixo.
:::

## 4. Uso contínuo: túnel com nome e domínio

Precisa de um domínio na sua conta da Cloudflare (o plano grátis serve).

```bash
cloudflared tunnel login                    # abre o navegador para autorizar
cloudflared tunnel create ceq               # cria o túnel e mostra o ID
cloudflared tunnel route dns ceq ceq.seudominio.com.br
```

Crie o arquivo `~/.cloudflared/config.yml` (troque o ID e o caminho pelo que o comando `create` mostrou):

```yaml
tunnel: ceq
credentials-file: /Users/voce/.cloudflared/ID-DO-TUNEL.json

ingress:
  - hostname: ceq.seudominio.com.br
    service: http://localhost:8080
  - service: http_status:404
```

Rode:

```bash
cloudflared tunnel run ceq
```

Ponha `BASE_URL=https://ceq.seudominio.com.br` no `.env` e rode `docker compose up -d` de novo.

Para o túnel subir sozinho quando o computador ligar, instale como serviço: `sudo cloudflared service install` (veja a [documentação da Cloudflare](https://developers.cloudflare.com/cloudflare-one/connections/connect-networks/configure-tunnels/local-management/as-a-service/) para o seu sistema).

## Próximo passo

[Crie o app da Meta](/tutoriais/app-meta).
