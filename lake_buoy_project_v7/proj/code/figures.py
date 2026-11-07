import pickle, json, numpy as np, pandas as pd, matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt, matplotlib.dates as mdates
from lib import *
plt.rcParams.update({'font.family': 'Liberation Sans', 'font.size': 17, 'axes.titlesize': 19, 'axes.titleweight': 'bold', 'axes.labelsize': 17,
                     'xtick.labelsize': 16, 'ytick.labelsize': 16, 'axes.spines.top': False, 'axes.spines.right': False, 'legend.fontsize': 16})
NAVY, TEAL, LT, AMB, RED, GREY, GREEN = '#0B2A4A', '#1B8A9A', '#BFE3E8', '#F2A541', '#D1495B', '#8A94A6', '#4C9F70'
D = pickle.load(open('../results/D_flags.pkl', 'rb')); P1 = json.load(open('../results/part1.json')); P3 = json.load(open('../results/part3.json'))
Y = pd.read_csv('../results/our_flags_by_year.csv'); OUT = '../figures/'
def save(fig, name): fig.savefig(OUT + name, dpi=200, facecolor='white'); plt.close(fig)
# ---- F1 map
fig, ax = plt.subplots(figsize=(9.6, 4.0)); inv = {r['buoy']: r for r in P1['inventory']}
for b, r in inv.items():
    ax.scatter(r['lon'], r['lat'], s=420, color=TEAL, edgecolor=NAVY, linewidth=2, zorder=3)
    dx, dy = {'WE2': (-0.012, -0.020), 'WE4': (0.008, 0.003), 'WE8': (-0.058, 0.004), 'WE13': (0.008, -0.003)}[b]
    ax.text(r['lon'] + dx, r['lat'] + dy, b, fontsize=20, fontweight='bold', color=NAVY, zorder=4)
ax.set_aspect(1 / np.cos(np.radians(41.8))); ax.set_xlim(-83.48, -83.00); ax.set_ylim(41.70, 41.87)
ax.set_xlabel('Longitude (°)'); ax.set_ylabel('Latitude (°N)'); ax.grid(alpha=.25)
x0, y0 = -83.46, 41.715; ax.plot([x0, x0 + 10 / 83.0], [y0, y0], color=NAVY, lw=5); ax.text(x0, y0 + 0.006, '10 km', fontsize=16, color=NAVY)
ax.set_title('Four buoys within about 20 km (western Lake Erie)', loc='left'); fig.tight_layout(); save(fig, 'f1_map.png')
# ---- F2 coverage timeline
fig, ax = plt.subplots(figsize=(9.6, 4.2)); lanes = ['Data', 'Flags: algae, O₂, turbidity', 'Flags: temperature']; cols = [TEAL, AMB, GREEN]
ypos = 0; yt = []; yl = []
for b, d in D.items():
    d = d.copy(); d['m'] = d.time.dt.to_period('M').dt.to_timestamp()
    g = d.groupby('m').agg(n=('chl', 'size'), e4=('chl_agg', lambda s: s.isin([1, 3, 4]).mean()), et=('temp_agg', lambda s: s.isin([1, 3, 4]).mean()))
    for k, (lane, c) in enumerate(zip(lanes, cols)):
        y = ypos + (2 - k) * 0.28
        m = g.index[(g.n > 0)] if k == 0 else (g.index[g.e4 >= .5] if k == 1 else g.index[g.et >= .5])
        ax.broken_barh([(mdates.date2num(t), 30) for t in m], (y, 0.22), facecolors=c)
    yt.append(ypos + 0.4); yl.append(b); ypos += 1.15
ax.set_yticks(yt); ax.set_yticklabels(yl, fontweight='bold'); ax.invert_yaxis(); ax.xaxis_date(); ax.set_xlim(mdates.date2num(pd.Timestamp('2015-06-01')), mdates.date2num(pd.Timestamp('2026-12-01')))
ax.xaxis.set_major_locator(mdates.YearLocator(2)); ax.xaxis.set_major_formatter(mdates.DateFormatter('%Y'))
from matplotlib.patches import Patch
ax.legend(handles=[Patch(color=c, label=l) for l, c in zip(lanes, cols)], loc='upper center', bbox_to_anchor=(.5, -.12), ncol=1, frameon=False, fontsize=15)
ax.set_title('When data and operator flags exist', loc='left'); fig.tight_layout(); save(fig, 'f2_coverage.png')
# ---- F3 temperature flags by year
T = Y[Y.sensor == 'temp'].groupby('year')[['n', 'ours_any', 'op_eval', 'op_flag']].sum()
fig, ax = plt.subplots(figsize=(9.6, 3.9))
ax.plot(T.index, 100 * T.op_flag / T.op_eval, '-o', color=AMB, lw=4, ms=10, label='Operators (suspect/fail)')
ax.plot(T.index, 100 * T.ours_any / T.n, '-s', color=TEAL, lw=4, ms=10, label='Our tests (candidates)')
ax.set_ylabel('Readings flagged (%)'); ax.set_ylim(0, 105); ax.set_xticks([2015, 2018, 2021, 2024]); ax.grid(alpha=.25); ax.legend(loc='center left', bbox_to_anchor=(.02, .62), frameon=False, fontsize=14)
ax.annotate('no 2025 data', xy=(2025, 3), xytext=(2024.1, 40), fontsize=15, color=GREY, arrowprops=dict(arrowstyle='->', color=GREY))
ax.set_title('Temperature: share of readings flagged per year', loc='left'); fig.tight_layout(); save(fig, 'f3_temp_flags.png')
# ---- F4 flag composition
fc = P1['flag_composition']; order = ['temp', 'phyco', 'chl', 'turb', 'do']; lab = {'temp': 'Temperature', 'phyco': 'Phycocyanin', 'chl': 'Chlorophyll', 'turb': 'Turbidity', 'do': 'Oxygen'}
fig, ax = plt.subplots(figsize=(9.6, 3.9)); left = np.zeros(len(order))
parts = [('only_flat', 'Flat-line rule alone', AMB), ('only_gross', 'Range rule alone', RED), ('only_roc', 'Rate-of-change alone', TEAL), ('only_spike', 'Spike alone', NAVY)]
for k, nm, c in parts:
    v = np.array([100 * fc[s][k] / fc[s]['flagged'] for s in order]); ax.barh(range(len(order)), v, left=left, color=c, label=nm); left += v
mix = 100 - left; ax.barh(range(len(order)), mix, left=left, color='#D9DEE7', label='More than one rule')
ax.set_yticks(range(len(order))); ax.set_yticklabels([lab[s] for s in order]); ax.invert_yaxis(); ax.set_xlim(0, 100); ax.set_xlabel('Share of operator-flagged readings (%)')
ax.legend(loc='upper center', bbox_to_anchor=(.38, -.28), ncol=2, frameon=False, fontsize=14)
ax.set_title('Most flags come from one single-sensor rule', loc='left'); fig.subplots_adjust(left=.2, right=.98, top=.9, bottom=.42); save(fig, 'f4_composition.png')
# ---- F5 real faults
fig, axs = plt.subplots(2, 1, figsize=(9.6, 5.4), gridspec_kw={'hspace': .6})
d = D['WE2']; m = (d.time >= '2015-07-20') & (d.time <= '2015-11-10'); ax = axs[0]
xs = d[m]; brk = xs.time.diff() > pd.Timedelta('3h')
for _, seg in xs.groupby(brk.cumsum()): ax.plot(seg.time, seg.temp, color=TEAL, lw=2.5)
dd = d[m & d.f_dead]; ax.axvspan(dd.time.min(), dd.time.max(), color=RED, alpha=.18)
ax.text(dd.time.min() - pd.Timedelta('3D'), 14.5, f'Dead probe: {len(dd):,}\nreadings (31 days),\nall sensors = 0', fontsize=16, color=RED, fontweight='bold', va='center', ha='right')
ax.set_ylim(-1.5, 28); ax.set_ylabel('Water temp (°C)'); ax.xaxis.set_major_formatter(mdates.DateFormatter('%d %b')); ax.xaxis.set_major_locator(mdates.MonthLocator()); ax.set_title('(a) WE2, 2015: temperature drops to 0 °C', loc='left')
d = D['WE8']; m = (d.time >= '2015-08-28') & (d.time <= '2015-11-08'); ax = axs[1]; s = d[m]
ax.plot(s.time, s.phyco, color=NAVY, lw=2.5); f = s[s.f_stuck_phyco]; ax.plot(f.time, f.phyco, color=RED, lw=5, label='frozen at 2.31 RFU')
ax.set_ylabel('Phycocyanin (RFU)'); ax.xaxis.set_major_formatter(mdates.DateFormatter('%d %b')); ax.xaxis.set_major_locator(mdates.MonthLocator())
ax.legend(loc='upper right', frameon=False); ax.set_title('(b) WE8, autumn 2015: sensor frozen for 36 days', loc='left')
fig.subplots_adjust(left=.13, right=.98, top=.93, bottom=.08); save(fig, 'f5_faults.png')
# ---- F6 drift
dr = pd.read_csv('../results/synthetic_drift.csv'); amp = [1, 2, 3, 5]
fig, ax = plt.subplots(figsize=(9.6, 3.8)); x = np.arange(4); w = .36
ax.bar(x - w / 2, 100 * dr.caught_neigh / dr.events, w, color=TEAL, label='Neighbour-buoy check'); ax.bar(x + w / 2, 100 * dr.caught_single / dr.events, w, color=GREY, label='Single-sensor tests')
for i, (a, b_) in enumerate(zip(100 * dr.caught_neigh / dr.events, 100 * dr.caught_single / dr.events)):
    ax.text(i - w / 2, a + 2, f'{a:.0f}%', ha='center', fontsize=16, fontweight='bold', color=NAVY); ax.text(i + w / 2, b_ + 2, f'{b_:.0f}%', ha='center', fontsize=16, color=NAVY)
ax.set_xticks(x); ax.set_xticklabels([f'+{a} °C' for a in amp]); ax.set_xlabel('Synthetic drift over 7 days (36 events each)'); ax.set_ylabel('Events caught (%)'); ax.set_ylim(0, 112)
ax.legend(loc='upper left', frameon=False); ax.set_title('Slow drift: neighbours see what one sensor cannot', loc='left'); fig.tight_layout(); save(fig, 'f6_drift.png')
# ---- F7 bloom vs fault
EV = pd.read_csv('../results/chl_events.csv'); fig, axs = plt.subplots(2, 1, figsize=(9.6, 5.4), gridspec_kw={'hspace': .55})
# pick a long bloom-like event seen at several buoys: use the period with most simultaneous high-chl readings
H = pd.DataFrame({b: D[b].assign(t=D[b].time.dt.round('15min')).drop_duplicates('t').set_index('t').chl for b in ['WE2', 'WE4', 'WE8']})
dayhi = (H > H.quantile(.97)).resample('D').sum().sum(axis=1); peak = dayhi.rolling(7).sum().idxmax(); a, b2 = peak - pd.Timedelta('10D'), peak + pd.Timedelta('3D')
ax = axs[0]
for b, c in zip(['WE2', 'WE4', 'WE8'], [TEAL, AMB, NAVY]):
    s = H[b][a:b2].dropna()
    if len(s) > 100: ax.plot(s.index, s.values, color=c, lw=2.2, label=b)
ax.set_ylabel('Chlorophyll (RFU)'); ax.legend(ncol=3, loc='upper left', frameon=False); ax.xaxis.set_major_formatter(mdates.DateFormatter('%d %b %Y')); ax.xaxis.set_major_locator(mdates.DayLocator(interval=5))
ax.set_title('(a) Bloom-like: sustained rise at more than one buoy', loc='left')
d = D['WE2']; c = d[(d.f_spike_chl) & ~d.f_dead & (d.chl > 6) & (d.year.isin([2016, 2017, 2018]))]; i0 = c.chl.idxmax(); t0 = d.time[i0]
s = d[(d.time > t0 - pd.Timedelta('2D')) & (d.time < t0 + pd.Timedelta('2D'))]; ax = axs[1]
ax.plot(s.time, s.chl, color=NAVY, lw=2.2, label='Chlorophyll'); ax.plot(s.time, s.phyco, color=GREEN, lw=2.2, label='Phycocyanin'); ax.scatter([t0], [d.chl[i0]], s=200, color=RED, zorder=5, label='flagged spike')
ax.set_ylabel('RFU'); ax.set_ylim(0, 22); ax.legend(ncol=3, loc='upper right', frameon=False, fontsize=14); ax.xaxis.set_major_formatter(mdates.DateFormatter('%d %b')); ax.xaxis.set_major_locator(mdates.DayLocator(interval=1))
ax.set_title('(b) Short isolated spike: other sensors stay calm', loc='left'); fig.subplots_adjust(left=.13, right=.98, top=.93, bottom=.09); save(fig, 'f7_bloom.png')
print('window', a, b2, 'spike', t0, float(d.chl[i0]))
