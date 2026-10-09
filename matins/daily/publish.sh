#!/bin/bash
# publish.sh OUT_DIR — merge freshly built daily files into the `daily-data`
# branch and push it. Keeps the past 60 days (so recent pages stay valid) and
# the days ahead, rebuilds the per-calendar indexes, and commits the result as
# a single commit. Objects already on GitHub are not uploaded again.
#
# Used by .github/workflows/daily-readings.yml; also runnable locally.
set -euo pipefail
here="$(cd "$(dirname "$0")" && pwd)"
out=$(cd "$1" && pwd)
repo=$(git rev-parse --show-toplevel)
work=$(mktemp -d)
index=$(mktemp)
rm -f "$index"
trap 'rm -rf "$work" "$index"' EXIT

cd "$repo"
if git fetch -q origin daily-data 2>/dev/null; then
  git archive FETCH_HEAD | tar -x -C "$work"
fi
cp -R "$out"/. "$work"/
python3 "$here/build_month_epubs.py" "$work"
python3 "$here/build_index.py" "$work"

# Stage the tree into a scratch index of this repository and commit it with no
# parent: the branch stays one commit, and push only sends the new objects.
GIT_INDEX_FILE="$index" GIT_WORK_TREE="$work" git add -A
tree=$(GIT_INDEX_FILE="$index" git write-tree)
commit=$(git -c user.name="matins-bot" -c user.email="matins-bot@users.noreply.github.com" \
  commit-tree "$tree" -m "Daily readings, generated $(date -u +%Y-%m-%dT%H:%MZ)")

# In GitHub Actions the checkout's token is already in this repository's config.
git push -q -f origin "$commit:refs/heads/daily-data"
echo "published $(find "$work" -name '*.json' | wc -l | tr -d ' ') files to daily-data"
