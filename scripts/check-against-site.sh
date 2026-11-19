#!/bin/sh
# Compare the copies in this repository with what https://exducer.ai serves now.
# Read-only: it changes nothing. Exit 0 when every copy is identical, 1 otherwise.
#   sh scripts/check-against-site.sh
cd "$(dirname "$0")/.." || exit 2
SITE="${TURBO_SITE:-https://exducer.ai}"
bad=0

same() {  # same <local file> <address>
  if curl -fsS --max-time 30 "$2" | cmp -s - "$1"; then
    echo "  same     $1"
  else
    echo "  DIFFERS  $1   ($2)"
    bad=1
  fi
}

same SETUP.md "$SITE/agents.md"
same cli/turbo.py "$SITE/cli/turbo.py"
same cli/install.sh "$SITE/cli/install.sh"
for dir in plugins/turbo/skills/*/; do
  name=$(basename "$dir")
  same "plugins/turbo/skills/$name/SKILL.md" "$SITE/.well-known/agent-skills/$name/SKILL.md"
done

if [ "$bad" = 0 ]; then echo "every copy is what the site serves"; else echo "some copies are out of date: the site is right"; fi
exit "$bad"
