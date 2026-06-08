#!/usr/bin/env bash
# Install a pre-push hook that runs scripts/check-secrets.sh
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
HOOK="$ROOT/.git/hooks/pre-push"

if [[ ! -d "$ROOT/.git" ]]; then
  echo "No .git directory. Run: git init"
  exit 1
fi

cat > "$HOOK" << 'EOF'
#!/usr/bin/env bash
exec "$(git rev-parse --show-toplevel)/scripts/check-secrets.sh"
EOF

chmod +x "$HOOK"
chmod +x "$ROOT/scripts/check-secrets.sh"
echo "Installed pre-push hook → scripts/check-secrets.sh"
