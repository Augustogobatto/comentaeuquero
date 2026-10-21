# Primeiro fluxo: comenta e recebe o link

O caso clássico: você publica um post dizendo "comenta EU QUERO que eu te mando o material". Quem comenta recebe o link no direct em segundos, e o comentário ganha uma resposta pública.

## 1. Crie o fluxo

1. No painel, abra **Fluxos** e clique em **Criar fluxo**.
2. Dê um nome, por exemplo "Material grátis".

O fluxo já nasce com o bloco **Quando começa**, que é o gatilho. Tudo que vem depois dele é o caminho que a pessoa percorre.

<!-- PRINT: editor com um fluxo novo, mostrando só o bloco "Quando começa" -->
<Print>Editor com um fluxo novo, mostrando só o bloco "Quando começa".</Print>

## 2. Configure o gatilho

Clique em **Quando começa** e depois em **Adicionar gatilho**:

- **Tipo:** comentário em post ou Reel.
- **Palavras-chave:** `eu quero, quero` (separadas por vírgula).
- **Só nestes posts:** marque o post da campanha. Sem nenhum marcado, vale para todos os posts.
- **Responder no próprio comentário:** `Te mandei no direct`. Dá pra pôr várias frases; elas saem em rodízio, o que parece menos robô.

::: tip Como a palavra é reconhecida
Maiúsculas e acentos não importam: "Eu Quero" e "eu quero" disparam igual. A palavra precisa aparecer inteira, em qualquer lugar do comentário: "quero" dispara em "eu quero muito", mas "passo" não dispara em "passou". Sem nenhuma palavra-chave, o gatilho dispara para qualquer comentário.
:::

## 3. Adicione a mensagem

Clique em **Adicionar passo**, escolha **Mensagem** e escreva:

```txt
Oi, {primeiro_nome}! Aqui está o material que você pediu:
{link}
```

No campo **Link**, cole o endereço do material. Se o texto não tiver `{link}`, o link entra sozinho numa linha no fim.

Quer um botão em vez do link solto? Adicione um botão do tipo **abre um link**, com até 20 caracteres no texto, por exemplo "Baixar o material". Uma mensagem aceita até 3 botões.

::: warning O botão só aparece no celular
No Instagram pelo computador, o botão não aparece. É limitação do Instagram (vale para qualquer ferramenta), não erro da instalação. No app do celular ele aparece normal.
:::

Ligue o bloco **Quando começa** na mensagem, arrastando da bolinha de saída até o bloco seguinte.

<!-- PRINT: fluxo pronto, "Quando começa" ligado a uma "Mensagem" com um botão de link -->
<Print>Fluxo pronto: "Quando começa" ligado a uma "Mensagem" com um botão de link.</Print>

## 4. Ligue e teste

1. Ative o fluxo e salve.
2. Peça para **outra pessoa** comentar a palavra no post. Comentário da sua própria conta é ignorado de propósito, e o Instagram não entrega direct para você mesmo.
3. A mensagem chega no direct dela em poucos segundos, e o comentário ganha a resposta pública.

No **Painel**, a **Atividade recente** mostra o que chegou e o que foi enviado. Em **Leads** aparece quem comentou, com nome, foto e número de seguidores.

## Se não chegou

- O app da Meta está **publicado**? Sem isso, comentário não chega. [Ver como publicar](./app-meta#_7-publique-o-app).
- Comentou da própria conta? Use outra.
- A palavra apareceu inteira no comentário?
- O fluxo e o gatilho estão ativos?
- O painel diz que os eventos estão sendo recusados? Falta a chave secreta do app.

## Para ir além

- Variações do texto: o bloco Mensagem aceita outras versões da mesma mensagem, enviadas em rodízio ou sorteadas.
- Só para quem segue: um bloco **Condição** com "segue a conta" manda quem segue para um lado e quem não segue para outro.
- [Etiquetas e campos](./etiquetas-e-campos) para saber depois quem pegou o quê.
