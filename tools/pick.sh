#!/usr/bin/env bash
# Print the next N open puzzles, oldest first, one per line: "<pub> <xdid> <release tag>".
# A puzzle is open when puzzles.tsv says so, no review.json for it is on
# upstream main, and no open pull request updated in the last 48 hours names it.
# Usage, from the repository root: git fetch upstream && tools/pick.sh 3
set -eu
n=${1:-3}
repo=EveryPuzzleProject/puzzle-review
claimed=$(gh pr list --repo "$repo" --state open --limit 200 --json updatedAt,body \
  --jq '.[] | select((.updatedAt | fromdateiso8601) > (now - 172800)) | .body' \
  | grep -oE '[a-z]+[0-9]{4}-[0-9]{2}-[0-9]{2}[a-z]?' | sort -u || true)
reviewed=$(git ls-tree -r --name-only upstream/main publications \
  | sed -n 's#^publications/[^/]*/reviews/\([^/]*\)/review\.json$#\1#p')
for pub in $(tr -d '\r' < publications/ORDER); do
  # columns: xdid date number packet state reason person updated (some may be empty)
  tr -d '\r' < "publications/$pub/puzzles.tsv" | awk -F'\t' 'NR > 1 && $5 == "open" { print $1, $4 }' | while read -r xdid packet; do
    grep -qx "$xdid" <<<"$claimed" && continue
    grep -qx "$xdid" <<<"$reviewed" && continue
    echo "$pub $xdid $packet"
  done
done | head -n "$n"
