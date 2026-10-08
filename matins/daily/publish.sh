#!/bin/bash
# publish.sh OUT_DIR — merge freshly built daily files into the `daily-data`
# branch and push it. Earlier dates are kept (their web pages stay valid); the
# branch is rewritten as a single commit each time so its history stays small.
#
# Used by .github/workflows/daily-readings.yml; also runnable locally.
set -euo pipefail
out=$(cd "$1" && pwd)
repo=$(git rev-parse --show-toplevel)
work=$(mktemp -d)
trap 'rm -rf "$work"' EXIT

cd "$repo"
if git fetch -q origin daily-data 2>/dev/null; then
  git archive FETCH_HEAD | tar -x -C "$work"
fi
cp -R "$out"/. "$work"/

cd "$work"
git init -q -b daily-data
git add -A
git -c user.name="matins-bot" -c user.email="matins-bot@users.noreply.github.com" \
  commit -q -m "Daily readings, generated $(date -u +%Y-%m-%dT%H:%MZ)"
# In GitHub Actions, checkout leaves its token as an extraheader on the main
# repository; reuse it for this temporary one.
auth=()
hdr=$(git -C "$repo" config --get-regexp '^http\..*\.extraheader$' 2>/dev/null | head -1 | cut -d' ' -f2- || true)
if [ -n "$hdr" ]; then auth=(-c "http.https://github.com/.extraheader=$hdr"); fi
git ${auth[@]+"${auth[@]}"} push -q -f "$(git -C "$repo" remote get-url origin)" daily-data:daily-data
echo "published $(find . -name '*.json' -not -path './.git/*' | wc -l | tr -d ' ') files to daily-data"
