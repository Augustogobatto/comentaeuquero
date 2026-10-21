# Configuração (.env)

Todas as variáveis que a instância lê. Depois de mudar o `.env`, rode `docker compose up -d` para valer. Na instalação pelo chão, o arquivo fica em `/opt/chao/.env`.

## Essenciais

| Variável | Padrão | Para quê |
|---|---|---|
| `BASE_URL` | vazio | Endereço público com `https`, sem barra no fim. Monta o endereço de retorno do login do Instagram e liga o cookie seguro. |
| `WEBHOOK_VERIFY_TOKEN` | `troque-este-token` | Texto que você inventa e cola igual no webhook da Meta. Troque o padrão. |
| `ADMIN_PASSWORD` | vazio | Senha do painel. Se estiver preenchida, vale mais que a senha criada no primeiro acesso. |
| `CEQ_ENCRYPTION_KEY` | vazio | Chave que cifra as credenciais salvas pelo painel. Sem ela, ficam sem cifra e o painel avisa. [Como gerar](/instalar/docker#_2-crie-a-pasta-e-os-dois-arquivos). |
| `META_APP_ID` | vazio | ID do app do Instagram. Se preenchido, vale mais que o do painel. |
| `META_APP_SECRET` | vazio | Chave secreta do app do Instagram. Sem ela (aqui ou no painel), todos os eventos são recusados. |

## IA

| Variável | Padrão | Para quê |
|---|---|---|
| `AI_API_KEY` | vazio | Chave da API da Anthropic, para o passo Resposta com IA. |
| `AI_MODEL` | `claude-haiku-4-5-20251001` | Modelo padrão do passo de IA. |
| `CEQ_IA_POR_LEAD_HORA` | `10` | Quantas respostas de IA a mesma pessoa pode gerar por hora. Passou disso, recebe o texto reserva. |

## Envio

| Variável | Padrão | Para quê |
|---|---|---|
| `CEQ_ENVIOS_HORA` | `180` | Teto inicial de envios por hora. Depois de ajustado em Configurações (de 10 a 750), vale o do painel. |

## Retenção de dados

| Variável | Padrão | Para quê |
|---|---|---|
| `RETENCAO_LEADS_DIAS` | vazio (guarda tudo) | Apaga o lead parado há mais que esse número de dias, com etiquetas e campos. Roda uma vez por dia. |
| `RETENCAO_EVENTOS_DIAS` | vazio (guarda tudo) | Apaga o histórico técnico mais velho que isso. |

## Alertas

| Variável | Padrão | Para quê |
|---|---|---|
| `ALERTA_TELEGRAM_TOKEN` | vazio | Token de um bot do Telegram que avisa quando a Meta segura os envios. O que for salvo em Configurações vale mais. |
| `ALERTA_TELEGRAM_CHAT` | vazio | O seu ID no Telegram (o @userinfobot informa). |

## Segurança e acesso

| Variável | Padrão | Para quê |
|---|---|---|
| `CEQ_LOGIN_FALHAS_JANELA` | `30` | Senhas erradas, somando todos os IPs, aceitas em 10 minutos antes de travar o login. |
| `CEQ_PERMITE_HTTP` | vazio | `1` libera o login por HTTP. Só para proxy que não envia `X-Forwarded-Proto`. Não use sem necessidade. |
| `CEQ_SETUP_TOKEN` | vazio | Usado pelo instalador: libera a página `/instalar?t=` para criar a senha no primeiro acesso. |
| `CEQ_MCP_REDIRECTS` | vazio | Hosts extras (separados por vírgula) pra onde o login OAuth do conector MCP pode devolver o acesso. Por padrão só `claude.ai`, `claude.com` e `localhost`. Ver [MCP](./mcp). |

## Instalação e licença

| Variável | Padrão | Para quê |
|---|---|---|
| `CLUB_TOKEN` | vazio | Token da instalação pelo chão (ou de membro do Push Club). Liga a instância à central de atualizações. Nunca bloqueia nada: só muda o aviso do painel. |
| `CHAO_URL` | `https://ia.augustogobatto.com` | Central do chão. |
| `CHAO_VERSAO` | vazio | Versão do instalador, gravada por ele. |
| `ACTIVATION_URL` | `https://ia.augustogobatto.com/api/ceq/validate` | Endereço de validação de token antigo de membro. |
| `DATA_DIR` | `/data` na imagem | Pasta do banco (`comentaeuquero.db`) e das fotos de perfil. |

## WhatsApp

As credenciais do WhatsApp (WABA ID, Phone Number ID e token permanente) entram pelo painel e ficam cifradas com a `CEQ_ENCRYPTION_KEY`. Se o canal ganhar variáveis próprias no lançamento, elas entram nesta página.
