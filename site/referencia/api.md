# API

A instância expõe rotas HTTP. As de `/api/` são as mesmas que o editor e o painel usam.

## Autenticação

Por enquanto, a API usa o **cookie de sessão do painel** (`ceq_session`), o mesmo do login. Não existe token de API separado.

- Sem senha configurada na instância: `403`.
- Sem sessão válida: `401`.

Para chamar de um script, faça login com `POST /login` (campo `senha`) por HTTPS, guarde o cookie e mande nas próximas chamadas:

```bash
curl -s -c cookie.txt -d "senha=SUA_SENHA" https://SEU-ENDERECO/login -o /dev/null
curl -s -b cookie.txt https://SEU-ENDERECO/api/flows
```

Datas são `AAAA-MM-DD`. O parâmetro `tz` é o fuso em horas, de -14 a 14 (padrão -3, Brasília).

## Fluxos

| Método | Rota | O que faz |
|---|---|---|
| GET | `/api/flows` | Lista os fluxos, com número de passos e gatilhos |
| POST | `/api/flows` | Cria um fluxo (`name`, `graph`, `entry_node`, `active`). Devolve `{id}` |
| GET | `/api/flows/{id}` | Fluxo, gatilhos e avisos de validação |
| PUT | `/api/flows/{id}` | Salva. Devolve `{ok, avisos}` |
| DELETE | `/api/flows/{id}` | Apaga o fluxo e os gatilhos dele |
| GET | `/api/flows/{id}/export` | JSON para importar em outra instância |
| POST | `/api/flows/import` | Importa um fluxo exportado. Entra desligado |
| GET | `/api/flows/{id}/metricas?periodo=tudo\|7\|30` | Funil: acionaram, entregues, leram, avançaram |

## Gatilhos

| Método | Rota | O que faz |
|---|---|---|
| POST | `/api/flows/{id}/triggers` | Cria um gatilho (`type`, `keywords`, `media_ids`, `public_replies`, `active`) |
| PATCH | `/api/triggers/{id}` | Liga ou desliga (`{active}`) |
| DELETE | `/api/triggers/{id}` | Apaga |

## Leads e dados

| Método | Rota | O que faz |
|---|---|---|
| GET | `/api/leads?desde=&ate=&campo=&keyword=&limit=200&offset=` | Leads com os campos preenchidos |
| GET | `/api/campos?desde=&ate=` | Quantos leads preencheram cada campo |
| GET | `/api/tags` | Etiquetas e quantos leads têm cada uma |
| GET | `/api/sessoes?limit=50` | Quem está parado em qual passo |
| GET | `/api/eventos?limit=40&kind=&desde=&ate=&flow=&offset=` | Eventos crus. `kind` aceita vários, separados por vírgula |
| GET | `/api/historico?desde=&ate=&por=dia\|fluxo\|dia_fluxo&flow=` | Funil por dia ou por fluxo |
| GET | `/api/export.csv?tipo=historico\|leads\|execucoes\|eventos&sep=,` | CSV para planilha. `sep` aceita `,` `;` ou `tab` |
| GET | `/api/medias` | Os últimos 25 posts e Reels da conta |
| GET | `/api/backup.db` | Cópia do banco ([backup](/tutoriais/backup-e-atualizacao)) |

## Rotas públicas

| Método | Rota | O que faz |
|---|---|---|
| GET | `/health` | `{ok, conta_conectada}`. Logado, mostra também versão, dias de acesso restantes, envios na última hora e teto |
| GET | `/webhook` | Verificação da Meta (`hub.verify_token` tem que bater com `WEBHOOK_VERIFY_TOKEN`) |
| POST | `/webhook` | Eventos da Meta. Confere a assinatura `X-Hub-Signature-256` com a chave secreta do app. Sem chave configurada, responde `503`; assinatura errada, `403` |
| GET | `/privacy` | Política de privacidade da instância |

## Painel

Páginas HTML, todas com login: `/painel`, `/fluxos`, `/editor`, `/leads`, `/config`. Conexão com o Instagram em `/auth/start` e `/auth/callback`.

## Proteção do login

Depois de 5 senhas erradas do mesmo IP, a espera começa em 30 segundos e dobra a cada erro, até 15 minutos. Somando todos os IPs, 30 erros em 10 minutos (ajustável em `CEQ_LOGIN_FALHAS_JANELA`) travam o login para todos por um tempo. O login só aceita senha por HTTPS.
