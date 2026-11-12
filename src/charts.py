#!/usr/bin/env python3
"""Draw the figures in charts/ from the CSV files in results/."""
import csv, collections
import matplotlib; matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.patches import FancyBboxPatch

SURFACE, INK, INK2, GRID = '#fcfcfb', '#0b0b0b', '#52514e', '#e4e3df'
BLUE, ORANGE = '#2a78d6', '#eb6834'
plt.rcParams.update({'font.family': 'DejaVu Sans', 'font.size': 11, 'axes.edgecolor': GRID, 'axes.labelcolor': INK2,
                     'xtick.color': INK2, 'ytick.color': INK2, 'text.color': INK, 'figure.facecolor': SURFACE,
                     'axes.facecolor': SURFACE, 'savefig.facecolor': SURFACE, 'axes.spines.top': False, 'axes.spines.right': False})
def rows(name): return list(csv.DictReader(open(f'results/{name}.csv')))
def style(ax):
    ax.grid(axis='y', color=GRID, linewidth=1); ax.set_axisbelow(True)
    ax.spines['left'].set_visible(False); ax.tick_params(length=0)
def title(fig, t, sub):
    fig.text(0.06, 0.95, t, fontsize=14, fontweight='bold', ha='left', va='top')
    fig.text(0.06, 0.885, sub, fontsize=10.5, color=INK2, ha='left', va='top')
def bar(ax, x, h, w, color):
    if h <= 0: return
    r = min(0.06 * w * 4, h)  # rounded data-end, square baseline
    ax.add_patch(FancyBboxPatch((x - w / 2, 0), w, h, boxstyle=f"round,pad=0,rounding_size={min(w/2.5, h/2)}", linewidth=0, facecolor=color, mutation_aspect=(h and 1) ))
    ax.add_patch(plt.Rectangle((x - w / 2, 0), w, h / 2, linewidth=0, facecolor=color))

# 1. fingerprint share by half-year
H = rows('half_year')
fig, ax = plt.subplots(figsize=(9, 5)); fig.subplots_adjust(top=0.78, left=0.08, right=0.97, bottom=0.12)
xs = range(len(H)); ys = [float(r['fingerprint_pct']) for r in H]
ax.bar(xs, ys, width=0.55, color=BLUE, linewidth=0)
ax.errorbar(xs, ys, yerr=[[y - float(r['ci_lo']) for y, r in zip(ys, H)], [float(r['ci_hi']) - y for y, r in zip(ys, H)]], fmt='none', ecolor=INK2, elinewidth=1, capsize=0)
ax.set_xticks(list(xs)); ax.set_xticklabels([r['period'].replace('H', '\nH') for r in H], fontsize=9)
ax.set_ylabel('% of new packages'); ax.set_ylim(0, 16); style(ax)
for i in (len(H) - 2, len(H) - 1, len(H) - 3):
    ax.text(i, float(H[i]['ci_hi']) + 0.35, f"{ys[i]:.1f}%", ha='center', fontsize=10, color=INK)
ax.text(4.5, 3.4, 'baseline 2019-2024: 1-3%', ha='center', fontsize=10, color=INK2)
title(fig, 'New npm packages carrying the "written from memory" fingerprint',
      'Share of first releases whose pinned versions are mostly round (x.0.0) and already superseded.\n250,000-package random sample; lines show 95% confidence intervals.')
fig.savefig('charts/01_fingerprint_share.png', dpi=200); plt.close(fig)

# 2. median dependency age at birth, by quarter
Q = rows('quarterly')
fig, ax = plt.subplots(figsize=(9, 5)); fig.subplots_adjust(top=0.78, left=0.09, right=0.95, bottom=0.12)
ys = [float(r['median_dep_age_days_no_clones']) for r in Q]; xs = list(range(len(Q)))
if int(Q[-1]['n']) < 1000: xs, ys, Q = xs[:-1], ys[:-1], Q[:-1]      # drop the incomplete last quarter
ax.plot(xs, ys, color=BLUE, linewidth=2, solid_capstyle='round', solid_joinstyle='round')
ax.fill_between(xs, ys, color=BLUE, alpha=0.10, linewidth=0)
ax.scatter([xs[-1]], [ys[-1]], s=60, color=BLUE, edgecolor=SURFACE, linewidth=2, zorder=3)
ipk = max(range(len(ys)), key=lambda i: ys[i])
ax.scatter([xs[ipk]], [ys[ipk]], s=60, color=BLUE, edgecolor=SURFACE, linewidth=2, zorder=3)
ax.text(xs[ipk], ys[ipk] + 16, f"{ys[ipk]:.0f} days\n({Q[ipk]['period']})", ha='center', fontsize=10)
ax.text(xs[-1] + 0.2, ys[-1] - 28, f"{ys[-1]:.0f}", ha='left', fontsize=10)
ax.text(8, ys[8] + 48, f"about {sum(ys[8:20])/12:.0f} days in 2021-2023", ha='left', fontsize=10, color=INK2)
ax.set_xticks([i for i, r in enumerate(Q) if r['period'].endswith('Q1')]); ax.set_xticklabels([r['period'][:4] for r in Q if r['period'].endswith('Q1')])
ax.set_ylabel('days'); ax.set_ylim(0, 500); style(ax)
title(fig, 'How old is a typical dependency on the day a package is born?',
      'Median age of the pinned dependency versions in the first release, by quarter of first publish.\nMass-cloned spam manifests removed.')
fig.savefig('charts/02_dependency_age.png', dpi=200); plt.close(fig)

# 3. per-library small multiples
P = collections.defaultdict(dict)
for r in rows('per_library'):
    if r['pct'] != '' and int(r['pins']) >= 40: P[r['library']][int(r['year'])] = float(r['pct'])
libs = ['@types/node', 'react', 'tsup', 'vitest', 'rollup', 'eslint', 'typescript', 'axios']
fig, axes = plt.subplots(2, 4, figsize=(11, 5.6), sharey=True); fig.subplots_adjust(top=0.76, left=0.07, right=0.98, bottom=0.08, hspace=0.45, wspace=0.12)
for ax, l in zip(axes.ravel(), libs):
    ys_ = sorted(P[l].items()); x = [a for a, _ in ys_]; y = [b for _, b in ys_]
    ax.plot(x, y, color=BLUE, linewidth=2, solid_capstyle='round'); ax.scatter([x[-1]], [y[-1]], s=50, color=BLUE, edgecolor=SURFACE, linewidth=2, zorder=3)
    ax.text(x[-1], y[-1] + 2.2, f"{y[-1]:.0f}%", ha='right', fontsize=10)
    ax.set_title(l, fontsize=11, loc='left', color=INK); ax.set_xlim(2018.6, 2026.4); ax.set_ylim(0, 30)
    ax.set_xticks([2020, 2023, 2026]); style(ax)
axes[0][0].set_ylabel('% of pins'); axes[1][0].set_ylabel('% of pins')
title(fig, 'The same break shows up library by library', 'Share of pins to each library that name a round x.0.0 version which was already superseded, by year the\ndepending package was born. Two libraries where the habit never appears are shown for contrast.')
fig.savefig('charts/03_per_library.png', dpi=200); plt.close(fig)

# 4. the default stack: 2021-2022 vs fingerprint packages of 2026
S = {r['library']: r for r in rows('stack')}
pairs = [('vitest', 'test runner'), ('jest', 'test runner'), ('mocha', 'test runner'), ('tsup', 'bundler'), ('rollup', 'bundler'), ('webpack', 'bundler')]
fig, ax = plt.subplots(figsize=(9, 5)); fig.subplots_adjust(top=0.76, left=0.14, right=0.95, bottom=0.1)
yy = [0, 1, 2, 3.6, 4.6, 5.6]; hgt = 0.34
for y, (l, cat) in zip(yy, pairs):
    a, b = float(S[l]['all_2021_2022_pct']), float(S[l]['fingerprint_2026_pct'])
    ax.barh(y - hgt / 2 - 0.02, a, height=hgt, color=BLUE, linewidth=0); ax.barh(y + hgt / 2 + 0.02, b, height=hgt, color=ORANGE, linewidth=0)
    ax.text(a + 0.8, y - hgt / 2 - 0.02, f"{a:.0f}%", va='center', fontsize=10); ax.text(b + 0.8, y + hgt / 2 + 0.02, f"{b:.0f}%", va='center', fontsize=10)
ax.set_yticks(yy); ax.set_yticklabels([l for l, _ in pairs]); ax.invert_yaxis(); ax.set_xlim(0, 52)
ax.text(51, -0.55, 'test runners', ha='right', fontsize=10, color=INK2); ax.text(51, 3.05, 'bundlers', ha='right', fontsize=10, color=INK2)
ax.grid(axis='x', color=GRID, linewidth=1); ax.set_axisbelow(True); ax.spines['bottom'].set_visible(False); ax.tick_params(length=0); ax.set_xlabel('% of packages that depend on it')
ax.legend(handles=[plt.Rectangle((0, 0), 1, 1, color=BLUE), plt.Rectangle((0, 0), 1, 1, color=ORANGE)], labels=['all new packages, 2021-2022', 'fingerprint packages, 2026'], frameon=False, loc='lower right', fontsize=10)
title(fig, 'Code written from memory converges on one stack', 'Share of new packages that depend on each tool: all packages born in 2021-2022\nversus packages born in 2026 that carry the fingerprint.')
fig.savefig('charts/04_default_stack.png', dpi=200); plt.close(fig)
print('charts written')
