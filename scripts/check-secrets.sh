#!/usr/bin/env bash
# Scan the repo for likely secrets before git push. Exit 1 if anything suspicious is found.
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

RED='\033[0;31m'
GREEN='\033[0;32m'
NC='\033[0m'

fail=0

echo "Checking for files that must not be committed..."

# --- Blocked paths (would be committed if not gitignored) ---
BLOCKED=(
  ".env"
  "backend/.env"
  "frontend/.env.local"
)
for f in "${BLOCKED[@]}"; do
  if [[ -f "$f" ]]; then
    if git rev-parse --git-dir >/dev/null 2>&1; then
      if git check-ignore -q "$f" 2>/dev/null; then
        echo "  OK (ignored): $f"
      else
        echo -e "${RED}FAIL${NC}: $f exists and is NOT gitignored"
        fail=1
      fi
    else
      echo "  (no git repo) $f present locally — ensure .gitignore before init"
    fi
  fi
done

# --- If git exists, verify staged files ---
if git rev-parse --git-dir >/dev/null 2>&1; then
  if git diff --cached --name-only 2>/dev/null | grep -qE '^\.env$|backend/\.env|frontend/\.env'; then
    echo -e "${RED}FAIL${NC}: .env file is staged for commit"
    fail=1
  fi
  if git diff --cached --name-only 2>/dev/null | grep -qE 'storage/dev/.*\.log'; then
    echo -e "${RED}FAIL${NC}: dev log files are staged (may contain apikey= in URLs)"
    fail=1
  fi
  if git diff --cached --name-only 2>/dev/null | grep -qE 'backend/data_store/.*\.(db|sqlite)'; then
    echo -e "${RED}FAIL${NC}: local database files are staged"
    fail=1
  fi
fi

# --- Pattern scan (tracked + untracked text, excluding venv/node_modules) ---
echo "Scanning for secret-like patterns..."

PATTERN='(apikey=[a-zA-Z0-9%+/=_-]{8,}|GPT_PROXY_API_KEY=[a-zA-Z0-9%+/=_-]{8,}|FMP_API_KEY=[a-zA-Z0-9]{8,}|FINNHUB_API_KEY=[a-zA-Z0-9]{8,}|ALPHA_VANTAGE_API_KEY=[a-zA-Z0-9]{8,}|NEWSAPI_KEY=[a-f0-9-]{8,}|OPENAI_API_KEY=sk-[a-zA-Z0-9]{10,})'

while IFS= read -r -d '' file; do
  case "$file" in
    */.venv/*|*/node_modules/*|*/.next/*|*/storage/*|*/data_store/*) continue ;;
    */.env|*/.env.local) continue ;;
    */fmp_client.py) continue ;;
  esac
  if grep -qE "$PATTERN" "$file" 2>/dev/null; then
    # Allow placeholders in templates
    if [[ "$file" == *".env.example"* ]] || [[ "$file" == *".env.local.example"* ]]; then
      if grep -qE 'your_.*_here|your_key_here' "$file" 2>/dev/null; then
        continue
      fi
    fi
    if [[ "$file" == *"check-secrets"* ]] || [[ "$file" == *"GITHUB_SETUP"* ]]; then
      continue
    fi
    echo -e "${RED}POSSIBLE SECRET${NC} in $file"
    grep -nE "$PATTERN" "$file" | head -3 || true
    fail=1
  fi
done < <(find . -type f \( -name '*.py' -o -name '*.ts' -o -name '*.tsx' -o -name '*.md' -o -name '*.json' -o -name '*.env*' -o -name '*.log' -o -name '*.sh' \) \
  ! -path './backend/.venv/*' ! -path './quant/.venv/*' ! -path './frontend/node_modules/*' \
  -print0 2>/dev/null)

if [[ "$fail" -eq 0 ]]; then
  echo -e "${GREEN}No obvious secrets detected.${NC}"
  exit 0
fi

echo -e "${RED}Fix issues above before pushing to GitHub.${NC}"
echo "See docs/GITHUB_SETUP.md"
exit 1
