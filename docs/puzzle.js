// Load a reviewed puzzle (the packet's ocr.json plus the volunteer's review.json)
// from GitHub and apply the review's corrections, giving the puzzle as printed.

const REPO = 'EveryPuzzleProject/blitz';

// from: "owner:branch" (a fork named blitz), "owner/repo:branch", or empty for main here.
function rawBase(from) {
  if (from === 'local') return '..';  // testing: the repo root served locally
  if (!from)return `https://raw.githubusercontent.com/${REPO}/main`;
  let [who, branch] = from.split(':');
  if (!who.includes('/')) who += '/blitz';
  return `https://raw.githubusercontent.com/${who}/${branch || 'main'}`;
}

// Publications that have their own repo (EveryPuzzleProject/<pub>) keep puzzles.tsv, xd/ and
// reviews/ at its root; the rest are still under publications/<pub> here. When every
// publication has moved, this set and the old path go.
const OWN_REPO = new Set(['judge']);

function pubRoot(pub, from) {
  if (!OWN_REPO.has(pub)) return `${rawBase(from)}/publications/${pub}`;
  if (from === 'local') return `../../${pub}`;  // testing: the publication's checkout beside blitz
  return `https://raw.githubusercontent.com/EveryPuzzleProject/${pub}/main`;
}

function pubBlob(pub, path) {
  return OWN_REPO.has(pub) ? `https://github.com/EveryPuzzleProject/${pub}/blob/main/${path}`
    : `https://github.com/${REPO}/blob/main/publications/${pub}/${path}`;
}

// The published .xd (every correction so far, a person's included) when there
// is one; otherwise a volunteer's review applied to its OCR reading.
async function loadPuzzle(pub, id, from) {
  const root = pubRoot(pub, from);
  const get = async (path, as) => {
    const r = await fetch(`${root}/${path}`, {cache: 'no-cache'});
    if (!r.ok) throw new Error(`${path}: ${r.status}`);
    return as === 'text' ? r.text() : r.json();
  };
  if (!from || from === 'local') {
    const xd = await get(`xd/${id}.xd`, 'text').catch(() => null);
    if (xd) return {...buildPuzzle(parseXd(xd, id), null), fromXd: true};
  }
  const ocr = await get(`reviews/${id}/ocr.json`);
  const review = await get(`reviews/${id}/review.json`).catch(() => null);
  return buildPuzzle(ocr, review);
}

// An .xd file in the shape of an OCR reading: headers, grid (letters are the
// answers), clues "A1. text ~ ANSWER", and notes.
function parseXd(text, id) {
  const parts = text.replace(/\r\n/g, '\n').split(/\n\n\n+/);
  const head = {};
  for (const l of parts[0].split('\n')) { const i = l.indexOf(': '); if (i > 0) head[l.slice(0, i)] = l.slice(i + 2); }
  const rows = (parts[1] || '').split('\n').filter(r => r.trim());
  const clues = {};
  for (const l of (parts[2] || '').split('\n')) {
    const m = l.match(/^([AD]\d+)\. (.*)$/);
    if (!m) continue;
    const k = m[2].lastIndexOf(' ~ ');
    clues[m[1]] = {text: k >= 0 ? m[2].slice(0, k) : m[2]};
  }
  return {
    xdid: id, source: head.Source, solutionSource: head['Solution-Source'], title: head.Title, author: head.Author, byline: head.Byline, captions: {},
    grid: rows.map(r => [...r].map(ch => (ch === '#' ? '#' : '.')).join('')),
    answers: rows.some(r => /[A-Za-z]/.test(r)) ? rows : null,
    clues, note: (parts[3] || '').trim(),
  };
}

// Every puzzle of a publication with its state, from puzzles.tsv on main.
async function loadStates(pub, from) {
  const tsv = await fetch(`${pubRoot(pub, from === 'local' ? 'local' : '')}/puzzles.tsv`, {cache: 'no-cache'}).then(r => r.text());
  const [cols, ...lines] = tsv.trim().split(/\r?\n/);
  const names = cols.split('\t');
  return lines.map(l => Object.fromEntries(l.split('\t').map((v, i) => [names[i], v])));
}

const REASONS = {
  'scan-missing': 'Part of the scan is missing',
  'no-key': 'Answer key not found',
  'unread': "Some answer squares can't be read",
  'quick': 'One small check left',
  'ruling': 'A printed mistake to rule on',
  'not-found': 'Not found in the scans yet',
};

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
    id: ocr.xdid, date: puzzleDate(ocr.xdid), source: ocr.source, solutionSource: ocr.solutionSource || '', R, C, cells, words,
    title: meta.title, author: meta.author, byline: meta.byline,
    captions: captions.filter(s => s && s.trim()),
    hasKey: keyed.length > 0 && keyed.every(x => x.sol),
    sic, note: rv.note || ocr.note || '', model: rv.model || '', ready: rv.ready,
  };
}
