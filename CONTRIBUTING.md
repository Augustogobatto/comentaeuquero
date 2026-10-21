# Contribuindo

Obrigado por querer ajudar. O projeto é código aberto sob a
[licença de uso sustentável](LICENSE.md): ao enviar um PR, você concorda que sua
contribuição entra sob essa mesma licença.

## Antes de começar

- Bug: abra uma issue com o template **Bug**.
- Ideia ou melhoria: abra uma issue com o label **`sugestao`** (template **Sugestão**) e
  descreva o problema que você quer resolver, não só a solução. Conversamos na issue antes
  de alguém escrever código.
- Vulnerabilidade: **não abra issue**. Siga o [SECURITY.md](SECURITY.md).
- PR pequeno e focado é revisado mais rápido que PR grande.

## Ambiente de desenvolvimento

Backend (Python 3.12):

```bash
python3 -m venv .venv
.venv/bin/pip install -r requirements-dev.txt
.venv/bin/pytest
```

Pra rodar o app local:

```bash
cp .env.example .env
DATA_DIR=./data CEQ_PERMITE_HTTP=1 .venv/bin/uvicorn app.main:app --port 8080 --reload
```

Editor de fluxos (Vue 3 + Vue Flow), em `editor/`:

```bash
cd editor
npm ci
npx vite            # servidor de desenvolvimento
npx vite build      # gera o resultado em app/static/editor (é o que a imagem serve)
```

Se mudar algo em `editor/src`, rode o build e inclua `app/static/editor` no commit.

## Testes

Todo PR roda a suíte no GitHub Actions (`.github/workflows/testes.yml`). Rode antes:

```bash
.venv/bin/pytest
```

- `tests/test_*.py`: testes unitários e de API (FastAPI `TestClient`).
- `tests/scripts/teste_*.py`: cenários de ponta a ponta do motor de fluxo, rodados em
  subprocesso por `tests/test_scripts.py`. O módulo do Instagram é dublado: nada sai pra Meta.

Corrigiu um bug? Inclua o teste que falhava antes.

## Padrão de commit

Mensagem curta, em português, no imperativo ou no passado, sem ponto final. Prefixo
opcional quando ajuda a ler o histórico:

```
v1.8.0: transmissão pelo WhatsApp
ci: imagem só a partir de tag v*
segurança: freio do login sem confiar no X-Forwarded-For
docs: instalador novo em /members/instalar
testes: instalar sem token, senha curta, hash pbkdf2
```

Mudança que o dono da instância percebe sobe `VERSAO` em `app/main.py` (o teste
`test_versao` acompanha) e ganha uma linha no [CHANGELOG.md](CHANGELOG.md).
Versões seguem `vMAJOR.MINOR.PATCH`; a tag `v*` dispara a publicação e assinatura da imagem.

## Regras do código

- Segredo nunca entra no repositório, nem em teste. `.env`, `*.db` e tokens estão no `.gitignore`.
- Texto da interface em português.
- Nada de dado de cliente ou de terceiros em exemplos, testes e fixtures.
- Comentário explica o **porquê** (a restrição, o bug que motivou), não repete o que o código faz.

## Código de conduta

Participar significa aceitar o [Código de Conduta](CODE_OF_CONDUCT.md).
