#!/usr/bin/env python3
"""Fossil versions: measure how stale the dependencies of new npm packages are on the
day they are first published, and count a simple "written from memory" fingerprint.

Inputs (see fetch_sample.py / fetch_deps.py):
  data/sample.jsonl  one slim record per sampled package (first version + its dependency ranges)
  data/deps.jsonl    release timeline (stable versions -> publish time) for the most-used dependencies
Outputs: CSV files in results/ and a summary printed to stdout.
"""
import json, re, csv, sys, math, collections, datetime as dt, os
import numpy as np

DAY = 86400.0
SAMPLE = sys.argv[1] if len(sys.argv) > 1 else 'data/sample.jsonl'
DEPS = sys.argv[2] if len(sys.argv) > 2 else 'data/deps.jsonl'
OUT = sys.argv[3] if len(sys.argv) > 3 else 'results'
REGISTRY_SIZE, SAMPLE_SIZE = 4669852, 250000   # names in all-the-package-names 2.0.2622, names drawn
os.makedirs(OUT, exist_ok=True)

def ts(s): return dt.datetime.fromisoformat(s.replace('Z', '+00:00')).timestamp()
def vkey(v): return tuple(int(x) for x in v.split('.'))
def utc(T): return dt.datetime.fromtimestamp(T, dt.timezone.utc)
def half(T): d = utc(T); return f"{d.year}H{1 if d.month <= 6 else 2}"
def quarter(T): d = utc(T); return f"{d.year}Q{(d.month - 1) // 3 + 1}"
def year(T): return utc(T).year
def wilson(k, n, z=1.96):
    if n == 0: return (float('nan'),) * 2
    p = k / n; den = 1 + z * z / n
    c = (p + z * z / (2 * n)) / den; h = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / den
    return (c - h, c + h)

# ---- dependency release timelines -------------------------------------------------
VT, NEXT = {}, {}          # dep -> {version: publish time}; dep -> {version: time a higher version first appeared}
for line in open(DEPS):
    r = json.loads(line)
    if r.get('err') or not r.get('vs'): continue
    m = {}
    for v, t in r['vs'].items():
        try: m[v] = ts(t)
        except Exception: pass
    VT[r['name']] = m
    items = sorted((t, vkey(v), v) for v, t in m.items())
    nx = {}
    for i, (t, k, v) in enumerate(items):
        nx[v] = next((items[j][0] for j in range(i + 1, len(items)) if items[j][1] > k), None)
    NEXT[r['name']] = nx

# ---- sampled packages ---------------------------------------------------------------
PIN = re.compile(r'^[\^~=v\s]*?(\d+)\.(\d+)\.(\d+)\s*$')   # ^1.2.3, ~1.2.3, 1.2.3 -> the version the author named
pk, everyone = [], []
for line in open(SAMPLE):
    try: r = json.loads(line)
    except Exception: continue
    if r.get('err') or not r.get('first_t'): continue
    try: T = ts(r['first_t'])
    except Exception: continue
    fd = r.get('fd') or {'d': {}, 'v': {}, 'p': {}}
    everyone.append((T, r['nv'], sum(len(fd[k]) for k in 'dvp'), bool(r['repo'])))
    if T < ts('2016-01-01T00:00:00Z'): continue
    pins = []
    for kind in 'dvp':                       # dependencies, devDependencies, peerDependencies of the FIRST version
        for dep, rng in fd[kind].items():
            if not isinstance(rng, str): continue
            m = PIN.match(rng.strip())
            if not m or dep not in VT: continue
            v = '.'.join(m.groups()); t = VT[dep].get(v)
            if t is None or t > T + DAY: continue
            nx = NEXT[dep].get(v)
            superseded = (T - nx) / DAY if (nx is not None and nx <= T) else 0.0   # days a newer version had existed
            a, b, c = map(int, m.groups())
            pins.append({'dep': dep, 'v': v, 'kind': kind, 'age': (T - t) / DAY, 'sup': superseded,
                         'round': b == 0 and c == 0, 't': t})
    if len(pins) >= 3:
        pk.append({'name': r['name'], 'T': T, 'pins': pins, 'nv': r['nv'], 'repo': bool(r['repo']), 'desc': r.get('desc') or ''})

def fingerprint(pins, kinds='dvp', k=2, frac=0.4):
    """>=k pins of the form x.0.0 that had already been superseded for >=30 days, making up >=frac of the pins."""
    P = [x for x in pins if x['kind'] in kinds]
    if len(P) < 3: return None
    sr = sum(1 for x in P if x['round'] and x['sup'] >= 30)
    return sr >= k and sr / len(P) >= frac

sig = collections.Counter(tuple(sorted((x['dep'], x['v']) for x in p['pins'])) for p in pk)
for p in pk:
    ages = np.array([x['age'] for x in p['pins']]); sup = np.array([x['sup'] for x in p['pins']])
    p['F'] = fingerprint(p['pins']); p['F_nopeer'] = fingerprint(p['pins'], 'dv'); p['F_strict'] = fingerprint(p['pins'], 'dvp', 3, 0.5)
    p['med_age'] = float(np.median(ages)); p['newest_age'] = float(ages.min())
    p['fresh'] = bool((sup <= 0).mean() >= 0.8)             # >=80% of pins were the newest release on the day
    p['sup180'] = float((sup >= 180).mean())
    p['clone'] = sig[tuple(sorted((x['dep'], x['v']) for x in p['pins']))] >= 5   # mass-cloned manifests (spam farms)

def table(keyfn, start, path):
    G = collections.defaultdict(list)
    for p in pk: G[keyfn(p['T'])].append(p)
    rows = []
    for g in sorted(G):
        if g < start: continue
        L = G[g]; n = len(L); k = sum(p['F'] for p in L); lo, hi = wilson(k, n)
        nd = [p for p in L if not p['clone']]; rv = [p for p in L if p['repo'] and p['nv'] >= 2]
        np_ = [p['F_nopeer'] for p in L if p['F_nopeer'] is not None]
        rows.append({'period': g, 'n': n, 'fingerprint_pct': round(100 * k / n, 2), 'ci_lo': round(100 * lo, 2), 'ci_hi': round(100 * hi, 2),
                     'fingerprint_pct_no_peer_deps': round(100 * np.mean(np_), 2),
                     'fingerprint_pct_strict': round(100 * np.mean([p['F_strict'] for p in L]), 2),
                     'fingerprint_pct_no_clones': round(100 * np.mean([p['F'] for p in nd]), 2), 'n_no_clones': len(nd),
                     'fingerprint_pct_repo_and_2plus_versions': round(100 * np.mean([p['F'] for p in rv]), 2),
                     'median_dep_age_days': round(float(np.median([p['med_age'] for p in L]))),
                     'median_dep_age_days_no_clones': round(float(np.median([p['med_age'] for p in nd]))),
                     'fresh_pct': round(100 * np.mean([p['fresh'] for p in L]), 2),
                     'fresh_pct_no_clones': round(100 * np.mean([p['fresh'] for p in nd]), 2),
                     'newest_dep_older_than_1y_pct': round(100 * np.mean([p['newest_age'] > 365 for p in L]), 2),
                     'pins_superseded_180d_pct': round(100 * np.mean([p['sup180'] for p in L]), 2)})
    with open(path, 'w', newline='') as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0])); w.writeheader(); w.writerows(rows)
    return rows

H = table(half, '2019H1', f'{OUT}/half_year.csv')
Q = table(quarter, '2019Q1', f'{OUT}/quarterly.csv')

# per-library share of pins that are a superseded x.0.0 (runtime + dev only)
LIBS = ['@types/node', 'react', 'eslint', 'jest', 'vitest', 'tsup', 'rollup', 'vite', 'commander', 'prettier', 'typescript', 'axios', 'webpack', 'mocha']
tab = collections.defaultdict(lambda: collections.defaultdict(lambda: [0, 0]))
for p in pk:
    y = year(p['T'])
    for x in p['pins']:
        if x['dep'] in LIBS and x['kind'] in 'dv':
            t = tab[x['dep']][y]; t[0] += 1; t[1] += (x['round'] and x['sup'] >= 30)
with open(f'{OUT}/per_library.csv', 'w', newline='') as f:
    w = csv.writer(f); w.writerow(['library', 'year', 'pins', 'stale_round_pins', 'pct'])
    for l in LIBS:
        for y in range(2019, 2027):
            n, k = tab[l][y]
            w.writerow([l, y, n, k, round(100 * k / n, 2) if n else ''])

# registry growth
scale = REGISTRY_SIZE / SAMPLE_SIZE
with open(f'{OUT}/volume.csv', 'w', newline='') as f:
    w = csv.writer(f); w.writerow(['year', 'sampled', 'estimated_packages_created', 'no_dependencies_pct', 'single_version_pct'])
    cy = collections.defaultdict(list)
    for a in everyone: cy[year(a[0])].append(a)
    for y in sorted(cy):
        if y < 2016: continue
        A = cy[y]; w.writerow([y, len(A), round(len(A) * scale), round(100 * np.mean([a[2] == 0 for a in A]), 1), round(100 * np.mean([a[1] == 1 for a in A]), 1)])

# what the fingerprint packages reach for, vs the pre-AI baseline
def share(L):
    c = collections.Counter()
    for p in L:
        for d in set(x['dep'] for x in p['pins']): c[d] += 1
    return {k: v / len(L) for k, v in c.items()}
F26 = [p for p in pk if year(p['T']) == 2026 and p['F']]; R26 = [p for p in pk if year(p['T']) == 2026 and not p['F']]
B = [p for p in pk if year(p['T']) in (2021, 2022) and not p['clone']]
sF, sR, sB = share(F26), share(R26), share(B)
with open(f'{OUT}/stack.csv', 'w', newline='') as f:
    w = csv.writer(f); w.writerow(['library', 'fingerprint_2026_pct', 'other_2026_pct', 'all_2021_2022_pct'])
    for l in ['vitest', 'jest', 'mocha', 'tsup', 'rollup', 'webpack', 'vite', 'esbuild', 'zod', 'commander', 'yargs', 'axios', 'eslint', 'prettier', '@modelcontextprotocol/sdk', 'tsx', '@types/node', 'typescript']:
        w.writerow([l, round(100 * sF.get(l, 0), 1), round(100 * sR.get(l, 0), 1), round(100 * sB.get(l, 0), 1)])

c = collections.Counter()
for p in F26:
    for x in p['pins']:
        if x['round'] and x['sup'] >= 30: c[(x['dep'], x['v'], utc(x['t']).strftime('%Y-%m'))] += 1
with open(f'{OUT}/top_round_pins_2026.csv', 'w', newline='') as f:
    w = csv.writer(f); w.writerow(['dependency', 'version', 'released', 'count_in_fingerprint_packages_2026'])
    for (d, v, m), n in c.most_common(40): w.writerow([d, v, m, n])

# ---- alternative explanations: scaffolds, monorepos, templates -----------------------------
REACT = {'react', 'react-dom', '@types/react', '@types/react-dom'}
TEMPLATE = re.compile(r'template|starter|boilerplate|scaffold|example|demo', re.I)
def scope(name): return name.split('/')[0] if name.startswith('@') else name
G = collections.defaultdict(list)
for p in pk: G[half(p['T'])].append(p)
with open(f'{OUT}/robustness.csv', 'w', newline='') as f:
    w = csv.writer(f)
    w.writerow(['period', 'n', 'fingerprint_pct', 'excluding_packages_that_depend_on_next_or_react_dom', 'ignoring_react_family_pins',
                'unscoped_packages_only', 'scoped_packages_only', 'one_package_per_scope', 'excluding_template_like_names'])
    for h in sorted(G):
        if h < '2019H1': continue
        L = G[h]; pct = lambda xs: round(100 * float(np.mean([x for x in xs if x is not None])), 2)
        seen, one = set(), []
        for p in L:
            if scope(p['name']) not in seen: seen.add(scope(p['name'])); one.append(p['F'])
        w.writerow([h, len(L), pct([p['F'] for p in L]),
                    pct([p['F'] for p in L if not any(x['dep'] in ('next', 'react-dom') for x in p['pins'])]),
                    pct([fingerprint([x for x in p['pins'] if x['dep'] not in REACT]) for p in L]),
                    pct([p['F'] for p in L if not p['name'].startswith('@')]), pct([p['F'] for p in L if p['name'].startswith('@')]),
                    pct(one), pct([p['F'] for p in L if not TEMPLATE.search(p['name'] + ' ' + p['desc'])])])
F1 = [p for p in G['2026H1'] if p['F']]
full = collections.Counter(tuple(sorted((x['dep'], x['v']) for x in p['pins'])) for p in F1)
combo = collections.Counter(tuple(sorted((x['dep'], x['v']) for x in p['pins'] if x['round'] and x['sup'] >= 30)) for p in F1)
uniq = sum(1 for p in F1 if full[tuple(sorted((x['dep'], x['v']) for x in p['pins']))] == 1) / len(F1)
print(f"2026H1 fingerprint packages: {len(F1)}; with a manifest no other sampled package shares: {100*uniq:.1f}%; "
      f"distinct round-pin combinations: {len(combo)}; ten most common combinations cover {100*sum(v for _, v in combo.most_common(10))/len(F1):.1f}%")

# ---- summary ---------------------------------------------------------------------------
print(f"sampled packages with a first version: {len(everyone)}; with >=3 datable pins (2016+): {len(pk)}")
print("half-year | n | fingerprint % (95% CI) | strict | no clones | median dep age (d) | fresh %")
for r in H:
    print(f"{r['period']} | {r['n']:6d} | {r['fingerprint_pct']:5.1f} ({r['ci_lo']:.1f}-{r['ci_hi']:.1f}) | {r['fingerprint_pct_strict']:4.1f} | {r['fingerprint_pct_no_clones']:5.1f} | {r['median_dep_age_days']:4d} / {r['median_dep_age_days_no_clones']:4d} | {r['fresh_pct']:5.1f} / {r['fresh_pct_no_clones']:5.1f}")
for lab, L in (('fingerprint 2026', F26), ('other 2026', R26), ('2021-2022', B)):
    print(f"{lab}: n={len(L)} median dep age {np.median([p['med_age'] for p in L]):.0f} d, newest dep age {np.median([p['newest_age'] for p in L]):.0f} d")
