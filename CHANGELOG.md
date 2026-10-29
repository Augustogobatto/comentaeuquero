# Changelog

Formato baseado em [Keep a Changelog](https://keepachangelog.com/pt-BR/1.1.0/).
Versões seguem `vMAJOR.MINOR.PATCH`. Reconstruído a partir das tags e do histórico git.

## [Unreleased]

### Mudado — Palavra-chave casa plural e variações
- Uma regra só pra comentário, live, story, direct e WhatsApp (`flowengine.casa_palavra`):
  caixa, acento, pontuação e emoji não contam ("eu-quero" e "eu, quero" casam "eu
  quero"; "quero!" casa "quero"). Continua palavra inteira: "ia" não dispara em
  "dia", "livro" não dispara em "livrinho".
- Letra esticada no comentário casa: "queroo", "QUEROOO", "siiim", "freee". Só o
  texto é desesticado, nunca a palavra-chave: "mall" não casa "mal", "free" não casa
  "fre".
- Plural pt-BR casa nos dois sentidos, gerado a partir do singular (s, es, ão ->
  ãos/ões/ães, al/el/ol/ul -> ais/éis/óis/uis, il -> is/eis, m -> ns): "livro" e
  "livros", "ação" e "ações", "papel" e "papéis", "homem" e "homens". Nunca encurta
  palavra qualquer do texto, então "mais" não casa "mal", "pais" não casa "pal",
  "seis" não casa "sel", "deu" não casa "deus".
- Palavra de até 3 letras só casa igual (com letra esticada), sem plural: "me" não
  casa "mes", "o" não casa "os", "ia" não casa "IAs", "pão" não casa "pães". Vale
  para cada palavra de uma frase. Invariáveis em s (mais, depois, lápis, simples,
  antes...) também só casam iguais. Limitação conhecida: palavra de 4+ letras em
  "ão" casa o plural em "ães" de outra palavra ("mamão" casa "mamães").
- "_" continua fazendo parte da palavra, como na v1.9.0: payload de botão
  "QUERO_NAO" não dispara "quero", e "@maria_livros" não dispara "livros".
- Palavra-chave sem letra nem número ("", "🔥", "!!") segue a regra da v1.9.0 sem
  mudança: "" casa qualquer texto com letra ou número. Ao salvar gatilho, palavras
  perdem espaço das pontas e repetidas (`db.add_trigger`); a vazia continua vazia.
- Escrita igual ganha de variação: "livro" e "livros" em fluxos diferentes seguem
  separados. Se algum gatilho casa exato, vale a regra de antes (primeiro na ordem
  entre os exatos e os "responde sempre").
- O texto do evento é tokenizado e indexado uma vez por evento, não uma vez por
  gatilho: 200 gatilhos x 2 palavras numa mensagem de 4096 caracteres caiu de
  ~75 ms (v1.9.0) para ~1 ms.
- MCP: o aviso de palavra repetida em outro fluxo usa a normalização do motor
  ("PROMOCAO!" = "promoção") e diz a regra certa (com a mesma palavra nos dois, vale
  o gatilho criado primeiro); variação ("livro" x "livros") não é repetição.

### Segurança — prompt injection no passo de IA
- A instrução do dono do fluxo vai sozinha no `system` da chamada. Nome, @, texto
  recebido, campos salvos e qualquer outra `{variavel}` viram `[variavel]` na
  instrução e o valor vai à parte: o do lead na mensagem de usuário, dentro de
  `<dados_do_lead>`, com aviso no `system` de que aquilo é dado, nunca instrução, e
  de que as instruções não podem ser reveladas.
- Origem decide o bloco: o que veio do dono (retorno de webhook, "definir campo" com
  valor fixo ou montado só com dados do dono, na mesma sessão) vai em
  `<dados_do_dono>` no `system`, sem teto e liberado pra preço e link; o resto (texto
  recebido, nome, @, respostas, campo salvo de origem desconhecida) vai em
  `<dados_do_lead>`. "Responda usando o catálogo: {resposta_api}" segue funcionando.
- Texto não é mais escapado como HTML ("Ana & Bia" chegava como "Ana &amp; Bia" e a
  IA ecoava a entidade): só o `<` que abriria ou fecharia `dados_do_lead`,
  `dados_do_dono` ou `campo` (com espaço, hífen, caixa, `＜` ou `&lt;`) é trocado por `‹`.
- Teto de caracteres por campo do lead enviado à IA: 1.500, ajustável em
  `CEQ_IA_MAX_CHARS`; valor inválido ou <= 0 usa o padrão e avisa no log em vez de
  derrubar o import (mesmo para `CEQ_IA_POR_LEAD_HORA`).
- Resposta da IA que despeja as regras internas ou copia a instrução do dono (n-gramas
  de 6 palavras cobrindo 40% da instrução ou 25 palavras seguidas; instrução com menos
  de 12 palavras não é checada) não é enviada; sai o texto reserva (evento
  `ia_fallback`, motivo `saida_com_prompt`). Tradução e paráfrase não são detectadas.
- Resposta da IA não passa mais por `render()`: `{link}`, `{resposta_api}` etc. que o
  lead induzir a IA a escrever saem literais. O texto reserva continua renderizado.
- Prompt já salvo continua funcionando sem editar: a sintaxe `{variavel}` é a mesma.

## [1.9.0] - 2026-10-22

### Adicionado — Conectar ao Claude (MCP)
- Servidor MCP nativo em `/mcp` (Streamable HTTP, SDK oficial `mcp` 2.3.0), no mesmo
  app e domínio do painel. Funciona com Claude.ai, Claude Desktop, Claude Code e
  qualquer cliente MCP.
- Acesso por token manual (Configurações → Conectar ao Claude: gerar, ver uma vez,
  revogar; só o hash fica no banco) ou por OAuth 2.1 com PKCE e registro dinâmico,
  exigido pelo conector do Claude.ai. A tela de consentimento é o login do painel.
- 17 ferramentas: `resumo`, `listar_fluxos`, `ver_fluxo` (com envios por passo),
  `listar_leads`, `ver_lead`, `listar_templates_whatsapp`, `listar_transmissoes`,
  `ver_transmissao`, `estado_da_conta`, `criar_fluxo` (passos simples compilados no
  grafo do editor, nasce desligado), `editar_mensagem_do_fluxo`, `ligar_desligar_fluxo`,
  `adicionar_gatilho`, `etiquetar_lead`, `criar_template_whatsapp`,
  `criar_transmissao` (rascunho) e `preparar_disparo` (prévia + link do painel; não
  envia). Prompt `montar_fluxo_de_lancamento`.
- Cada chamada vira o evento `mcp_ferramenta` (nome e resultado, sem conteúdo).
  Limite por minuto por acesso e trava por IP depois de falhas de autenticação.
- Transmissão em **rascunho**: só sai pelo botão Disparar no painel. O Claude não
  tem ferramenta que envie, então texto de lead não consegue induzir um disparo.
- Fluxo no ar fica com você: o Claude não liga nem desliga fluxo (manda o link do
  editor) e só edita mensagem ou gatilho de fluxo desligado e sem ninguém no meio.

### Adicionado — Templates organizados
- Pastas de template (criar, renomear, apagar, mover). Ficam só no CEQ, a Meta não tem
  pasta; o sync não mexe nelas e apagar a pasta solta os templates em "sem pasta".
- Busca por nome e texto e filtros por pasta, status, categoria e idioma em Templates.
  Os de exemplo da Meta (`sample_*`, `hello_world`) ficam escondidos, com opção de mostrar.
- Na nova transmissão, o seletor só traz aprovados, separados por pasta, com busca e
  prévia do texto. `listar_templates_whatsapp` (MCP) devolve a pasta e filtra por ela.
- Erros da Meta na transmissão aparecem explicados em português, com o que fazer
  (131042 sem forma de pagamento, 131049, 131026, 132000...), código ao lado.

### Adicionado — Transmissão por pessoa
- Lista "Quem recebeu" na tela da transmissão: nome, número, situação (entregue, lida,
  respondeu, sem confirmação de entrega, na fila, adiada, pulada, falhou) e horário,
  com o erro da Meta explicado na linha. Filtros com contagem; a página se atualiza
  sozinha enquanto envia.

### Mudado
- Painel com o visual do Blocos (tokens, barra lateral, componentes e modo escuro); o
  editor de fluxos usa os mesmos tokens. O CSS ganha versão pelo conteúdo, então o
  navegador não fica preso no visual antigo depois de atualizar.

### Corrigido
- Template aprovado na Meta continuava "em análise" no CEQ até alguém clicar em
  Sincronizar, e não aparecia na transmissão. Templates e Nova transmissão sincronizam
  sozinhas quando há template em análise (no máximo uma vez por minuto); a linha em
  análise ganhou o link "atualizar".
- O custo da transmissão recém-criada saía US$ 0.00 enquanto o formulário mostrava o
  previsto: a página só somava o que a Meta já tinha cobrado. Agora mostra o mesmo
  previsto do formulário e, separado, o cobrado até agora.
- Fluxo criado por script com nó sem `position` quebrava o editor (o canvas ficava no
  fluxo anterior). O editor e a API dão posição automática da esquerda pra direita.

## [1.8.0] - 2026-10-21

### Adicionado — WhatsApp
Canal WhatsApp pela Cloud API oficial da Meta. Instância sem número configurado
continua exatamente como antes.

- Conexão do número em Configurações: WABA ID, Phone Number ID, token permanente
  (cifrado com `CEQ_ENCRYPTION_KEY`) e a chave secreta do app geral. O painel mostra
  nome verificado, qualidade e limite de mensagens do número. O limite é lido do
  campo `whatsapp_business_manager_messaging_limit` do número (o
  `messaging_limit_tier` está deprecado; se a versão da Graph recusar o campo novo,
  o app pede o antigo) e atualizado pelos webhooks `phone_number_quality_update`
  (`max_daily_conversations_per_business`, com `current_limit` de reserva) e
  `business_capability_update`. Tiers: TIER_50, TIER_250, TIER_2K, TIER_10K,
  TIER_100K, TIER_UNLIMITED.
- Gatilhos novos: `wa_message` (mensagem no WhatsApp, mesmas palavras-chave do
  Instagram) e `wa_template_reply` (clique em botão de template).
- Nós novos: **Pedir WhatsApp** (pede o número no direct com texto de consentimento,
  valida BR com e sem o 9 e DDI, liga ao lead) e **Template WhatsApp** (abre a
  conversa no WA; a resposta retoma a mesma sessão).
- Nós de conversa (mensagem, botões, opções rápidas, mídia, IA) traduzidos pro
  formato do WhatsApp: até 3 botões, lista até 10, botão de link como CTA.
- Saída opcional "fora da janela 24h" nos nós de mensagem livre; sem ela, o
  comportamento de antes (a sessão expira).
- Templates: sincronizados da Meta, listados e criados pelo painel.
- Transmissões: público por etiqueta ou campo (só quem deu opt-in), fila com ritmo
  por minuto, limite diário, agendamento em horário de Brasília e relatório de
  enviado / entregue / lido / respondido / falhou com custo estimado.
- Opt-out: SAIR, PARAR ou STOP (a mensagem inteira) tiram o lead de todos os envios;
  VOLTAR desfaz. O erro 131050 e o webhook `user_preferences` também contam.
- Importação de contatos (CSV ou texto colado) só com a caixa de consentimento.
- Variáveis de ambiente novas: `CEQ_WA_ENVIOS_HORA` (padrão 1000/h, separado do
  `CEQ_ENVIOS_HORA` do Instagram) e `META_WA_APP_SECRET`.

### Adicionado
- Abertura do código: README novo, CONTRIBUTING, SECURITY, CODE_OF_CONDUCT, templates de
  issue e PR, `.env.example` completo e CI de testes em pull request.
- Testes de cenário do motor de fluxo agora rodam dentro da suíte (`tests/scripts/`).

### Alterado
- `requirements-dev.txt` passa a incluir `requirements.txt`.

### Removido
- Scripts de teste obsoletos da raiz (`teste_b1.py`, `teste_b5_api.py`).

## [1.7.3] - 2026-10-20
### Alterado
- Primeira versão com imagem assinada (cosign keyless, identidade do workflow na tag).
- Imagem só é publicada a partir de tag `v*`; execução manual em branch não sobrescreve `:X.Y.Z` nem `:estavel`.

## [1.7.1] - 2026-10-11
### Alterado
- Instalador novo documentado; `:estavel` só avança com versão final (pré-release publica só a própria tag).

## [1.7.0] - 2026-10-11
### Adicionado
- Primeiro acesso em `/instalar?t=`: cria a senha do painel (hash PBKDF2 no banco); `ADMIN_PASSWORD` segue valendo.
- App ID e App Secret configuráveis pelo painel, cifrados com `CEQ_ENCRYPTION_KEY`, com checklist da Meta.
- Token `inst_` com ping de saúde (só contagens, nenhum dado de lead), aviso de instalação nova.
- `backup.db` pelo painel (arquivo sem sessões; temporário apagado se falhar).
- CI de build por tag.
### Segurança
- Token do primeiro acesso vai no corpo do POST e sai do access log.
- Estado da chave de cifra (ok/ausente/inválida) visível no painel e no log.

## [1.6.9] - 2026-09-14
### Adicionado
- Leads de verdade: `/api/campos`, `/api/leads` e exportação CSV de leads.
- Histórico exportável por janela de datas (`/api/historico` e CSV).
- Apagar a ligação entre dois passos no editor.
### Corrigido
- O ✕ da ligação ficava embaixo da própria linha e o clique não pegava.
### Alterado
- Workflow que vincula a imagem ao repositório para publicar no ghcr.

## [1.6.5] - 2026-09-03
### Adicionado
- Botão de apagar fluxo no editor; lista de fluxos com rolagem.
- Workflow de build e push da imagem no ghcr.

## [1.6.4] - 2026-08-05
### Corrigido
- Foto de perfil baixada pro volume e servida em `/avatar` (o link do CDN vencia); busca de novo no boot e no ciclo diário.

## [1.6.2] - 2026-08-05
### Segurança
- Lock unificado, validador sem explosão, senha nunca em texto claro.
- Revisão de segurança documentada.

## [1.6.1] - 2026-08-05
### Corrigido
- Gate de seguidor: `e_seguidor` reconsulta a API na hora da checagem.

## [1.5.0] - 2026-07-23
### Adicionado
- Métricas dentro do fluxo (alternador Fluxo/Métricas no editor, funil por etapa).
- Trava de rate limit: cooldown da Meta, fila em vez de descarte, alerta.
- Aba Configurações: teto de envio e alerta editáveis ao vivo.

## [1.4.0 a 1.4.3] - 2026-07-23
### Adicionado
- Card de gatilho com uma linha por gatilho e chavinha de ligar/desligar.
### Corrigido
- Painel volta a contar os eventos gravados pelo motor de fluxo.
- Atividade recente: mais nova em cima, com o dia.
### Alterado
- "Regras" sai do menu do editor.

## [1.3.0] - 2026-07-23
### Alterado
- UX do editor: caixa de texto que cresce, botões dentro da mensagem, limites à vista.

## [1.2.0 a 1.2.3] - 2026-07-23
### Alterado
- O gatilho passa a ser o primeiro passo do fluxo, no canvas.
- Botão de link: tentativa com generic template, revertida para button template (o problema era a tela, não o formato).

## [1.1.0 e 1.1.1] - 2026-07-23
### Adicionado
- Variações de mensagem com rodízio: a DM deixa de ser sempre igual.

## [1.0.3] - 2026-07-23
### Corrigido
- Reentrega de webhook da Meta travava o banco inteiro (rollback no claim duplicado).

## [1.0.2] - 2026-07-22
### Adicionado
- Painel com sessão revogável, freio de força bruta no login e retenção de dados (LGPD).

## [1.0.1] - 2026-07-22
### Segurança
- Webhook falha fechado sem `META_APP_SECRET`, e o painel diz o que falta.

## [1.0.0] - 2026-07-21
Primeira versão (v0.1 a v1.0 em 21/07/2026, sem tags).
### Adicionado
- Resposta no direct a comentário, story e DM por palavra-chave.
- Captura e enriquecimento de perfil dos leads (nome, foto, seguidores, se segue).
- Motor de fluxo com schema de grafo, runtime, mensagens ricas e webhook ligado ao motor.
- Editor visual de fluxo (Vue Flow), com painel e editor no mesmo visual.
- Imagem Docker publicada no ghcr; ativação opcional por token.
