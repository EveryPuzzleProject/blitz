"""Compare a whole-page transcription with our reviewed xd: grid squares and clue text."""
import re, sys, difflib
got_p, ref_p = sys.argv[1], sys.argv[2]


def load(p):
    t = open(p, encoding='utf-8').read().replace('\r', '')
    lines = t.split('\n')
    # grid = longest run of lines made only of letters/#
    runs, cur = [], []
    for l in lines:
        if l and re.fullmatch(r'[A-Za-z#_.]+', l.strip()):
            cur.append(l.strip().upper())
        else:
            if cur: runs.append(cur)
            cur = []
    if cur: runs.append(cur)
    grid = max(runs, key=len) if runs else []
    clues = {m[0]: (m[1].strip(), m[2].strip()) for m in re.findall(r'^([AD]\d+)\. (.*?) ~ (.*)$', t, re.M)}
    return grid, clues


def norm(s):
    return re.sub(r'\s+', ' ', s.replace('—', '-').replace('–', '-').replace('’', "'").replace('“', '"').replace('”', '"')).strip()


g1, c1 = load(got_p)
g2, c2 = load(ref_p)
print('grid size', len(g1), 'x', len(g1[0]) if g1 else 0, 'vs', len(g2), 'x', len(g2[0]))
if len(g1) == len(g2) and len(g1[0]) == len(g2[0]):
    tot = sum(1 for r in g2 for ch in r)
    bad = [(r, c, g1[r][c], g2[r][c]) for r in range(len(g2)) for c in range(len(g2[0])) if g1[r][c] != g2[r][c]]
    print('squares wrong', len(bad), 'of', tot, bad[:20])
keys = sorted(set(c1) | set(c2))
missing = [k for k in c2 if k not in c1]
extra = [k for k in c1 if k not in c2]
exact = sum(1 for k in c2 if k in c1 and norm(c1[k][0]) == norm(c2[k][0]))
print('clues', len(c2), 'exact', exact, 'missing', missing, 'extra', extra)
for k in c2:
    if k in c1 and norm(c1[k][0]) != norm(c2[k][0]):
        print(' ', k, '| got:', c1[k][0], '| ref:', c2[k][0])
