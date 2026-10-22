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
| Limites | 120 leituras e 30 escritas por minuto por acesso; IP com 30 falhas de autenticação em 10 min espera 10 min |

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
| `preparar_disparo` | `transmissao_id` | Prévia de um rascunho: pessoas, template, custo estimado, limite de 24h, quantos ficam de fora por SAIR e o link no painel. Não envia: quem dispara é o usuário, no botão Disparar |
| `estado_da_conta` | nenhum | Instagram e validade do token, chave da Meta configurada (sim/não), ritmo, pausa da Meta, WhatsApp (número, qualidade, limite) |

## Escrita

| Ferramenta | Parâmetros | Observação |
|---|---|---|
| `criar_fluxo` | `nome`, `gatilho` {`tipo`, `palavras`, `so_nos_posts`, `respostas_publicas`}, `passos` [...] | Nasce sempre desligado. Recusa nome repetido; avisa palavra que já dispara outro fluxo |
| `editar_mensagem_do_fluxo` | `fluxo_id`, `passo_id`, `texto`, `variacoes`, `link` | Só passos com texto (mensagem, botões, opções, pedir WhatsApp) e só em fluxo desligado |
| `ligar_desligar_fluxo` | `fluxo_id`, `ligado` | Não muda nada: devolve o link do editor, onde o usuário liga ou desliga, e o que falta antes de ligar |
| `adicionar_gatilho` | `fluxo_id`, `gatilho` | Só em fluxo desligado |
| `etiquetar_lead` | `lead_id`, `adicionar`, `remover` | |
| `criar_template_whatsapp` | `nome`, `categoria` (MARKETING, UTILITY), `corpo`, `exemplos`, `botoes`, `idioma` | Envia pra aprovação da Meta |
| `criar_transmissao` | `nome`, `template`, `publico_tipo` (todos, etiqueta, campo), `publico_valor`, `campo_valor`, `variaveis` {"1": "{primeiro_nome}"}, `ritmo_por_minuto`, `agendar_para` | Cria **rascunho**: nada é enviado |

Fluxo **no ar** (ligado, ou desligado com alguém ainda no meio dele dentro da janela de 24h) não muda pelo MCP: a ferramenta recusa, não altera nada e devolve o link do editor. Assim, texto de lead lido pelo Claude não consegue mexer em automação que está recebendo gente.

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
