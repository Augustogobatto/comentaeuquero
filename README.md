# comenta EU QUERO

Automação de resposta no direct do Instagram, rodando no seu servidor, com o seu app da Meta.

Alguém comenta a palavra-chave no seu post, responde seu story, comenta na sua live ou
manda a palavra na DM. A instância responde no direct com o fluxo que você montou:
mensagem, botão, link, pergunta, captura de nome e telefone, etiqueta, IA.
Sem mensalidade e sem limite de contatos.

**Código aberto, licença de uso sustentável.** Você pode usar, estudar, modificar e
instalar pros seus clientes. Não pode hospedar e revender acesso como serviço.
Veja [LICENSE.md](LICENSE.md).

<!-- PRINT: GIF de 10 a 15 s do editor de fluxo (arrastar um passo, ligar, salvar) -->
<!-- PRINT: print do painel com a lista de leads e as últimas interações -->

## O que faz

- **Gatilhos do Instagram:** comentário em post, comentário em live, resposta a story e mensagem direta.
- **Editor visual de fluxos:** passos de mensagem (com variações), botões, espera, condição, pergunta
  com captura de campo, etiqueta, chamada de webhook e resposta por IA. Métricas por etapa dentro do fluxo.
- **Resposta pública opcional** no comentário ("te mandei no direct").
- **Leads:** quem interagiu, etiquetas, campos capturados, exportação em CSV.
- **Proteções:** teto de envios por hora, fila quando a Meta limita, assinatura dos webhooks,
  login com freio de força bruta, segredos cifrados, retenção de dados configurável (LGPD).
- **WhatsApp oficial (Cloud API):** os mesmos fluxos no WhatsApp, ponte do direct pro WhatsApp
  (o lead passa o número com consentimento), templates e transmissão com relatório.

## Pra quem é

Quem vende ou capta pelo Instagram e quer o mesmo mecanismo das ferramentas de DM
automática sem pagar por contato: criadores, infoprodutores, lojas, agências e quem
instala isso pros próprios clientes.

Cada pessoa roda a própria instância, ligada ao próprio app da Meta. Por isso não passa
por análise (review) da Meta pra usar na sua conta.

## Instalação

Você precisa de uma conta Instagram profissional, Docker e um endereço HTTPS público
(um VPS pequeno, ou seu computador com Cloudflare Tunnel).

```bash
git clone https://github.com/Augustogobatto/comentaeuquero.git
cd comentaeuquero
cp .env.example .env     # preencha WEBHOOK_VERIFY_TOKEN, BASE_URL e o que mais precisar
docker compose up -d     # painel em http://localhost:8080
```

No primeiro acesso, abra `/instalar?t=<CEQ_SETUP_TOKEN>` pra criar a senha do painel
(ou defina `ADMIN_PASSWORD` no `.env`).

O resto (criar o app na Meta, webhook, publicar o app, conectar a conta) tem tutorial
passo a passo, com as pegadinhas, em **<https://comentaeuquero.com>**.
Todas as variáveis estão comentadas em [.env.example](.env.example).

## WhatsApp (opcional, API oficial)

Desde a 1.8.0 a mesma instância fala também pelo WhatsApp, pela Cloud API oficial da
Meta (nada de QR code). Sem número configurado, nada muda.

1. No mesmo app da Meta, **Adicionar produto → WhatsApp**. Anote o ID da conta do
   WhatsApp Business (WABA) e o ID do número.
2. Gere um **token permanente** de usuário do sistema com `whatsapp_business_messaging`
   e `whatsapp_business_management`.
3. Em **Configurações** do painel, seção *WhatsApp (API oficial)*: cole os dois IDs, o
   token e a chave secreta do **app geral** (Configurações do app → Básico). O webhook
   é o mesmo `/webhook`, campos `messages`, `user_preferences`,
   `phone_number_quality_update` e `business_capability_update`.

O que passa a existir: gatilho *mensagem no WhatsApp* e *clique em botão de template*,
os passos **Pedir WhatsApp** (pede o número no direct, com consentimento) e **Template
WhatsApp**, a saída "fora da janela 24h", as telas **Templates** e **Transmissões**
(fila com ritmo, limite diário e relatório de entregue/lido/respondido/custo) e a
importação de contatos com consentimento. Quem manda SAIR ou PARAR sai de todos os
envios; VOLTAR desfaz.

Variáveis novas no `.env` (opcionais): `CEQ_WA_ENVIOS_HORA` (teto de mensagens de
fluxo por hora no WhatsApp, padrão 1000) e `META_WA_APP_SECRET` (a chave do app geral,
se preferir no .env em vez do painel).

Passo a passo com prints: <https://comentaeuquero.com/tutoriais/conectar-whatsapp>.

## Conectar ao Claude (MCP)

Desde a 1.9.0 a instância tem um servidor MCP próprio em `https://SEU-DOMINIO/mcp`.
Com ele, o Claude (Claude.ai, Claude Desktop, Claude Code) ou qualquer cliente MCP opera
a sua instância por conversa: "cria um fluxo que responde 'ebook' com este link",
"quantos leads a 'mentoria' trouxe essa semana?", "manda o template da black friday pra
quem tem a etiqueta comprador". É código do próprio CEQ: nada passa por servidor de terceiros.

- **Claude.ai / Claude Desktop:** Configurações → Conectores → Adicionar conector
  personalizado, URL `https://SEU-DOMINIO/mcp`. O Claude abre a instância, você entra
  com a senha do painel e clica em Permitir (OAuth 2.1 com PKCE).
- **Claude Code e outros clientes:** gere um token em **Configurações → Conectar ao
  Claude** e use `claude mcp add --transport http ceq https://SEU-DOMINIO/mcp --header "Authorization: Bearer SEU_TOKEN"`.

São 17 ferramentas (resultados, fluxos, leads, templates, transmissões). Fluxo criado por
conversa nasce desligado. O Claude prepara a transmissão e mostra a prévia (público,
custo) com o link do painel, mas não dispara: quem envia é você, no botão Disparar.
Nenhuma ferramenta mostra token ou segredo.
Detalhes: <https://comentaeuquero.com/tutoriais/conectar-claude>.

## Stack

- Python 3.12, FastAPI e uvicorn
- SQLite (um arquivo, no volume `/data`)
- Editor de fluxo em Vue 3 + Vue Flow, compilado dentro da imagem
- Docker; imagem publicada no ghcr e assinada com cosign (keyless)
- API oficial do Instagram (login do Instagram, webhooks, private reply)

## Rodar os testes

```bash
python3 -m venv .venv
.venv/bin/pip install -r requirements-dev.txt
.venv/bin/pytest
```

Os testes não falam com a Meta: o Instagram é dublado.

## Contribuir

Issues e PRs são bem-vindos. Leia o [CONTRIBUTING.md](CONTRIBUTING.md). Pra sugerir uma
melhoria, abra uma issue com o label `sugestao`. Vulnerabilidade: não abra issue,
siga o [SECURITY.md](SECURITY.md). Histórico de versões em [CHANGELOG.md](CHANGELOG.md).

## Licença

Licença de Uso Sustentável, versão 1.0 ([LICENSE.md](LICENSE.md)). © 2026 Augusto Gobatto.
Livre pra uso próprio e pra instalar pra terceiros; proibido revender como serviço hospedado.

Feito por [Augusto Gobatto](https://instagram.com/augustogobatto).
