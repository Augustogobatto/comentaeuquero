#!/usr/bin/env bash
# Gera uma cópia limpa do repositório, SEM histórico, pronta pra virar o repo público.
#
#   scripts/exportar-publico.sh /caminho/da/pasta-destino
#
# - copia só o que o git versiona (nada de .env, .venv, banco, node_modules)
# - tira o material interno (lista abaixo)
# - varre segredos (gitleaks > trufflehog > grep de padrões) e nomes internos
# - NÃO faz git init, push nem muda visibilidade de nada: o commit inicial é seu.
#
# Sai com código 1 se a varredura de segredo achar algo.
set -euo pipefail

DESTINO="${1:-}"
[ -n "$DESTINO" ] || { echo "uso: $0 <pasta-destino>" >&2; exit 2; }

RAIZ="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
mkdir -p "$DESTINO"
DESTINO="$(cd "$DESTINO" && pwd)"
if [ -n "$(ls -A "$DESTINO")" ]; then
  echo "a pasta $DESTINO não está vazia; use uma pasta nova" >&2
  exit 2
fi
case "$DESTINO" in "$RAIZ"|"$RAIZ"/*) echo "o destino não pode ficar dentro do repo" >&2; exit 2;; esac

# material que não vai pro repo público
EXCLUIR=(
  "docs/SEGURANCA.md"
  "docs/REVIEW_05AGO2026.md"
  "docs/AULA_INSTALACAO.md"
  "docs/superpowers"
  ".venv"
  "node_modules"
  "__pycache__"
  ".git"
  ".claude"
)

echo "==> copiando arquivos versionados pra $DESTINO"
# git ls-files => só o que está no repo (respeita .gitignore); mais os novos ainda não commitados
(cd "$RAIZ" && git ls-files -z --cached --others --exclude-standard) | rsync -a --from0 --files-from=- "$RAIZ"/ "$DESTINO"/

for item in "${EXCLUIR[@]}"; do
  find "$DESTINO" -path "$DESTINO/$item" -prune -exec rm -rf {} + 2>/dev/null || true
  find "$DESTINO" -name "$(basename "$item")" -prune -exec rm -rf {} + 2>/dev/null || true
done
find "$DESTINO" -name "*.pyc" -delete
find "$DESTINO" -name ".DS_Store" -delete
find "$DESTINO" -mindepth 1 -type d -empty -delete
echo "    $(find "$DESTINO" -type f | wc -l | tr -d ' ') arquivos copiados"

STATUS=0

echo "==> varredura de segredos"
if command -v gitleaks >/dev/null 2>&1; then
  echo "    ferramenta: gitleaks $(gitleaks version 2>/dev/null)"
  gitleaks detect --no-git --source "$DESTINO" --redact --no-banner -v || STATUS=1
elif command -v trufflehog >/dev/null 2>&1; then
  echo "    ferramenta: trufflehog"
  trufflehog filesystem "$DESTINO" --fail --no-update || STATUS=1
else
  echo "    ferramenta: grep de padrões (instale gitleaks: brew install gitleaks)"
  PADROES='gh[opsur]_[A-Za-z0-9]{20,}|github_pat_[A-Za-z0-9_]{20,}|EAA[A-Za-z0-9]{30,}|sk-[A-Za-z0-9_-]{20,}|AKIA[0-9A-Z]{16}|xox[baprs]-[A-Za-z0-9-]{10,}|-----BEGIN [A-Z ]*PRIVATE KEY-----|[0-9]{8,10}:AA[A-Za-z0-9_-]{30,}'
  if grep -rInE --exclude-dir=node_modules "$PADROES" "$DESTINO"; then STATUS=1; else echo "    nenhum padrão de token/chave encontrado"; fi
  # senha preenchida em arquivo de ambiente
  if grep -rInE --include=".env*" '^(ADMIN_PASSWORD|META_APP_SECRET|AI_API_KEY|CEQ_ENCRYPTION_KEY|CLUB_TOKEN|ALERTA_TELEGRAM_TOKEN)=.+' "$DESTINO"; then STATUS=1; fi
fi
if [ -n "$(find "$DESTINO" \( -name ".env" -o -name "*.db" -o -name "tokens.json" \) -print -quit)" ]; then
  echo "    ATENÇÃO: .env/.db/tokens.json na cópia:"; find "$DESTINO" \( -name ".env" -o -name "*.db" -o -name "tokens.json" \); STATUS=1
fi

echo "==> nomes internos / de cliente (revise cada linha; autoria e licença do Augusto Gobatto ficam)"
NOMES='aline|linedecker|camila|\bELA\b|\bclub\b|push club|raiz|maxxima|go ?image|\bTPC\b|edital|chatwoot|vps-claude|n8n\.|/home/claude'
grep -rInEi --exclude-dir=node_modules --exclude=package-lock.json --exclude-dir=static "$NOMES" "$DESTINO" \
  | sed "s|^$DESTINO/||" | cut -c1-160 || echo "    nenhum"

if [ "$STATUS" -ne 0 ]; then
  echo "==> FALHOU: a varredura de segredo achou algo. Não publique esta cópia." >&2
  exit 1
fi
echo "==> ok: cópia limpa em $DESTINO (sem histórico; faça o git init/commit inicial aí)"
