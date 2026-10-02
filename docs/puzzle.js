// Load a reviewed puzzle (the packet's ocr.json plus the volunteer's review.json)
// from GitHub and apply the review's corrections, giving the puzzle as printed.

const REPO = 'EveryPuzzleProject/puzzle-review';

// from: "owner:branch" (a fork named puzzle-review), "owner/repo:branch", or empty for main here.
function rawBase(from) {
  if (from === 'local') return '..';  // testing: the repo root served locally
  if (!from)return `https://raw.githubusercontent.com/${REPO}/main`;
  let [who, branch] = from.split(':');
  if (!who.includes('/')) who += '/puzzle-review';
  return `https://raw.githubusercontent.com/${who}/${branch || 'main'}`;
}

async function loadPuzzle(pub, id, from) {
  const base = `${rawBase(from)}/publications/${pub}/reviews/${id}`;
  const get = async f => {
    const r = await fetch(`${base}/${f}`, {cache: 'no-cache'});
    if (!r.ok) throw new Error(`${f}: ${r.status}`);
    return r.json();
  };
  const ocr = await get('ocr.json');
  const review = await get('review.json').catch(() => null);
  return buildPuzzle(ocr, review);
}

function puzzleDate(xdid) {
  const m = xdid.match(/(\d{4})-(\d\d)-(\d\d)/);
  if (!m) return '';
  return new Date(Date.UTC(+m[1], +m[2] - 1, +m[3]))
    .toLocaleDateString('en-US', {year: 'numeric', month: 'long', day: 'numeric', timeZone: 'UTC'});
}

function buildPuzzle(ocr, review) {
  const rv = review || {};
  const grid = ocr.grid.map(r => [...r]);
  let answers = ocr.answers ? ocr.answers.map(r => [...r]) : null;
  if (answers && (answers.length !== grid.length || answers[0].length !== grid[0].length)) answers = null;
  const meta = {title: ocr.title || '', author: ocr.author || '', byline: ocr.byline || ''};
  const clues = {};
  for (const [k, v] of Object.entries(ocr.clues || {})) clues[k] = v.text;
  const captions = Object.keys(ocr.captions || {}).sort((a, b) => a - b).map(k => ocr.captions[k]);
  const set = (g, m, v) => { if (g[m[1] - 1] && m[2] - 1 < g[m[1] - 1].length) g[m[1] - 1][m[2] - 1] = v; };

  for (const [item, value] of Object.entries(rv.corrections || {})) {
    const i = item.indexOf(':'), kind = item.slice(0, i), key = item.slice(i + 1);
    const rc = key.match(/^r(\d+)c(\d+)$/);
    if (kind === 'meta') meta[key] = value;
    else if (kind === 'clue') { if (value === '') delete clues[key]; else clues[key] = value; }
    else if (kind === 'other' && /^\d+$/.test(key)) captions[+key - 1] = value;
    else if (kind === 'grid' && rc) set(grid, rc, value);
    else if (kind === 'cell' && rc) {
      if (answers) set(answers, rc, value);
      const cur = grid[rc[1] - 1]?.[rc[2] - 1];
      if (cur !== undefined) set(grid, rc, value === '#' ? '#' : cur === '#' ? '.' : cur);
    }
  }

  // The answer key decides black squares when there is one: it's what the reviewers checked first.
  const R = grid.length, C = grid[0].length;
  const black = (r, c) => answers ? answers[r][c] === '#' : grid[r][c] === '#';
  const white = (r, c) => r >= 0 && c >= 0 && r < R && c < C && !black(r, c);

  // Standard numbering, or the old style that also numbers unchecked single squares
  // across, whichever matches the printed clue list better.
  const numbering = singles => {
    const nums = {}, labels = new Set();
    let n = 0;
    for (let r = 0; r < R; r++) for (let c = 0; c < C; c++) {
      if (!white(r, c)) continue;
      const a = !white(r, c - 1) && (white(r, c + 1) || (singles && !white(r - 1, c) && !white(r + 1, c)));
      const d = !white(r - 1, c) && white(r + 1, c);
      if (a || d) { n++; nums[`${r},${c}`] = n; if (a) labels.add('A' + n); if (d) labels.add('D' + n); }
    }
    return {nums, labels};
  };
  const have = Object.keys(clues);
  const score = nb => have.filter(l => !nb.labels.has(l)).length + [...nb.labels].filter(l => !(l in clues)).length;
  const plain = numbering(false), alt = numbering(true);
  const nb = score(alt) < score(plain) ? alt : plain;

  const cells = [];
  for (let r = 0; r < R; r++) {
    const row = [];
    for (let c = 0; c < C; c++) {
      if (!white(r, c)) { row.push(null); continue; }
      const ch = answers ? answers[r][c] : '';
      row.push({r, c, num: nb.nums[`${r},${c}`] || 0, sol: /^[A-Za-z]$/.test(ch) ? ch.toUpperCase() : null});
    }
    cells.push(row);
  }

  // Words: each numbered start, across and down.
  const words = [];
  for (const [rc, n] of Object.entries(nb.nums)) {
    const [r0, c0] = rc.split(',').map(Number);
    for (const dir of ['A', 'D']) {
      if (!nb.labels.has(dir + n)) continue;
      const sq = [];
      let r = r0, c = c0;
      while (white(r, c)) { sq.push([r, c]); if (dir === 'A') c++; else r++; }
      words.push({id: dir + n, dir, n, cells: sq, text: clues[dir + n] ?? '[no clue printed]'});
    }
  }
  words.sort((a, b) => (a.dir === b.dir ? a.n - b.n : a.dir < b.dir ? -1 : 1));

  const sic = Object.entries(rv.sic || {}).map(([k, v]) => `${k.replace(/^\w+:/, '')}: ${v}`);
  const keyed = cells.flat().filter(Boolean);
  return {
    id: ocr.xdid, date: puzzleDate(ocr.xdid), source: ocr.source, R, C, cells, words,
    title: meta.title, author: meta.author, byline: meta.byline,
    captions: captions.filter(s => s && s.trim()),
    hasKey: keyed.length > 0 && keyed.every(x => x.sol),
    sic, note: rv.note || '', model: rv.model || '', ready: rv.ready,
  };
}
