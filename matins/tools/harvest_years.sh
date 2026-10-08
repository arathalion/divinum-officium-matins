#!/bin/bash
# harvest_years.sh FIRST_YEAR LAST_YEAR [OUTDIR] — run harvest_day.pl for every
# date in the range (in parallel) and write one gzipped JSON-lines file per year.
set -euo pipefail
here="$(cd "$(dirname "$0")" && pwd)"
first=$1; last=$2; out=${3:-"$here/../cache/harvest"}
jobs=${JOBS:-$(sysctl -n hw.ncpu 2>/dev/null || nproc)}
mkdir -p "$out"
for y in $(seq "$first" "$last"); do
  [ -s "$out/$y.jsonl.gz" ] && continue
  tmp="$out/$y.tmp"; rm -rf "$tmp"; mkdir -p "$tmp"
  # Each day goes to its own file: the lines are too long to share a pipe.
  python3 -c "
import datetime
d=datetime.date($y,1,1)
while d.year==$y:
    print(d.strftime('%m-%d-%Y')); d+=datetime.timedelta(1)" |
    xargs -P "$jobs" -I{} sh -c 'perl "$1" "$2" > "$3/$2.json" 2>> "$3/err"' _ "$here/harvest_day.pl" {} "$tmp"
  cat "$tmp"/*.json | gzip > "$out/$y.jsonl.gz.part"
  [ -s "$tmp/err" ] && cp "$tmp/err" "$out/$y.err"
  rm -rf "$tmp"
  mv "$out/$y.jsonl.gz.part" "$out/$y.jsonl.gz"
  echo "$y: $(gzip -dc "$out/$y.jsonl.gz" | wc -l | tr -d ' ') days"
done
