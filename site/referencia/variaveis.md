# Variáveis

Escreva o nome entre chaves simples: `{primeiro_nome}`. Só letras, números e `_`.

## Do lead

| Variável | Valor |
|---|---|
| `{primeiro_nome}` | O primeiro nome, limpo. "MARIA SANTOS \| Doces" vira "Maria". Sem nome utilizável, usa o @. |
| `{username}` | O @, sem o `@` na frente. |
| `{name}` | O nome completo, como está no perfil. Se vazio, o @. |
| `{qualquer_campo}` | Qualquer campo guardado no lead: `{email}`, `{telefone}`, `{whatsapp}`. |

## Do fluxo

| Variável | Valor |
|---|---|
| `{link}` | O campo Link do passo Mensagem. |
| `{gatilho}` | `comment`, `live_comment`, `story_reply` ou `dm`. |
| `{texto_recebido}` | O texto que disparou o fluxo (até 500 caracteres). |
| `{ultima_escolha}` | O botão ou opção que a pessoa clicou por último. |
| `{nome_do_campo}` | O que a pessoa respondeu num **Esperar resposta** (o nome é o do "Guardar em"). |
| `{chave}` | Cada chave do JSON devolvido por um **Webhook**. |

## Regras

- Variável sem valor vira vazio, e o espaço sobrando antes de pontuação some: "Oi {apelido}!" sem o campo `apelido` vira "Oi!".
- Maiúsculas importam: `{Email}` e `{email}` são diferentes.
- Se um campo do lead tiver o mesmo nome de uma variável do fluxo, vale o campo do lead. Evite criar campos chamados `link`, `name` ou `username`.

## Onde funciona

Texto da mensagem e variações, texto de botão e de opção, prompt da IA, valor do "guardar um valor", texto de nova tentativa e resposta pública no comentário (nesta, sem `{link}`).

## Templates do WhatsApp

::: v-pre

Templates usam a sintaxe da Meta, com números: `{{1}}`, `{{2}}`. Você liga cada número a um campo do lead ao usar o template. Veja [Criar um template](/tutoriais/criar-template).

:::
