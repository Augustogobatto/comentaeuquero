# Referência

O que existe no comenta EU QUERO, tirado do código da versão 1.7.3. Para aprender a usar, comece pelos [tutoriais](/tutoriais/).

- [Nós](./nos): cada bloco do editor, o que faz, campos e limites.
- [Gatilhos](./gatilhos): o que começa um fluxo e como a palavra-chave é reconhecida.
- [Variáveis](./variaveis): o que dá pra escrever entre chaves nas mensagens.
- [API](./api): as rotas HTTP da instância.
- [Configuração (.env)](./env): todas as variáveis de ambiente.

Itens marcados **WhatsApp** fazem parte do canal novo, em construção. Eles descrevem o comportamento planejado e podem mudar até o lançamento.

## Limites gerais

| O quê | Valor |
|---|---|
| Contas de Instagram por instalação | 1 |
| Números de WhatsApp por conta | 1 (WhatsApp) |
| Passos executados por vez num fluxo | 40 (passou disso, a sessão termina) |
| Envios por hora (padrão) | 180, ajustável de 10 a 750 em Configurações |
| Intervalo entre mensagens do mesmo fluxo | 1,5 segundo |
| Janela para responder no Instagram | 24 horas desde a última mensagem da pessoa |
