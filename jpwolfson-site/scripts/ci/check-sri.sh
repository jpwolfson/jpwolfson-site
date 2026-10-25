#!/usr/bin/env bash
# Re-download every SRI-protected external script named in the template and
# confirm the integrity attribute still matches. Run from jpwolfson-site/.
set -euo pipefail
tpl=src/_includes/base.njk
fail=0
n=0
# Pair each src URL with the integrity attribute that follows it.
while IFS=$'\t' read -r url want; do
  n=$((n+1))
  got="sha384-$(curl -fsSL --max-time 60 "$url" | openssl dgst -sha384 -binary | openssl base64 -A)"
  if [ "$got" = "$want" ]; then
    echo "ok   SRI matches for $url"
  else
    echo "FAIL SRI mismatch for $url"; echo "     in template: $want"; echo "     from CDN:    $got"
    echo "     If you intentionally changed the version, paste the CDN value into $tpl."
    fail=1
  fi
done < <(tr '\n' ' ' < "$tpl" | grep -oE '<script[^>]+src="https://[^"]+"[^>]+integrity="[^"]+"' \
         | sed -E 's/.*src="([^"]+)".*integrity="([^"]+)".*/\1\t\2/')
if [ "$n" -lt 1 ]; then echo "FAIL no SRI-protected script found in $tpl (integrity attribute missing?)"; fail=1; fi
exit $fail
