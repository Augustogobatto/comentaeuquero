# Conectar ao Claude (MCP)

Desde a 1.9.0, a sua instância fala MCP, o protocolo que o Claude usa pra conversar com outros programas. Com o conector ligado, você opera o comenta EU QUERO por conversa:

- "Cria um fluxo que responde quem comentar *ebook* com este link."
- "Quantos leads a palavra *mentoria* trouxe essa semana?"
- "Manda o template da black friday pra todo mundo com a etiqueta *comprador*."

O Claude conversa direto com a **sua** instância. Nada passa por servidor nosso nem de terceiros: o conector é código do próprio CEQ, no mesmo endereço do painel.

::: tip Antes de começar
Você precisa da instância no ar com endereço **https** (o `BASE_URL` do `.env`). O Claude.ai não conecta em http.
:::

## Claude.ai e Claude Desktop

Os dois usam o mesmo cadastro de conectores, e não precisam de token: o Claude pede autorização e você aprova com a senha do painel.

1. No Claude, abra **Configurações → Conectores → Adicionar conector personalizado**.
2. Nome: `comenta EU QUERO`. URL: `https://SEU-DOMINIO/mcp` (está pronta pra copiar em **Configurações → Conectar ao Claude** do painel).
3. Clique em **Conectar**. Abre a sua instância: entre com a senha do painel e clique em **Permitir**.
4. Pronto. Numa conversa nova, peça: "como está minha conta no comenta EU QUERO?".

<Print>Tela "Permitir acesso?" da instância, com o nome do Claude e os botões Permitir e Recusar.</Print>

A conexão aparece na tabela de **Configurações → Conectar ao Claude**, com o último uso. **Desconectar** corta o acesso na hora.

## Claude Code

1. No painel, **Configurações → Conectar ao Claude → Gerar token**. O token aparece **uma vez**: copie e guarde como senha.
2. No terminal:

```bash
claude mcp add --transport http ceq https://SEU-DOMINIO/mcp \
  --header "Authorization: Bearer SEU_TOKEN"
```

3. Abra o Claude Code e peça "lista meus fluxos do ceq".

Outros clientes MCP (Cursor, scripts, o Inspector) usam o mesmo par: transporte **Streamable HTTP** em `https://SEU-DOMINIO/mcp` com o cabeçalho `Authorization: Bearer SEU_TOKEN`.

Gerar um token novo invalida o anterior. **Revogar** apaga o token e quem usava perde o acesso na hora.

## O que o Claude pode e não pode fazer

Pode ler resultados, fluxos, leads, templates e transmissões; criar fluxos e editar os que estão desligados (mensagens e gatilhos); etiquetar leads; enviar template pra aprovação da Meta; preparar transmissão como rascunho e mostrar a prévia.

Fluxo criado por conversa nasce **desligado** e abre organizado no editor visual. **Quem liga e desliga é você**, no editor: o Claude manda o link. Fluxo ligado (ou com gente no meio dele) o Claude também não edita; ele te passa o link pra mudar lá, ou pra desligar antes.

Transmissão manda mensagem pra gente de verdade e custa dinheiro, então **o Claude não dispara**. Ele cria o rascunho e te mostra a prévia: quantas pessoas, qual template, custo estimado, quantos ficam de fora por terem pedido SAIR e se cabe no limite de 24h. Junto vem o link da transmissão no painel. Você confere lá e aperta **Disparar**.

É de propósito: o Claude lê mensagens de leads, e um texto malicioso poderia tentar convencer ele a enviar, ou a trocar o link de um fluxo no ar. Como nenhuma ferramenta envia nem mexe no que está no ar, não tem o que convencer.

O envio segue as mesmas regras do painel: só quem deu consentimento, quem pediu SAIR fica de fora, ritmo, limite diário e pausas pedidas pela Meta.

Não pode: disparar transmissão, ligar ou desligar fluxo, editar fluxo no ar, ver tokens ou senhas, mudar as credenciais da Meta, apagar a conta ou leads.

## Segurança

- Só o hash do token fica no banco. Sem https, a instância recusa o acesso (o token iria legível).
- Cada chamada vira um evento `mcp_ferramenta` com o nome da ferramenta e o resultado, nunca o conteúdo.
- Limite de chamadas por minuto (leitura e escrita têm tetos diferentes) e trava por IP depois de muitas tentativas com token errado.

A lista completa de ferramentas está na [referência](/referencia/mcp).
