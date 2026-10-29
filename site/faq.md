# Perguntas frequentes

## Funcionamento

### É permitido pela Meta?

Sim. O comenta EU QUERO usa a API oficial do Instagram (com login do Instagram) e a Cloud API oficial do WhatsApp, com as permissões oficiais e dentro das regras de janela de cada uma. É o mesmo mecanismo que as ferramentas pagas usam. Como o app da Meta é seu e você usa na sua própria conta, não precisa de análise da Meta.

### Por que a mensagem não chegou?

Na ordem do mais comum:

1. **O app da Meta não está publicado.** Sem publicar, comentário não chega. [Como publicar](/tutoriais/app-meta#_7-publique-o-app).
2. **Você comentou da própria conta.** É ignorado de propósito.
3. **A palavra não apareceu inteira.** "passo" não dispara em "passou"; "livro" não dispara em "livros".
4. **O fluxo ou o gatilho está desligado.**
5. **Falta a chave secreta do app.** O painel mostra um aviso de eventos recusados.

A **Atividade recente** no painel mostra tudo que chegou e o que foi enviado.

### O botão não aparece na mensagem

Você está olhando pelo computador. Botão em mensagem só aparece no app do Instagram no celular. Vale para qualquer ferramenta.

### Preciso reconectar a conta de tempos em tempos?

Não. O acesso dura 60 dias e a instância renova sozinha antes de vencer. Se a conta desconectar (senha trocada, acesso removido no Instagram), o painel avisa e mostra **Reconectar conta**.

## Janela de 24 horas

### O que é a janela de 24 horas?

Regra da Meta, no Instagram e no WhatsApp: depois que a pessoa manda a última mensagem (ou comenta, ou clica num botão), você tem 24 horas para mandar mensagens livres para ela. Passou disso, só volta a abrir quando ela escrever de novo.

### Como o comenta EU QUERO lida com isso?

- Cada resposta, clique ou mensagem da pessoa reabre a janela por mais 24 horas.
- Mensagem que cairia fora da janela não é enviada. A execução termina como "fora da janela" e fica registrada.
- O editor avisa quando a soma das esperas de um fluxo passa de 24 horas.
- Não usamos a etiqueta de "atendimento humano" (que estende a janela para 7 dias), porque ela é só para conversa com uma pessoa de verdade. Usar em automação dá bloqueio.

### E o comentário?

Para comentário, a Meta permite uma **resposta privada** por comentário, em até 7 dias depois dele. É essa resposta que leva a primeira mensagem. Em live, só enquanto a live está no ar.

### E no WhatsApp? (WhatsApp)

Fora da janela, só template aprovado. Num fluxo, um passo de texto que cairia fora da janela não envia e segue pela saída de falha; para retomar contato, use um passo Template WhatsApp.

## Limites da Meta

### Quantas mensagens por hora?

No Instagram, o comenta EU QUERO manda até **180 por hora** por padrão, com 1,5 segundo entre mensagens do mesmo fluxo. Dá para subir até 750 por hora em **Configurações → Ritmo de envio**, que é o limite de respostas privadas a comentários da Meta (750 por hora por conta, segundo a [documentação de limites da Meta](https://developers.facebook.com/documentation/business-messaging/messenger-platform/overview/rate-limiting), consultada em 21/10/2026).

Quando o limite acaba, nada se perde: a mensagem espera a vez e sai assim que der. A resposta pública no comentário é a exceção; em pico, ela é pulada.

### O que acontece se a Meta mandar parar?

Se a Meta responder que a conta está mandando demais, a instância para todos os envios pelo tempo que a Meta pedir (ou 15 minutos, se ela não disser), guarda isso mesmo se reiniciar e retoma sozinha. O painel mostra o tempo restante e, se você configurou, avisa no Telegram.

### Limite do WhatsApp

A Meta limita quantas **pessoas diferentes** você pode contatar por template em 24 horas, fora da janela de atendimento. As faixas são 250, 2.000, 10.000, 100.000 e ilimitado. Número novo começa em 250. Sobe para 2.000 verificando a empresa na Meta ou enviando bem por 30 dias; acima disso, sobe sozinho quando a qualidade é alta e você usou pelo menos metade do limite na última semana. Desde 2026 o limite vale para o portfólio empresarial inteiro, não por número. Fonte: [limites de mensagens da Meta](https://developers.facebook.com/documentation/business-messaging/whatsapp/messaging-limits), consultada em 21/10/2026.

Responder quem te escreveu (dentro da janela) não conta para esse limite.

## Custo

### Quanto custa comparado ao ManyChat?

O comenta EU QUERO não cobra nada. Você paga o servidor, que custa o mesmo com 500 ou 50 mil contatos: uma VPS de R$ 20 a R$ 30 por mês. O ManyChat cobra por contato ativo.

| Contatos ativos | ManyChat, por mês | comenta EU QUERO, por mês |
|---|---|---|
| 2.500 | US$ 29 (Pro) | só o servidor |
| 10.000 | US$ 114 (Business + 2.500 extras) | só o servidor |
| 25.000 | US$ 139 (Advanced) | só o servidor |
| 50.000 | US$ 209 (Advanced + 25.000 extras) | só o servidor |

Fonte: preços públicos em [manychat.com/pricing](https://manychat.com/pricing), consultados em 21/10/2026, plano anual, valor por mês, sem impostos. No plano mensal o ManyChat cobra mais. As mensagens de WhatsApp são cobradas pela Meta nos dois casos (veja abaixo). ManyChat é marca de ManyChat, Inc.; o comenta EU QUERO não tem relação com a empresa.

## Custo do WhatsApp

### Quanto custa cada mensagem de WhatsApp?

A Meta cobra por **mensagem de template entregue**, conforme a categoria. Mensagem que o cliente manda para você é grátis. Valores para destinatários no Brasil:

| Categoria | Preço por mensagem | Situação |
|---|---|---|
| Marketing | cerca de US$ 0,0625 | Não confirmado na tabela oficial (ver nota) |
| Utilidade | US$ 0,0068 | Confirmado |
| Autenticação | US$ 0,0068 | Confirmado |
| Atendimento (resposta dentro da janela) | 1.000 grátis por mês por número; a partir da 1.001ª, cobrada | Confirmado |

- **Desde 1º de outubro de 2026**, mensagem de utilidade dentro da janela de atendimento passou a ser cobrada (antes era grátis), e as mensagens de atendimento passaram a ter a franquia de 1.000 por mês.
- **Anúncio que abre conversa no WhatsApp** (clique para o WhatsApp): por até 7 dias depois, nenhuma mensagem é cobrada.
- Utilidade e autenticação têm desconto por volume, que recomeça todo mês.
- Contas no Brasil podem ser cobradas em reais; a migração para BRL é obrigatória até 30/06/2027.

Fonte: [preços da plataforma WhatsApp Business](https://developers.facebook.com/docs/whatsapp/pricing), tabela vigente desde 01/10/2026, consultada em 21/10/2026. O valor de utilidade e autenticação no Brasil está nessa página. O de marketing vem de guias de terceiros, porque a tabela por país sai num arquivo que não conseguimos abrir: confira o valor atual na [tabela interativa da Meta](https://business.whatsapp.com/products/platform-pricing) antes de planejar uma transmissão grande.

### Quanto sai uma transmissão para 1.000 pessoas?

Com template de marketing, perto de US$ 62,50 em mensagens, mais o servidor. Com utilidade, perto de US$ 6,80. O painel mostra o custo estimado antes de você disparar. Esse valor é cobrado pela Meta no cartão cadastrado na conta do WhatsApp, não pelo comenta EU QUERO. Ferramentas pagas pagam a mesma tarifa para a Meta e cobram a mensalidade em cima.

## Bloqueios

### Posso ser bloqueado?

No Instagram, o risco vem de mandar demais em pouco tempo ou de muita gente denunciar as mensagens. O ritmo padrão e o respeito à janela existem para isso. Mantenha o ritmo padrão até conhecer o comportamento da sua conta.

No WhatsApp, a Meta mede a **qualidade** do número pelas denúncias e bloqueios dos clientes. Qualidade baixa reduz o limite e pode pausar templates ou o número.

### Como evitar?

- Mande só para quem pediu: quem comentou, deu o número ou iniciou a conversa.
- Deixe claro quem está falando e como sair. O comenta EU QUERO respeita SAIR e PARAR no WhatsApp.
- Não importe lista comprada ou antiga sem consentimento.
- Comece transmissões devagar e acompanhe a qualidade no painel.
- Não use WhatsApp não oficial (QR code, WhatsApp Web automatizado) no mesmo número.

### Meu app da Meta foi restrito. E agora?

Abra o painel de desenvolvedores: a Meta mostra o motivo e o que fazer em **Alertas** ou na página do app. Os casos mais comuns são falta de política de privacidade válida (a instância serve uma em `/privacy`) ou nome do app com marca da Meta.

## Licença e uso

### Posso instalar para os meus clientes e cobrar?

Pode. Consultoria e instalação são permitidas. O que a licença proíbe é hospedar uma instância e vender acesso a ela como serviço (SaaS) sem autorização. [Ler a licença](/licenca).

### O comenta EU QUERO é open source?

O código é aberto: você lê, modifica e usa de graça. A licença é de uso sustentável, que não é uma licença open source no sentido da OSI, porque proíbe revender como serviço hospedado. [Detalhes](/licenca).
