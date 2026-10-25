#!/usr/bin/env bash
# Invariants on the built site. Run from jpwolfson-site/ after `npm run build`.
set -euo pipefail
fail=0
say() { printf '%s\n' "$*"; }
chk() { if eval "$2"; then say "ok   $1"; else say "FAIL $1"; fail=1; fi; }

chk "404 page is built"                 'test -f _site/404.html'
chk "no admin/ in output (Decap removed)" 'test ! -e _site/admin'
chk "_headers is deployed"              'test -f _site/_headers'
chk "_headers has HSTS"                 'grep -q "Strict-Transport-Security" _site/_headers'
chk "_headers has /files/* CSP"         'grep -A2 "^/files/\*" _site/_headers | grep -q "Content-Security-Policy"'

# Every HTML page carries exactly one inline <script> (the MathJax config) and
# no script-src ever contains unsafe-inline or unsafe-eval.
while IFS= read -r -d '' f; do
  n=$(grep -o '<script>' "$f" | wc -l)
  if [ "$n" -ne 1 ]; then say "FAIL $f has $n inline <script> blocks (expected 1)"; fail=1; fi
  if grep -qiE "script-src[^;]*unsafe-(inline|eval)" "$f"; then say "FAIL $f allows unsafe-inline/eval in script-src"; fail=1; fi
  if ! grep -q 'http-equiv="Content-Security-Policy"' "$f"; then say "FAIL $f has no CSP meta tag"; fail=1; fi
done < <(find _site -name '*.html' -print0)

# Every <iframe src> in output must be a host allowed by frame-src.
if grep -rhoE '<iframe[^>]*src="[^"]+"' _site | grep -oE 'src="[^"]+"' | grep -vE 'src="https://(player\.vimeo\.com|www\.youtube\.com)/' ; then
  say "FAIL iframe to a host not in frame-src"; fail=1
else
  say "ok   all iframes target frame-src hosts"
fi

exit $fail
