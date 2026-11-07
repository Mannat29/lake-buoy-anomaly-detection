"""Figures re-drawn at final size for the 36x48 in conference template (width 15.8 in)."""
import pickle, json, numpy as np, pandas as pd, matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt, matplotlib.dates as mdates
from lib import *
plt.rcParams.update({'font.family': 'Liberation Sans', 'font.size': 19, 'axes.titlesize': 21, 'axes.titleweight': 'bold', 'axes.labelsize': 19,
                     'xtick.labelsize': 18, 'ytick.labelsize': 18, 'axes.spines.top': False, 'axes.spines.right': False, 'legend.fontsize': 18})
NAVY, TEAL, AMB, RED, GREY, GREEN = '#283747', '#1B8A9A', '#E89B2D', '#C0392B', '#8A94A6', '#4C9F70'
D = pickle.load(open('../results/D_flags.pkl', 'rb')); P1 = json.load(open('../results/part1.json'))
Y = pd.read_csv('../results/our_flags_by_year.csv'); OUT = '../figures/t_'
W = 15.8
def save(fig, n): fig.savefig(OUT + n, dpi=200, facecolor='white'); plt.close(fig)
# map
fig, ax = plt.subplots(figsize=(7.9, 3.9)); inv = {r['buoy']: r for r in P1['inventory']}
for b, r in inv.items():
    ax.scatter(r['lon'], r['lat'], s=520, color=TEAL, edgecolor=NAVY, linewidth=2.5, zorder=3)
    dx, dy = {'WE2': (0.012, -0.012), 'WE4': (0.012, 0.004), 'WE8': (-0.062, 0.006), 'WE13': (0.012, -0.004)}[b]
    ax.text(r['lon'] + dx, r['lat'] + dy, b, fontsize=19, fontweight='bold', color=NAVY, zorder=4)
ax.set_aspect(1 / np.cos(np.radians(41.8))); ax.set_xlim(-83.46, -83.02); ax.set_ylim(41.70, 41.87)
ax.set_xlabel('Longitude (°)'); ax.set_ylabel('Latitude (°N)'); ax.grid(alpha=.25)
x0, y0 = -83.44, 41.715; ax.plot([x0, x0 + 10 / 83.0], [y0, y0], color=NAVY, lw=5); ax.text(x0, y0 + 0.008, '10 km', fontsize=16, color=NAVY)
ax.set_title('Buoy positions (about 20 km apart)', loc='left', fontsize=19); fig.tight_layout(); save(fig, 'map.png')
# temp flags by year
T = Y[Y.sensor == 'temp'].groupby('year')[['n', 'ours_any', 'op_eval', 'op_flag']].sum()
fig, ax = plt.subplots(figsize=(W, 3.3))
ax.plot(T.index, 100 * T.op_flag / T.op_eval, '-o', color=AMB, lw=5, ms=12, label='Operators: suspect or fail')
ax.plot(T.index, 100 * T.ours_any / T.n, '-s', color=TEAL, lw=5, ms=12, label='Our tests: candidate faults')
ax.set_ylabel('Readings flagged (%)'); ax.set_ylim(0, 108); ax.set_xticks(range(2015, 2027)); ax.tick_params(axis='x', labelsize=16); ax.grid(alpha=.25)
ax.legend(loc='center left', bbox_to_anchor=(.01, .55), frameon=False, fontsize=18)
ax.annotate('no 2025 data', xy=(2025, 3), xytext=(2024.3, 38), fontsize=17, color=GREY, arrowprops=dict(arrowstyle='->', color=GREY))
ax.set_title('Temperature: share of readings flagged, per year', loc='left'); fig.tight_layout(); save(fig, 'tempflags.png')
# faults (two panels side by side)
fig, axs = plt.subplots(1, 2, figsize=(W, 3.4), gridspec_kw={'wspace': .28})
d = D['WE2']; m = (d.time >= '2015-07-20') & (d.time <= '2015-11-10'); ax = axs[0]; xs = d[m]; brk = xs.time.diff() > pd.Timedelta('3h')
for _, seg in xs.groupby(brk.cumsum()): ax.plot(seg.time, seg.temp, color=TEAL, lw=3)
dd = d[m & d.f_dead]; ax.axvspan(dd.time.min(), dd.time.max(), color=RED, alpha=.18)
ax.text(dd.time.min() - pd.Timedelta('2D'), 13, 'Dead probe:\n31 days,\nall sensors 0', fontsize=17, color=RED, fontweight='bold', va='center', ha='right')
ax.set_ylim(-1.5, 29); ax.set_ylabel('Water temp (°C)'); ax.xaxis.set_major_formatter(mdates.DateFormatter('%b')); ax.xaxis.set_major_locator(mdates.MonthLocator()); ax.set_title('(a) WE2, 2015: temperature', loc='left', fontsize=19)
d = D['WE8']; m = (d.time >= '2015-08-28') & (d.time <= '2015-11-08'); ax = axs[1]; s = d[m]
ax.plot(s.time, s.phyco, color=NAVY, lw=3); f = s[s.f_stuck_phyco]; ax.plot(f.time, f.phyco, color=RED, lw=6, label='frozen at 2.31 RFU')
ax.set_ylabel('Phycocyanin (RFU)'); ax.xaxis.set_major_formatter(mdates.DateFormatter('%b')); ax.xaxis.set_major_locator(mdates.MonthLocator()); ax.legend(loc='upper right', frameon=False, fontsize=17)
ax.set_title('(b) WE8, 2015: phycocyanin', loc='left', fontsize=19); fig.subplots_adjust(left=.07, right=.99, top=.88, bottom=.14); save(fig, 'faults.png')
# drift
dr = pd.read_csv('../results/synthetic_drift.csv'); amp = [1, 2, 3, 5]
fig, ax = plt.subplots(figsize=(W, 3.2)); x = np.arange(4); w = .34
ax.bar(x - w / 2, 100 * dr.caught_neigh / dr.events, w, color=TEAL, label='Neighbour-buoy check'); ax.bar(x + w / 2, 100 * dr.caught_single / dr.events, w, color=GREY, label='Single-sensor tests')
for i, (a, b_) in enumerate(zip(100 * dr.caught_neigh / dr.events, 100 * dr.caught_single / dr.events)):
    ax.text(i - w / 2, a + 2, f'{a:.0f}%', ha='center', fontsize=18, fontweight='bold', color=NAVY); ax.text(i + w / 2, b_ + 2, f'{b_:.0f}%', ha='center', fontsize=18, color=NAVY)
ax.set_xticks(x); ax.set_xticklabels([f'+{a} °C drift over 7 days' for a in amp], fontsize=17); ax.set_ylabel('Events caught (%)'); ax.set_ylim(0, 115)
ax.legend(loc='upper left', frameon=False); ax.set_title('Synthetic slow drift, 36 events per size', loc='left'); fig.tight_layout(); save(fig, 'drift.png')
print('ok')
