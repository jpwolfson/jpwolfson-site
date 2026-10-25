#!/usr/bin/env bash
# src/files/ is passthrough-copied to the production origin. Only documents and
# images may live there; never HTML, SVG, scripts, or anything executable.
# Portable (Linux and macOS, bash 3.2+). Run from jpwolfson-site/.
set -euo pipefail
allow='pdf|png|jpg|jpeg'
max_bytes=$((25 * 1024 * 1024))
fail=0
hexhead() { od -An -tx1 -N "$2" "$1" | tr -d ' \n'; }
while IFS= read -r f; do
  base=$(basename "$f")
  [ "$base" = ".gitkeep" ] && continue
  if [ ! -f "$f" ] || [ -L "$f" ]; then echo "FAIL not a regular file: $f"; fail=1; continue; fi
  ext=$(printf '%s' "${base##*.}" | tr '[:upper:]' '[:lower:]')
  if ! printf '%s' "$ext" | grep -Eq "^($allow)$"; then echo "FAIL disallowed file type: $f"; fail=1; continue; fi
  size=$(wc -c < "$f" | tr -d ' ')
  if [ "$size" -gt "$max_bytes" ]; then echo "FAIL over 25 MB: $f ($size bytes)"; fail=1; fi
  case "$ext" in
    pdf)      [ "$(hexhead "$f" 4)" = "25504446" ]         || { echo "FAIL not a real PDF: $f"; fail=1; } ;;
    png)      [ "$(hexhead "$f" 8)" = "89504e470d0a1a0a" ] || { echo "FAIL not a real PNG: $f"; fail=1; } ;;
    jpg|jpeg) [ "$(hexhead "$f" 3)" = "ffd8ff" ]           || { echo "FAIL not a real JPEG: $f"; fail=1; } ;;
  esac
done < <(find src/files -mindepth 1 \( -type f -o -type l \))
[ $fail -eq 0 ] && echo "ok   src/files contains only allowed document/image types"
exit $fail
