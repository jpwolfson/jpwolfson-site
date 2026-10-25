#!/usr/bin/env bash
# src/files/ is passthrough-copied to the production origin. Only documents and
# images may live there; never HTML, SVG, scripts, or anything executable.
# Run from jpwolfson-site/.
set -euo pipefail
allow='pdf|png|jpg|jpeg'
max_bytes=$((25 * 1024 * 1024))
fail=0
while IFS= read -r -d '' f; do
  base=$(basename "$f")
  [ "$base" = ".gitkeep" ] && continue
  ext="${base##*.}"; ext="${ext,,}"
  if ! [[ "$ext" =~ ^($allow)$ ]]; then echo "FAIL disallowed file type: $f"; fail=1; fi
  size=$(stat -c %s "$f")
  if [ "$size" -gt "$max_bytes" ]; then echo "FAIL over 25 MB: $f ($size bytes)"; fail=1; fi
  # Content sniff: a 'PDF' must start with %PDF, images with their magic bytes.
  case "$ext" in
    pdf)      head -c 4 "$f" | grep -q '%PDF' || { echo "FAIL not a real PDF: $f"; fail=1; } ;;
    png)      head -c 8 "$f" | xxd -p | grep -qi '^89504e470d0a1a0a' || { echo "FAIL not a real PNG: $f"; fail=1; } ;;
    jpg|jpeg) head -c 3 "$f" | xxd -p | grep -qi '^ffd8ff' || { echo "FAIL not a real JPEG: $f"; fail=1; } ;;
  esac
done < <(find src/files -type f -print0)
[ $fail -eq 0 ] && echo "ok   src/files contains only allowed document/image types"
exit $fail
