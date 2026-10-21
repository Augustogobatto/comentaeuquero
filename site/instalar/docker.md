# Instalar com Docker (manual)

Este caminho monta a mesma instalação à mão: um container do comenta EU QUERO e um proxy com HTTPS na frente. Leva uns 15 minutos numa VPS com Docker.

## 1. Prepare a máquina

Numa VPS Ubuntu ou Debian:

```bash
curl -fsSL https://get.docker.com | sudo sh
docker compose version   # tem que responder com a versão
```

Precisa de um subdomínio apontando para o IP da VPS (registro `A`), por exemplo `ceq.seudominio.com.br`. Se não tiver domínio, veja [Computador + Cloudflare Tunnel](./computador), que funciona igual numa VPS.

## 2. Crie a pasta e os dois arquivos

```bash
sudo mkdir -p /opt/ceq && cd /opt/ceq
```

**`docker-compose.yml`**

```yaml
services:
  ceq:
    image: ghcr.io/augustogobatto/comentaeuquero:estavel
    ports:
      - "127.0.0.1:8080:8080"
    env_file: .env
    volumes:
      - ceq_data:/data
    restart: unless-stopped

volumes:
  ceq_data:
```

A imagem é pública: não precisa de `docker login`. A tag `:estavel` aponta sempre para a última versão final. Se preferir fixar uma versão, troque por `:1.7.3` (veja as versões no [GitHub](https://github.com/Augustogobatto/comentaeuquero)). Não use `:latest`: ela parou na 1.6.9.

O `127.0.0.1:` na frente da porta é de propósito. O app só escuta de dentro da máquina, e quem fala com a internet é o proxy com HTTPS. Sem isso o painel ficaria aberto em `http://SEU-IP:8080`, com a senha trafegando sem criptografia.

**`.env`**

```ini
# endereço público, com https e sem barra no fim
BASE_URL=https://ceq.seudominio.com.br

# invente um texto qualquer; você vai colar o mesmo valor na Meta
WEBHOOK_VERIFY_TOKEN=troque-por-um-texto-seu

# senha do painel (mínimo 8 caracteres)
ADMIN_PASSWORD=troque-por-uma-senha-forte

# chave que cifra as credenciais da Meta salvas pelo painel
CEQ_ENCRYPTION_KEY=

# ID e chave secreta do app do Instagram (pode deixar vazio e preencher no painel)
META_APP_ID=
META_APP_SECRET=
```

Gere a `CEQ_ENCRYPTION_KEY` com:

```bash
python3 -c "import base64, os; print(base64.urlsafe_b64encode(os.urandom(32)).decode())"
```

Cole o resultado depois do `=`. **Guarde essa chave fora da VPS** (num gerenciador de senhas). Sem ela, um backup restaurado não consegue abrir as credenciais salvas pelo painel.

A lista completa de variáveis está em [Configuração (.env)](/referencia/env).

Proteja o arquivo:

```bash
sudo chmod 600 .env
```

## 3. Suba

```bash
sudo docker compose up -d
curl -s localhost:8080/health
```

Tem que responder `{"ok":true,...}`.

## 4. Coloque o HTTPS na frente

O jeito mais simples é o [Caddy](https://caddyserver.com/docs/install), que tira o certificado sozinho. Depois de instalar, deixe o `/etc/caddy/Caddyfile` assim:

```txt
ceq.seudominio.com.br {
    reverse_proxy 127.0.0.1:8080
}
```

```bash
sudo systemctl reload caddy
```

Abra `https://ceq.seudominio.com.br`. A tela de login tem que aparecer.

::: warning Firewall do provedor
O certificado só sai com as portas 80 e 443 liberadas. Na Hostinger, Oracle, AWS e Hetzner, esse firewall fica no painel do provedor.
:::

::: details Usa nginx em vez de Caddy?
Encaminhe para `127.0.0.1:8080` e mande os cabeçalhos de origem. O painel só aceita login por HTTPS e confere isso pelo `X-Forwarded-Proto`:

```nginx
location / {
    proxy_pass http://127.0.0.1:8080;
    proxy_set_header Host $host;
    proxy_set_header X-Forwarded-Proto $scheme;
    proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
    proxy_set_header X-Real-IP $remote_addr;
}
```

O certificado sai com `certbot --nginx`.
:::

## 5. Atualizar

```bash
cd /opt/ceq
sudo docker compose pull
sudo docker compose up -d
```

O banco fica no volume `ceq_data` e não é tocado na atualização. Antes de atualizar, [faça um backup](/tutoriais/backup-e-atualizacao).

## Próximo passo

[Crie o app da Meta](/tutoriais/app-meta).
