#!/usr/bin/env bash
# Review puzzles by hand, without Claude. See HAND.md.
#
#   tools/hand.sh start [count] [judge|games]   claim puzzles, download their scans, set up an editor for each
#   tools/hand.sh submit <puzzle>               send the review you saved from the editor
#
# Run from the root of your blitz checkout (a fork of EveryPuzzleProject/blitz,
# with the main repository as the "upstream" remote). Work files go in ../blitz-work.
set -euo pipefail
repo=EveryPuzzleProject/blitz
work=../blitz-work
state=$work/hand-session

die() { echo "$*" >&2; exit 1; }
[ -f publications/ORDER ] || die "Run this from the root of your blitz checkout."
command -v gh >/dev/null || die "Needs the GitHub CLI (https://cli.github.com), then: gh auth login"
gh auth status >/dev/null 2>&1 || die "Log in to GitHub first: gh auth login"
git remote | grep -qx upstream || die "No 'upstream' remote. Add it: git remote add upstream https://github.com/$repo.git"
mkdir -p "$work"

open_file() {  # best effort; otherwise the path is printed
  case "$(uname -s)" in
    Darwin) open "$1" ;;
    Linux) xdg-open "$1" >/dev/null 2>&1 & ;;
    MINGW*|MSYS*|CYGWIN*) start "" "$1" ;;
  esac
}

abs() { (cd "$(dirname "$1")" && echo "$(pwd -W 2>/dev/null || pwd)/$(basename "$1")"); }

start() {
  local n=${1:-1} only=${2:-}
  git fetch -q upstream
  git checkout -q --detach upstream/main
  local picks; picks=$(tools/pick.sh "$n" $only)
  [ -n "$picks" ] || die "Every open puzzle is taken right now${only:+ for $only}. Thanks for offering! Try again in a day or two."
  local user; user=$(gh api user --jq .login)
  local branch="hand-$user-$(date +%Y%m%d-%H%M)"
  git checkout -q -b "$branch" upstream/main
  local body="$work/pr-$branch.md" xdids=()
  echo "Reviewing by hand." > "$body"; echo >> "$body"
  while read -r pub xdid tag; do
    echo "Getting $xdid ..."
    gh release download "$tag" --repo "$repo" --pattern "$xdid.tar.gz" --dir "$work" --clobber
    tar -xzf "$work/$xdid.tar.gz" -C "$work"
    mkdir -p "publications/$pub/reviews/$xdid"
    cp "$work/$xdid/ocr.json" "publications/$pub/reviews/$xdid/ocr.json"
    cp tools/hand/edit.html "$work/$xdid/edit.html"
    local images; images=$(cd "$work/$xdid" && ls *.jpg *.png 2>/dev/null | sed 's/.*/"&"/' | paste -sd, -)
    { printf 'window.PUZZLE = {"ocr": '; cat "$work/$xdid/ocr.json";
      printf ', "images": [%s], "instructions": "%s"};\n' "$images" "https://github.com/$repo/blob/main/publications/$pub/INSTRUCTIONS.md"; } > "$work/$xdid/data.js"
    echo "- [ ] $xdid" >> "$body"
    xdids+=("$xdid")
  done <<< "$picks"
  git add publications
  git commit -q -m "Claim ${xdids[*]}"
  git push -q -u origin HEAD
  local url; url=$(gh pr create --draft --repo "$repo" --title "Review ${xdids[*]} (by hand)" --body-file "$body")
  printf 'branch=%s\npr=%s\nbody=%s\n' "$branch" "$url" "$body" > "$state"
  echo
  echo "Claimed: $url"
  echo "Open each puzzle's editor in your browser:"
  for x in "${xdids[@]}"; do echo "  $(abs "$work/$x/edit.html")"; done
  open_file "$work/${xdids[0]}/edit.html" || true
  echo
  echo "When you've saved a review from the editor: tools/hand.sh submit <puzzle>"
}

submit() {
  local xdid=${1:-}; [ -n "$xdid" ] || die "Which puzzle? tools/hand.sh submit judge1929-03-16"
  [ -f "$state" ] || die "No hand session here. Start one with: tools/hand.sh start"
  # shellcheck disable=SC1090
  . "$state"
  local pub=${xdid%%[0-9]*}
  [ -d "publications/$pub/reviews/$xdid" ] || git checkout -q "$branch"
  [ -d "publications/$pub/reviews/$xdid" ] || die "$xdid isn't one of the puzzles you claimed."
  [ "$(git branch --show-current)" = "$branch" ] || git checkout -q "$branch"
  # The editor's download: newest of ~/Downloads/<xdid>.review*.json, or one put in the work folder.
  local f
  f=$(ls -t "$work/$xdid/review.json" "$HOME"/Downloads/"$xdid".review*.json 2>/dev/null | head -1 || true)
  [ -n "$f" ] || die "No saved review for $xdid. In the editor, press Save review (it goes to your Downloads folder)."
  echo "Using $f"
  cp "$f" "publications/$pub/reviews/$xdid/review.json"
  if command -v python3 >/dev/null || command -v python >/dev/null; then
    "$(command -v python3 || command -v python)" tools/check_reviews.py || die "That review isn't well-formed; save it again from the editor."
  fi
  git add "publications/$pub/reviews/$xdid/review.json"
  git commit -q -m "Review $xdid (by hand)"
  git push -q
  sed -i.bak "s/^- \[ \] $xdid\$/- [x] $xdid/" "$body" && rm -f "$body.bak"
  gh pr edit "$pr" --body-file "$body" >/dev/null
  echo "Sent $xdid. Its record: https://everypuzzleproject.github.io/blitz/view.html?p=$pub/$xdid&from=$(gh api user --jq .login):$branch"
  if ! grep -q '^- \[ \]' "$body"; then
    gh pr ready "$pr" >/dev/null
    echo "That was the last one: your pull request is ready for review. Thank you! $pr"
  fi
}

case "${1:-}" in
  start) shift; start "$@" ;;
  submit) shift; submit "$@" ;;
  *) sed -n '2,8p' "$0" | sed 's/^# \{0,1\}//' ;;
esac
