#!/usr/bin/env bash
# File-level invariants on the built site. Run from jpwolfson-site/ after `npm run build`.
# DOM-level checks (scripts, iframes, CSP) live in check-csp.py.
set -euo pipefail
fail=0
say() { printf '%s\n' "$*"; }
chk() { if eval "$2"; then say "ok   $1"; else say "FAIL $1"; fail=1; fi; }

chk "404 page is built"                   'test -f _site/404.html'
chk "no admin/ in output (Decap removed)" 'test ! -e _site/admin'
chk "_headers is deployed"                'test -f _site/_headers'
chk "_headers has HSTS"                   'grep -q "Strict-Transport-Security" _site/_headers'
chk "_headers has /files/* CSP"           'grep -A2 "^/files/\*" _site/_headers | grep -q "Content-Security-Policy"'
# Cloudflare Pages would deploy these as server-side code, outside anything _site checks see.
chk "no Pages Functions directory"        'test ! -e functions'
chk "no wrangler config in project root"  'test ! -e wrangler.toml && test ! -e wrangler.json && test ! -e wrangler.jsonc'

# Everything that reaches the origin must be one of these types. Catches a stray
# .js/.svg/.html dropped into a passthrough directory (css/, files/).
allow='html|css|pdf|png|jpg|jpeg'
while IFS= read -r f; do
  base=$(basename "$f")
  case "$base" in _headers|.gitkeep) continue ;; esac
  ext=$(printf '%s' "${base##*.}" | tr '[:upper:]' '[:lower:]')
  case "$base" in *.*) ;; *) ext="";; esac
  if ! printf '%s' "$ext" | grep -Eq "^($allow)$"; then say "FAIL disallowed output file: $f"; fail=1; fi
  if [ ! -f "$f" ] || [ -L "$f" ]; then say "FAIL not a regular file: $f"; fail=1; fi
done < <(find _site -mindepth 1 \( -type f -o -type l \))
[ $fail -eq 0 ] && say "ok   output contains only html/css/pdf/png/jpg and _headers"

exit $fail
