# MCP (Claude)

Servidor MCP nativo da instância. Para conectar, veja o [tutorial](/tutoriais/conectar-claude).

| Item | Valor |
|---|---|
| Endereço | `https://SEU-DOMINIO/mcp` |
| Transporte | Streamable HTTP, sem sessão, resposta JSON |
| Acesso | `Authorization: Bearer <token>`. Sem token: 401 com `WWW-Authenticate` apontando os metadados |
| Token manual | Configurações → Conectar ao Claude. Não vence; um por vez |
| OAuth 2.1 | PKCE (S256), registro dinâmico, consentimento pelo login do painel. Acesso vale 8 h, renovação 60 dias (gira a cada uso) |
| Metadados | `/.well-known/oauth-protected-resource/mcp` e `/.well-known/oauth-authorization-server` |
| Rotas OAuth | `/authorize`, `/token`, `/register`, `/revoke`, tela `/mcp/autorizar` |
| Retorno do OAuth | Só `claude.ai`, `claude.com` (e subdomínios) e `localhost`. Outro cliente: `CEQ_MCP_REDIRECTS=host1,host2` no `.env` |
| Limites | 120 leituras, 30 escritas e 10 disparos por minuto por acesso; IP com 30 falhas de autenticação em 10 min espera 10 min |

::: v-pre

## Leitura

| Ferramenta | Parâmetros | Devolve |
|---|---|---|
| `resumo` | `periodo` (hoje, ontem, 7d, 30d, 90d, tudo), `desde`, `ate` (AAAA-MM-DD), `fluxo` (nome ou palavra-chave) | Pessoas que acionaram, receberam, leram e avançaram; mensagens, falhas, leads novos, campos preenchidos; por origem, por fluxo e por dia. Horário de Brasília |
| `listar_fluxos` | nenhum | id, nome, ligado, gatilhos, mensagens entregues |
| `ver_fluxo` | `fluxo_id` | Gatilhos, passos (id, tipo, texto, botões, ligações), enviados e falhas por passo, pessoas paradas em cada passo, avisos, link do editor |
| `listar_leads` | `palavra`, `etiqueta`, `segue` (todos, sim, nao), `busca`, `periodo`/`desde`/`ate`, `pagina`, `por_pagina` (até 200) | Leads da página e se tem mais |
| `ver_lead` | `lead_id` ou `username` | Dados, etiquetas, campos, histórico (sem texto de mensagem), fluxos e transmissões |
| `listar_templates_whatsapp` | `sincronizar`, `so_aprovados` | Templates com status, categoria, corpo, variáveis e botões |
| `listar_transmissoes` | nenhum | Status e funil de cada transmissão |
| `ver_transmissao` | `transmissao_id` | Relatório completo e público previsto agora |
| `estado_da_conta` | nenhum | Instagram e validade do token, chave da Meta configurada (sim/não), ritmo, pausa da Meta, WhatsApp (número, qualidade, limite) |

## Escrita

| Ferramenta | Parâmetros | Observação |
|---|---|---|
| `criar_fluxo` | `nome`, `gatilho` {`tipo`, `palavras`, `so_nos_posts`, `respostas_publicas`}, `passos` [...], `ligar` | Nasce desligado por padrão. Recusa nome repetido; avisa palavra que já dispara outro fluxo |
| `editar_mensagem_do_fluxo` | `fluxo_id`, `passo_id`, `texto`, `variacoes`, `link` | Só passos com texto (mensagem, botões, opções, pedir WhatsApp) |
| `ligar_desligar_fluxo` | `fluxo_id`, `ligado` | |
| `adicionar_gatilho` | `fluxo_id`, `gatilho` | |
| `etiquetar_lead` | `lead_id`, `adicionar`, `remover` | |
| `criar_template_whatsapp` | `nome`, `categoria` (MARKETING, UTILITY), `corpo`, `exemplos`, `botoes`, `idioma` | Envia pra aprovação da Meta |
| `criar_transmissao` | `nome`, `template`, `publico_tipo` (todos, etiqueta, campo), `publico_valor`, `campo_valor`, `variaveis` {"1": "{primeiro_nome}"}, `ritmo_por_minuto`, `agendar_para` | Cria **rascunho**: nada é enviado |
| `disparar_transmissao` | `transmissao_id`, `codigo_confirmacao` | Sem código: prévia + código (10 min, uso único, do mesmo acesso). Com código: vira agendada e o envio segue as regras de sempre |

### Passos do `criar_fluxo`

| `tipo` | Campos | Vira no editor |
|---|---|---|
| `mensagem` | `texto` (até 1000; 640 com botões), `variacoes`, `link`, `botoes` [{`titulo`, `link`}] (até 3) | Mensagem ou mensagem com botões. Botão sem link continua o fluxo |
| `link` | `texto`, `url`, `titulo_botao` | Mensagem com um botão de link (fim do caminho) |
| `esperar` | `minutos` (1 a 1440) | Esperar |
| `pergunta` | `texto`, `guardar_em`, `espera` (texto, email, telefone), `se_invalido` | Mensagem + Esperar resposta |
| `pedir_whatsapp` | `texto`, `consentimento` | Pedir WhatsApp (só com WhatsApp ligado) |
| `etiqueta` | `adicionar`, `remover` | Ação |
| `ia` | `instrucao`, `se_falhar` | Resposta com IA |

Cada passo liga no seguinte, da esquerda pra direita. Gatilhos: `comentario`, `live`, `story`, `direct`, `whatsapp`.

Links precisam começar com `http://` ou `https://`. O servidor nunca acessa esses endereços: eles só vão dentro da mensagem. Por isso não há passo de webhook nem de mídia pelo MCP; esses se montam no editor.

## Prompt e recurso

- Prompt `montar_fluxo_de_lancamento` (`produto`, `palavra_chave`, `link`): roteiro que o Claude segue pra propor, confirmar e criar o fluxo de captação.
- Recurso `ceq://referencia/passos`: esta tabela de passos, pro assistente consultar.

## Erros

Erro de regra (fluxo que não existe, template não aprovado, código vencido) volta como resultado de ferramenta com `isError` e uma frase em português pro assistente repassar. Argumento desconhecido ou fora do formato é recusado antes de rodar.

:::
