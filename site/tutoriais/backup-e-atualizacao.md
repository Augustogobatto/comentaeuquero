# Backup e atualização

Tudo que importa mora num arquivo só: o banco SQLite, com leads, fluxos, etiquetas, campos, histórico e credenciais. Mais uma chave no `.env`.

## O que guardar

1. **O banco.** Baixe pelo painel ou pela linha de comando (abaixo).
2. **A `CEQ_ENCRYPTION_KEY` do `.env`.** As credenciais que você salvou pelo painel (chave secreta do app, token do WhatsApp) ficam cifradas no banco com essa chave. Banco sem a chave = você vai precisar colar as credenciais de novo.

Guarde os dois fora do servidor, em lugares diferentes. O backup tem o acesso da sua conta do Instagram dentro: trate como senha.

## Baixar o backup

**Pelo painel:** **Configurações → Backup → Baixar backup do banco**. Sai um arquivo `comentaeuquero-backup.db`.

A cópia é feita com o app rodando, sem parar nada, e não leva as sessões de login do painel.

**Instalação pelo chão:** além do botão, a VPS faz um backup por dia às 3h (horário de Brasília) em `/opt/chao/backups/`, mantendo os últimos 7. Esse backup fica na própria VPS: se ela sumir, ele vai junto. Baixe uma cópia de vez em quando.

## Restaurar

Na pasta do `docker-compose.yml` (no Docker manual, `/opt/ceq`; no chão, `/opt/chao`), com o arquivo `comentaeuquero-backup.db` nela:

```bash
docker compose stop ceq
docker compose run --rm --no-deps -v "$PWD":/b --entrypoint sh ceq -c \
  "cp /b/comentaeuquero-backup.db /data/comentaeuquero.db && rm -f /data/comentaeuquero.db-wal /data/comentaeuquero.db-shm"
docker compose up -d
```

Confira que o `.env` tem a mesma `CEQ_ENCRYPTION_KEY` de quando o backup foi feito.

::: tip Faça um teste
Restaure uma vez num computador, antes de precisar. Backup que nunca foi testado não é backup.
:::

## Atualizar

**Instalação pelo chão:** automática. O agente confere a cada 10 minutos, só aceita versão assinada pelo processo oficial de publicação e volta para a anterior se a nova não subir.

**Docker manual:**

```bash
cd /opt/ceq
sudo docker compose pull
sudo docker compose up -d
```

Com a tag `:estavel`, isso pega a última versão final. Com uma versão fixa (`:1.7.3`), troque o número no `docker-compose.yml` antes do `pull`.

O banco é atualizado sozinho quando a versão nova sobe. As mudanças de banco só acrescentam; não apagam dado.

## Conferir a versão

Logado no painel, abra `https://SEU-ENDERECO/health`. O campo `versao` mostra a versão rodando.

## Levar embora

O sistema é seu. Para mudar de servidor: baixe o backup, copie o `.env`, suba a instalação nova, restaure e atualize o `BASE_URL` e as URLs na Meta, se o endereço mudou ([domínio próprio](./dominio-proprio) explica quais).
