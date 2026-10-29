# Gatilhos

Um gatilho diz quando um fluxo começa. Fica no bloco **Quando começa**; um fluxo pode ter vários.

## Tipos

| Tipo | Nome interno | Dispara com |
|---|---|---|
| comentário em post ou Reel | `comment` | Comentário num post ou Reel |
| comentário durante a live | `live_comment` | Comentário numa live em andamento |
| resposta de story | `story_reply` | Resposta a um story |
| mensagem no direct | `dm` | Mensagem de texto no direct |
| mensagem no WhatsApp (WhatsApp) | `wa_message` | Mensagem recebida no número do WhatsApp |
| resposta a template (WhatsApp) | `wa_template_reply` | Clique num botão de um template enviado |

## Campos

| Campo | Detalhe |
|---|---|
| Palavras-chave | Separadas por vírgula. Vazio = qualquer texto. |
| Só nestes posts | Os posts em que o gatilho vale. Nenhum marcado = todos. Só para comentário e live. Em story e direct, deixe vazio, senão o gatilho nunca dispara. |
| Responder no próprio comentário | Uma ou mais frases, enviadas em rodízio como resposta pública. Só para comentário e live. |
| Ligado | Liga e desliga o gatilho sem apagar. |

## Como a palavra-chave é reconhecida

1. Texto e palavra passam para minúsculas e perdem os acentos. Pontuação e emoji não contam. "Eu Quero" = "eu quero"; "promoção" = "promocao"; "eu-quero" = "eu quero". O "_" faz parte da palavra: "QUERO_SIM" não dispara "quero".
2. A palavra precisa aparecer **inteira**, em qualquer posição. "quero" dispara em "eu quero muito"; "passo" não dispara em "passou".
3. Frase com espaço casa como sequência: "eu quero" dispara em "eu quero sim", não em "quero eu".
4. Plural e letra esticada casam sozinhos: "livro" dispara em "livros", "ação" em "ações", "papel" em "papéis", "quero" em "queroo" e "QUERO!!! 🙏". Diminutivo e outras palavras não: "livro" não dispara em "livrinho" nem "livraria", "ia" não dispara em "dia", "mal" não dispara em "mais".
5. Palavra de até 3 letras só casa escrita igual (letra esticada vale, plural não): "sim" dispara em "siiim", mas "ia" não dispara em "IAs" e "pão" não dispara em "pães". Se quiser os dois, coloque as duas palavras no gatilho.

## Quando dois gatilhos casam

Vale o primeiro gatilho ativo, na ordem em que foram criados, de um fluxo ativo. Só um fluxo dispara por evento.

Palavra escrita igual ganha de variação: com "livro" num fluxo e "livros" em outro, "livros" vai pro segundo e "livro" pro primeiro, em qualquer ordem.

## O que é ignorado

- Comentários e mensagens da sua própria conta.
- O mesmo evento entregue duas vezes pela Meta.
- Mensagens sem texto (figurinha, só áudio) no gatilho de direct.
- Quem está num passo **Esperar resposta**: o texto dessa pessoa vai para o passo, não para os gatilhos.

## Resposta pública

- Sai só em comentário e live, e só se a mensagem no direct foi enviada.
- Gasta uma unidade do [limite por hora](/faq#quantas-mensagens-por-hora). Em pico, quando o limite acaba, a resposta pública é pulada (a mensagem no direct não: ela espera a vez).
- Aceita variáveis de lead (`{primeiro_nome}`), mas não `{link}`.

## Primeira mensagem de um comentário

Vai como "resposta privada" ao comentário. A Meta permite uma resposta privada por comentário, em até 7 dias. As mensagens seguintes do fluxo vão como direct normal, dentro da janela de 24 horas.
