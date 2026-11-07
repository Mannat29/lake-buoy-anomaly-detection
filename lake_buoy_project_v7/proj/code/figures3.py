"""Final poster figures, drawn at placement size (no scaling): half width 7.8 in, full width 15.8 in; all text >= 18 pt."""
import pickle, json, numpy as np, pandas as pd, matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt, matplotlib.dates as mdates
from lib import *
plt.rcParams.update({'font.family': 'Liberation Sans', 'font.size': 18, 'axes.titlesize': 19, 'axes.titleweight': 'bold', 'axes.labelsize': 18, 'xtick.labelsize': 18,
                     'ytick.labelsize': 18, 'axes.spines.top': False, 'axes.spines.right': False, 'legend.fontsize': 18})
NAVY, TEAL, AMB, RED, GREY, GREEN = '#283747', '#1B8A9A', '#E89B2D', '#C0392B', '#8A94A6', '#4C9F70'
R = '../results/'; OUT = '../figures/p_'; H, F = 7.8, 15.8
D = pickle.load(open(R + 'D_flags.pkl', 'rb')); SP = pd.read_csv(R + 'spark/temp_flagged_share_by_year_spark.csv')
def save(fig, n): fig.savefig(OUT + n, dpi=200, facecolor='white'); plt.close(fig)
# 1 temperature flagged share per year (operators: share of READINGS THEY EVALUATED; ours: share of readings)
fig, ax = plt.subplots(figsize=(H, 3.7)); yrs = SP.year
ax.plot(yrs, 100 * SP.op_flag / SP.op_eval, '-o', color=AMB, lw=4, ms=9, label='Operators: suspect or fail')
ax.plot(yrs, 100 * SP.ours_any / SP.n, '-s', color=TEAL, lw=4, ms=9, label='Our tests')
ax.set_ylim(0, 112); ax.set_xticks(range(2016, 2027, 2)); ax.set_ylabel('Flagged (%)'); ax.grid(alpha=.25)
ax.legend(loc='center left', bbox_to_anchor=(0.0, 0.62), frameon=False); ax.set_title('Temperature: share flagged per year', loc='left')
ax.text(2025, 6, 'no 2025\ndata', fontsize=18, color=GREY, ha='center'); fig.tight_layout(); save(fig, 'tempflags.png')
# 2 what operator flags are made of (share of flagged readings caused by one rule only)
C = pd.read_csv(R + 'spark/operator_flag_composition_spark.csv').set_index('sensor'); order = ['temp', 'do', 'turb', 'phyco', 'chl']
lab = {'temp': 'Temperature', 'do': 'Oxygen', 'turb': 'Turbidity', 'phyco': 'Phycocyanin', 'chl': 'Chlorophyll'}
parts = [('only_flat', 'Flat-line only', AMB), ('only_gross', 'Range only', RED), ('only_roc', 'Rate-of-change only', TEAL)]
fig, ax = plt.subplots(figsize=(H, 3.7)); left = np.zeros(len(order))
for col, name, c in parts:
    v = np.array([100 * C.loc[s, col] / C.loc[s, 'flagged'] for s in order]); ax.barh(range(len(order)), v, left=left, color=c, label=name, height=.62)
    for i, (a, b) in enumerate(zip(left, v)):
        if b >= 12: ax.text(a + b / 2, i, f'{b:.0f}%', ha='center', va='center', color='white', fontsize=18, fontweight='bold')
    left += v
ax.barh(range(len(order)), 100 - left, left=left, color='#C9D1DB', height=.62, label='Mixed / other')
ax.set_yticks(range(len(order))); ax.set_yticklabels([lab[s] for s in order]); ax.invert_yaxis(); ax.set_xlim(0, 100); ax.set_xticks([0, 25, 50, 75, 100]); ax.set_xlabel('Share of operator flags (%)')
ax.legend(loc='upper center', bbox_to_anchor=(0.42, -0.30), ncol=2, frameon=False, fontsize=18, columnspacing=1, handlelength=1.2)
ax.set_title('What the flags are made of', loc='left'); fig.subplots_adjust(left=.27, right=.95, top=.9, bottom=.42); save(fig, 'comp.png')
# 3 real faults (full width)
fig, axs = plt.subplots(1, 2, figsize=(F, 3.1), gridspec_kw={'wspace': .28})
d = D['WE2']; m = (d.time >= '2015-07-20') & (d.time <= '2015-11-10'); ax = axs[0]; xs = d[m]; brk = xs.time.diff() > pd.Timedelta('3h')
for _, seg in xs.groupby(brk.cumsum()): ax.plot(seg.time, seg.temp, color=TEAL, lw=3)
dd = d[m & d.f_dead]; ax.axvspan(dd.time.min(), dd.time.max(), color=RED, alpha=.18)
ax.text(dd.time.min() - pd.Timedelta('2D'), 13, 'Dead probe:\n31 days,\nall sensors 0', fontsize=18, color=RED, fontweight='bold', va='center', ha='right')
ax.set_ylim(-1.5, 29); ax.set_ylabel('Water temp (°C)'); ax.xaxis.set_major_formatter(mdates.DateFormatter('%b')); ax.xaxis.set_major_locator(mdates.MonthLocator()); ax.set_title('(a) WE2, 2015: temperature', loc='left')
d = D['WE8']; m = (d.time >= '2015-08-28') & (d.time <= '2015-11-08'); ax = axs[1]; s = d[m]
ax.plot(s.time, s.phyco, color=NAVY, lw=3); f = s[s.f_stuck_phyco]; ax.plot(f.time, f.phyco, color=RED, lw=6, label='frozen at 2.31 RFU')
ax.set_ylabel('Phycocyanin (RFU)'); ax.xaxis.set_major_formatter(mdates.DateFormatter('%b')); ax.xaxis.set_major_locator(mdates.MonthLocator()); ax.legend(loc='upper right', frameon=False)
ax.set_title('(b) WE8, 2015: phycocyanin', loc='left'); fig.subplots_adjust(left=.07, right=.99, top=.88, bottom=.14); save(fig, 'faults.png')
# 4 drift (half width)
dr = pd.read_csv(R + 'synthetic_drift.csv'); amp = [1, 2, 3, 5]
fig, ax = plt.subplots(figsize=(H, 3.3)); x = np.arange(4); w = .38; a = 100 * dr.caught_neigh / dr.events; b_ = 100 * dr.caught_single / dr.events
ax.bar(x - w / 2, a, w, color=TEAL, label='Neighbour-buoy check'); ax.bar(x + w / 2, b_, w, color=GREY, label='Single-sensor tests')
for i in range(4): ax.text(i - w / 2, a[i] + 2, f'{a[i]:.0f}%', ha='center', fontsize=18, fontweight='bold', color=NAVY); ax.text(i + w / 2, b_[i] + 2, f'{b_[i]:.0f}%', ha='center', fontsize=18, color=NAVY)
ax.set_xticks(x); ax.set_xticklabels([f'+{v}' for v in amp]); ax.set_xlabel('Drift added over 7 days (°C)'); ax.set_ylabel('Caught (%)'); ax.set_ylim(0, 150); ax.set_yticks([0, 50, 100])
ax.legend(loc='upper left', frameon=False); ax.set_title('Synthetic drift, 36 events each', loc='left'); fig.tight_layout(); save(fig, 'drift.png')
# 5 Spark vs Pandas timing (log scale, seconds)
B = pd.read_csv(R + 'spark/benchmark_spark_vs_pandas.csv')
g = lambda j, e, v=None: float(B[(B.job.str.startswith(j)) & (B.engine == e) & (B.variant.str.contains(v) if v else True)].median_s.min())
jobs = [('Read + tidy', g('ingest + tidy', 'pandas', 'load_all'), g('ingest + tidy', 'spark', 'CSV')), ('Aggregate', g('aggregate', 'pandas'), g('aggregate', 'spark')),
        ('Hampel spike', g('Hampel', 'pandas'), g('Hampel', 'spark')), ('Neighbour', g('neighbour', 'pandas'), g('neighbour', 'spark')),
        ('Synthetic x10', g('SYNTHETIC x10', 'pandas'), g('SYNTHETIC x10', 'spark')), ('Synthetic x50', g('SYNTHETIC x50', 'pandas'), g('SYNTHETIC x50', 'spark'))]
json.dump(jobs, open(R + 'spark/timing_summary_best_spark.json', 'w'))
fig, ax = plt.subplots(figsize=(H, 3.9)); y = np.arange(len(jobs)); h = .4
ax.barh(y - h / 2, [j[1] for j in jobs], h, color=TEAL, label='Pandas'); ax.barh(y + h / 2, [j[2] for j in jobs], h, color=AMB, label='Spark (best variant)')
ax.set_xscale('log'); ax.set_xlim(0.1, 40000); ax.set_yticks(y); ax.set_yticklabels([j[0] for j in jobs]); ax.invert_yaxis(); ax.set_xlabel('Seconds (log scale, lower is faster)')
ax.set_xticks([0.1, 1, 10, 100, 1000]); ax.set_xticklabels(['0.1', '1', '10', '100', '1000'])
fmt = lambda v: f'{v:.2g}' if v < 10 else f'{v:.0f}'
for i, j in enumerate(jobs): ax.text(j[2] * 1.25, i + h / 2, f'{fmt(j[1])} vs {fmt(j[2])} s', va='center', fontsize=18, color=NAVY)
ax.legend(loc='lower left', bbox_to_anchor=(-0.02, 1.0), ncol=2, frameon=False, columnspacing=1.2); fig.tight_layout(); save(fig, 'timing.png')
print([ (j[0], round(j[1],3), round(j[2],2)) for j in jobs])
# 6 bloom-or-fault donuts (half width)
import textwrap
bl = pd.DataFrame(json.load(open(R + 'part3.json'))['bloom_table'])
v1 = round(100 * bl.readings[0] / bl.readings.sum()); v2 = round(bl.op_flag_pct[2]); v3 = round(bl.op_flag_pct[0])
fig = plt.figure(figsize=(H, 2.95)); fig.patch.set_facecolor('white')
for k, (val, col, cap) in enumerate([(v1, TEAL, 'of high-chlorophyll readings sit in 67 sustained, bloom-like events'), (v2, AMB, f'of short isolated spikes were flagged by operators (bloom-like readings: {v3}%)')]):
    ax = fig.add_axes([k * .5 + .25 - .5 * 1.5 / H, 1.32 / 2.95, 1.5 / H, 1.5 / 2.95]); ax.pie([val, 100 - val], colors=[col, '#E3E8ED'], startangle=90, counterclock=False, wedgeprops=dict(width=.3, edgecolor='white'))
    ax.text(0, 0, f'{val}%', ha='center', va='center', fontsize=26, fontweight='bold', color=NAVY)
    fig.text(k * .5 + .25, 1.18 / 2.95, '\n'.join(textwrap.wrap(cap, 29)), ha='center', va='top', fontsize=18, color=NAVY)
save(fig, 'bloom.png')
