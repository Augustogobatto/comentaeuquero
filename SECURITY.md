# Segurança

## Como reportar uma vulnerabilidade

**Não abra issue pública.** Use o reporte privado do GitHub:
[**Report a vulnerability**](https://github.com/Augustogobatto/comentaeuquero/security/advisories/new)
(aba *Security* do repositório). Inclua:

- o que você encontrou e onde (arquivo, rota ou tela);
- passo a passo pra reproduzir;
- o impacto que você enxerga;
- versão da instância (aparece no painel e em `app/main.py`).

Respondemos em até 5 dias úteis confirmando o recebimento, e mantemos você informado
até a correção. Pedimos que não divulgue o problema antes de haver uma versão corrigida
publicada; depois disso, damos o crédito a quem reportou, se você quiser.

## O que está no escopo

O código deste repositório e a imagem `ghcr.io/augustogobatto/comentaeuquero`: autenticação
do painel, verificação de assinatura dos webhooks, tratamento de segredos, isolamento entre
instâncias, injeção, e a cadeia de publicação da imagem (assinatura cosign).

Fora do escopo: problemas na plataforma da Meta, no seu servidor ou na sua configuração
(por exemplo, expor o painel sem HTTPS).

## Versões suportadas

Corrigimos a versão mais recente. Mantenha a instância atualizada.

## Pra quem instala

- Use `META_APP_SECRET`: sem ele a instância recusa os eventos, de propósito.
- Use senha longa e única no painel e sirva o painel só por HTTPS.
- Guarde a `CEQ_ENCRYPTION_KEY` fora do servidor e faça backup do volume `/data`.
- Nunca coloque o `.env` ou o banco em repositório.
