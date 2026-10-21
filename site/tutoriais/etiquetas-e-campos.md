# Etiquetas e campos

Duas formas de guardar informação sobre cada pessoa:

- **Etiqueta** (marcação): um rótulo sim ou não. "pegou_material", "aluna", "quer_desconto".
- **Campo**: um valor com nome. `email = maria@exemplo.com`, `telefone = 11999990000`, `interesse = cabelo`.

Os dois ficam no lead e podem ser usados depois em condições, mensagens e exportações.

## Marcar uma etiqueta

Adicione um passo **Ação** e escolha **marcar a pessoa**, com o nome da etiqueta. Para tirar, **tirar a marcação**. Um bloco Ação pode ter várias ações em sequência.

Exemplo: logo depois da mensagem com o link, uma Ação que marca `pegou_material`.

## Guardar um campo

Dois jeitos:

**Perguntando.** O passo **Esperar resposta** faz uma pergunta e guarda o que a pessoa responder:

- **O que espera:** qualquer texto, um e-mail ou um telefone. E-mail e telefone são conferidos; se vier inválido, sai o texto de nova tentativa ("Esse e-mail não parece certo, tenta de novo").
- **Guardar em:** o nome do campo, por exemplo `email`.
- **Desistir depois de:** em minutos. Com 0, espera para sempre. Com um prazo, o bloco ganha a saída "se não responder".

Telefone aceito: só números, de 10 a 15 dígitos.

**Definindo.** Na **Ação**, escolha **guardar um valor**, com o nome do campo e o valor. O valor aceita variáveis: `origem = {gatilho}`.

## Usar depois

- Na mensagem: `Prontinho, {primeiro_nome}. Mandei também para {email}.`
- Na **Condição**: "tem a marcação", "tem o campo preenchido" ou "tem o campo igual a".
- Num **Webhook**: o corpo enviado leva todas as etiquetas e campos do lead.
- Em **Leads** e na exportação CSV, com uma coluna por campo.

Os nomes diferenciam maiúsculas: `{Email}` e `{email}` são campos diferentes. Escolha um padrão (tudo minúsculo, sem acento) e mantenha.

## Exemplo completo

1. Gatilho: comentário com `quero`.
2. Mensagem: "Te mando agora! Qual o seu melhor e-mail?"
3. Esperar resposta: espera um e-mail, guarda em `email`, desiste em 60 minutos.
4. Ação: marcar `deu_email`.
5. Mensagem: "Pronto, {primeiro_nome}! Aqui está: {link}"
6. Na saída "se não responder" do passo 3: Mensagem com o link mesmo assim.

Responder ao "Esperar resposta" reabre a janela de 24 horas, então os passos seguintes têm prazo novo.

## Privacidade

E-mail e telefone são dados pessoais. Se quiser apagar leads parados automaticamente, use `RETENCAO_LEADS_DIAS` no `.env` ([referência](/referencia/env)). Um lead também pode ser apagado à mão na tela Leads, junto com as etiquetas e campos dele.
