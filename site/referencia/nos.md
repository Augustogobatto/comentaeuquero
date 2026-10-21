# Nós

Os blocos do editor se dividem em famílias pela função: **Conversa** (fala com a pessoa), **Tempo** (espera), **Caminhos** (decide) e **Bastidores** (trabalha por trás). O primeiro bloco de todo fluxo é o **Quando começa**, que guarda os [gatilhos](./gatilhos).

Entre parênteses, o nome interno do tipo, que aparece no JSON exportado.

## Conversa

### Mensagem (`text` / `buttons`)

Envia um texto, com link e botões opcionais.

| Campo | Detalhe |
|---|---|
| Texto | Até 1.000 bytes sem botões, 640 com botões. Aceita [variáveis](./variaveis). |
| Link | Opcional. Se o texto não tiver `{link}`, entra numa linha no fim (só sem botões). |
| Variações | Outras versões do texto. **Rotação:** rodízio (uma depois da outra) ou aleatória. |
| Botões | Até 3. Texto com até 20 caracteres. Tipo **abre um link** (sem saída) ou **continua o fluxo** (cada um vira uma saída). |

- Com botões, texto acima de 640 bytes sai antes, numa mensagem separada, e o cartão com os botões vem depois.
- Botões só aparecem no app do Instagram no celular.
- Depois de uma mensagem com botão "continua o fluxo", o fluxo espera o clique.

### Opções rápidas (`quick_replies`)

Uma pergunta com opções que aparecem como bolhas acima do teclado.

- Até 13 opções, cada uma com até 20 caracteres.
- Cada opção é uma saída. O valor clicado fica em `{ultima_escolha}`.

### Mídia (`media`)

Envia imagem, vídeo ou áudio, ou um carrossel.

| Campo | Detalhe |
|---|---|
| Tipo | imagem, vídeo ou áudio |
| URL | Endereço público do arquivo. Quem baixa é a Meta, então não pode ser link privado. |
| Carrossel | Até 10 cartões, cada um com título e subtítulo (até 80 caracteres), imagem e link ao tocar. Se preenchido, vale no lugar da URL. |

### Resposta com IA (`ai`)

Manda o prompt para a IA e envia a resposta como mensagem. Detalhes no [tutorial](/tutoriais/ia-no-fluxo).

| Campo | Detalhe |
|---|---|
| Prompt | O pedido para a IA. Aceita variáveis, como `{texto_recebido}`. |
| Texto reserva | Enviado se faltar a chave, se a pessoa passou do limite por hora ou se a API falhar. |

- Provedor: Anthropic. Chave em `AI_API_KEY`, modelo em `AI_MODEL`.
- Resposta com até 1.000 bytes, até 300 tokens.

### Pedir WhatsApp (WhatsApp)

Pede o número no direct do Instagram, confere (com ou sem o 9, com ou sem DDI), guarda no campo `whatsapp` e registra o consentimento. Tem um texto de consentimento próprio. Veja a [ponte](/tutoriais/ponte-ig-wa).

### Template WhatsApp (WhatsApp)

Envia um template aprovado e passa a conversa para o WhatsApp. A resposta da pessoa continua o mesmo fluxo. Cada variável do template é ligada a um campo do lead.

## Tempo

### Esperar (`delay`)

Espera alguns minutos e segue para o próximo passo.

- O editor avisa se a soma das esperas passar de 24 horas: depois disso o Instagram não deixa mais mandar mensagem, a não ser que a pessoa responda.

### Agendar (`schedule`)

Segue para o próximo passo numa data e hora, em UTC (`2026-11-01T14:00:00Z` = 11h em Brasília).

### Esperar resposta (`wait_input`)

Espera a pessoa escrever e guarda o que ela mandou.

| Campo | Detalhe |
|---|---|
| Espera | qualquer texto, um e-mail ou um telefone (10 a 15 dígitos) |
| Guardar em | Nome do campo do lead. Obrigatório. |
| Texto de nova tentativa | Enviado quando a resposta não é válida. |
| Desistir depois de | Minutos. 0 = espera para sempre. Com prazo, ganha a saída **se não responder**. |

- E-mail é guardado em minúsculas.
- A resposta reabre a janela de 24 horas.

## Caminhos

### Condição (`condition`)

Duas saídas: **sim** e **não**.

| Teste | Pergunta |
|---|---|
| tem a marcação | A pessoa tem esta etiqueta? |
| tem o campo preenchido | Este campo tem algum valor? |
| tem o campo igual a | Este campo é exatamente este valor? |
| segue a conta | A pessoa segue o seu perfil? (Consulta a Meta na hora. Se a Meta não informar, conta como sim.) |

### Teste A/B (`split`)

Sorteia entre as saídas **A** e **B**. Você escolhe o percentual que vai para A; o resto vai para B.

## Bastidores

### Ação (`action`)

Uma lista de ações, executadas em ordem:

- **marcar a pessoa** com uma etiqueta
- **tirar a marcação**
- **guardar um valor** num campo (o valor aceita variáveis)

### Webhook (`webhook`)

Faz um POST com JSON para uma URL sua (n8n, Make, Zapier, um servidor próprio).

Corpo enviado:

```json
{
  "lead": { "igsid": "...", "username": "maria.santos", "name": "Maria Santos" },
  "context": { "gatilho": "comment", "texto_recebido": "eu quero" },
  "fields": { "email": "maria@exemplo.com" },
  "tags": ["pegou_material"]
}
```

- Se a resposta for JSON com um objeto, cada chave vira uma variável nos passos seguintes: `{"cupom": "MARIA10"}` permite escrever `{cupom}`.
- Saída **ok** para qualquer resposta HTTP (até erro 4xx e 5xx, com o código em `{status}`). Saída **erro** só quando a conexão falha ou passa de 15 segundos.
- As chaves da resposta não viram campos do lead. Para guardar, use uma Ação depois.

## Regras do motor

- Um passo que ramifica sem saída ligada gera aviso ao salvar.
- No máximo 40 passos por execução, para não prender a instalação num laço.
- Se a pessoa disparar o fluxo de novo, a execução anterior dela é encerrada.
- Mensagem fora da janela de 24 horas não é enviada: a execução termina como "fora da janela".
