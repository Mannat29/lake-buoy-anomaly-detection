"""Part 3: synthetic fault injection (labelled), bloom-vs-fault logic, event tables."""
import pickle, json, numpy as np, pandas as pd
from lib import *
from ours import *
rng = np.random.default_rng(42)
D = pickle.load(open('../results/D_flags.pkl', 'rb')); NB = pickle.load(open('../results/NB.pkl', 'rb')); meta = json.load(open('../results/detector_meta.json'))
OUT = {}
# ---------- episodes worth naming (stuck + dead probe)
ep = []
for b, d in D.items():
    for s in SENSORS:
        f = d[f'f_stuck_{s}'].to_numpy(); idx = np.flatnonzero(np.diff(np.r_[0, f.astype(int), 0]))
        for a, z in zip(idx[::2], idx[1::2]):
            ep.append(dict(buoy=b, sensor=s, start=str(d.time.iloc[a]), end=str(d.time.iloc[z - 1]), readings=int(z - a),
                           hours=round((d.time.iloc[z - 1] - d.time.iloc[a]).total_seconds() / 3600, 1), value=float(d[s].iloc[a])))
E_ = pd.DataFrame(ep).sort_values('readings', ascending=False); E_.to_csv('../results/stuck_episodes.csv', index=False)
OUT['stuck_events_by_sensor'] = E_.groupby('sensor').size().to_dict(); OUT['stuck_longest'] = E_.head(5).to_dict('records')
f = D['WE2'].f_dead.to_numpy(); idx = np.flatnonzero(np.diff(np.r_[0, f.astype(int), 0])); L = [(a, z) for a, z in zip(idx[::2], idx[1::2])]
a, z = max(L, key=lambda t: t[1] - t[0]); d2 = D['WE2']
OUT['dead_probe_we2'] = dict(start=str(d2.time.iloc[a]), end=str(d2.time.iloc[z - 1]), readings=int(z - a),
                             days=round((d2.time.iloc[z - 1] - d2.time.iloc[a]).total_seconds() / 86400, 1))
# ---------- synthetic fault injection (labelled, on a copy)
def clean_windows(b, s, length, n, avoid_frac=0.0):
    d = D[b]; ok = d[s].notna().to_numpy() & ~d.f_dead.to_numpy() & ~d[f'f_any_{s}'].to_numpy()
    starts = []
    tries = 0
    t = d.time.values
    while len(starts) < n and tries < 20000:
        tries += 1; i = int(rng.integers(30, len(d) - length - 30))
        if (t[i + length] - t[i]) > np.timedelta64(int(length * 20), 'm'): continue   # contiguous only
        if ok[i - 12:i + length + 12].mean() < 0.98: continue
        starts.append(i)
    return starts

def neighbour_flags(b, s_series, d):
    """Recompute temperature neighbour check for buoy b with modified series (reference = real other buoys)."""
    cols = {}
    for bb, dd in D.items():
        if bb == b: continue
        x = dd['temp'].where(~dd.f_dead); tt = dd.time.dt.round('15min'); ser = pd.Series(x.values, index=tt); cols[bb] = ser[~ser.index.duplicated()]
    O = pd.DataFrame(cols).sort_index(); n = O.notna().sum(axis=1); ref = O.median(axis=1).where(n >= 2)
    tt = d.time.dt.round('15min'); mine = pd.Series(s_series, index=tt); mine = mine[~mine.index.duplicated()]
    res = (mine - ref.reindex(mine.index)); roll = res.rolling(24, min_periods=12).median()
    thr = NB[b]['thr']; return (roll.abs() > thr).reindex(tt).fillna(False).to_numpy()

res = []
SPIKE = dict(temp=3.0, chl=5.0); STUCK_LEN = 24
DRIFT = dict(temp=[1.0, 2.0, 3.0, 5.0])
for s in ['temp', 'chl']:
    sig = {b: meta[f'{b}_{s}']['sigma'] for b in ['WE2', 'WE4', 'WE8']}
    # spikes
    n_ev = 100; per = n_ev // 3
    ev = {'spike': [], 'stuck': []}; recs = {'spike': [0, 0], 'stuck': [0, 0, 0]}   # events, caught
    for b in ['WE2', 'WE4', 'WE8']:
        d = D[b]
        for i in clean_windows(b, s, 4, per):
            x = d[s].to_numpy(float).copy(); x[i + 2] += SPIKE[s]
            fl, _, _ = hampel_flags(x, d.time, FLOOR[s], sigma=meta[f'{b}_{s}']['sigma'])
            recs['spike'][0] += 1; recs['spike'][1] += int(fl[i + 2])
        for i in clean_windows(b, s, STUCK_LEN + 2, per):
            x = d[s].to_numpy(float).copy(); x[i + 1:i + 1 + STUCK_LEN] = x[i]
            fl = stuck_flags(x, d.time); recs['stuck'][0] += 1; recs['stuck'][1] += int(fl[i + 1:i + 1 + STUCK_LEN].any()); recs['stuck'][2] += int(fl[i + 1:i + 1 + STUCK_LEN].sum())
    res.append(dict(sensor=s, fault='single spike', events=recs['spike'][0], caught_events=recs['spike'][1], recall=recs['spike'][1] / recs['spike'][0], detector='Hampel (single sensor)'))
    res.append(dict(sensor=s, fault='stuck 6 h', events=recs['stuck'][0], caught_events=recs['stuck'][1], recall=recs['stuck'][1] / recs['stuck'][0], detector='exact-repeat rule'))
# drift: temperature, compare single-sensor tests vs neighbour check
drift_rows = []
for A_ in DRIFT['temp']:
    cnt = dict(ev=0, single=0, neigh=0, neigh72=0, delay=[])
    for b in ['WE2', 'WE4', 'WE8']:
        d = D[b]; L = 672
        for i in clean_windows(b, 'temp', L, 12):
            t = d.time.values; sl = slice(i, i + L)
            frac = ((t[sl] - t[i]) / np.timedelta64(7, 'D')).astype(float)
            x = d['temp'].to_numpy(float).copy(); x[sl] = x[sl] + A_ * frac
            x0 = d['temp'].to_numpy(float)
            fl, _, _ = hampel_flags(x, d.time, FLOOR['temp'], sigma=meta[f'{b}_temp']['sigma']); st = stuck_flags(x, d.time)
            fl0, _, _ = hampel_flags(x0, d.time, FLOOR['temp'], sigma=meta[f'{b}_temp']['sigma']); st0 = stuck_flags(x0, d.time)
            nb = neighbour_flags(b, x, d); nb0 = neighbour_flags(b, x0, d)
            cnt['ev'] += 1; cnt['single'] += int(((fl & ~fl0) | (st & ~st0))[sl].any()); w = (nb & ~nb0)[sl]; cnt['neigh'] += int(w.any())
            if w.any():
                first = int(np.argmax(w)); hrs = (t[i + first] - t[i]) / np.timedelta64(1, 'h'); cnt['delay'].append(float(hrs)); cnt['neigh72'] += int(hrs <= 72)
    drift_rows.append(dict(sensor='temp', fault=f'slow drift to +{A_:g} °C over 7 days', events=cnt['ev'], caught_single=cnt['single'], caught_neigh=cnt['neigh'],
                           caught_neigh_within72h=cnt['neigh72'], median_delay_h=float(np.median(cnt['delay'])) if cnt['delay'] else None))
pd.DataFrame(res).to_csv('../results/synthetic_single.csv', index=False); pd.DataFrame(drift_rows).to_csv('../results/synthetic_drift.csv', index=False)
print(pd.DataFrame(res).round(2).to_string()); print(pd.DataFrame(drift_rows).round(2).to_string())
# neighbour false-alarm rate on real data
fa = {}
for b, d in D.items():
    ok = d['nb_roll_temp'].notna(); fa[b] = dict(rows=int(ok.sum()), flagged=int((d.f_neigh_temp & ok).sum()))
OUT['neighbour_real'] = fa; OUT['neighbour_thr'] = {b: round(NB[b]['thr'], 2) for b in NB}
# ---------- bloom vs fault logic on chlorophyll
rows = []
G = {}
for b, d in D.items():
    c = np.log1p(d.chl.clip(lower=0)); z = (c - c.median()) / (1.4826 * (c - c.median()).abs().median())
    p = np.log1p(d.phyco.clip(lower=0)); zp = (p - p.median()) / (1.4826 * (p - p.median()).abs().median())
    u = np.log1p(d.turb.clip(lower=0)); zu = (u - u.median()) / (1.4826 * (u - u.median()).abs().median())
    G[b] = pd.DataFrame({'t': d.time.dt.round('15min'), 'hi': (z > 3.5) & ~d.f_dead, 'phi': zp > 2.0, 'uhi': zu > 3.5, 'op': d.chl_agg, 'i': d.index})
allhi = pd.concat([g.set_index('t')['hi'].rename(b) for b, g in G.items()], axis=1) if False else None
H = pd.DataFrame({b: g.drop_duplicates('t').set_index('t')['hi'] for b, g in G.items()}).sort_index()
events = []
for b, g in G.items():
    hi = g.hi.to_numpy(); idx = np.flatnonzero(np.diff(np.r_[0, hi.astype(int), 0])); runs = list(zip(idx[::2], idx[1::2]))
    merged = []
    for a, z in runs:                                        # merge runs separated by <=2 readings
        if merged and a - merged[-1][1] <= 2: merged[-1][1] = z
        else: merged.append([a, z])
    for a, z in merged:
        sl = slice(max(0, a - 4), min(len(g), z + 4)); times = g.t.iloc[a:z]
        t0, t1 = g.t.iloc[a] - pd.Timedelta('3h'), g.t.iloc[z - 1] + pd.Timedelta('3h')
        others = [bb for bb in H.columns if bb != b]
        oth_hi = bool(H.loc[(H.index >= t0) & (H.index <= t1), others].any().any())
        ev_ = dict(buoy=b, readings=int(z - a), phyco_co=bool(g.phi.iloc[sl].any()), turb_co=bool(g.uhi.iloc[sl].any()), other_buoy_high=oth_hi,
                   op_eval=int(g.op.iloc[a:z].isin([1, 3, 4]).sum()), op_flag=int(g.op.iloc[a:z].isin([3, 4]).sum()))
        events.append(ev_)
EV = pd.DataFrame(events)
def cls(r):
    if r.readings >= 8 and (r.phyco_co or r.other_buoy_high): return 'Bloom-like'
    if r.readings <= 2 and not (r.phyco_co or r.other_buoy_high or r.turb_co): return 'Short isolated spike'
    return 'Other / unclear'
EV['class'] = EV.apply(cls, axis=1); EV.to_csv('../results/chl_events.csv', index=False)
S = EV.groupby('class').agg(events=('readings', 'size'), readings=('readings', 'sum'), op_eval=('op_eval', 'sum'), op_flag=('op_flag', 'sum'))
S['op_flag_pct'] = (100 * S.op_flag / S.op_eval).round(1); print(S)
OUT['bloom_table'] = S.reset_index().to_dict('records')
json.dump(OUT, open('../results/part3.json', 'w'), indent=1, default=str)
print(json.dumps({k: OUT[k] for k in ['dead_probe_we2', 'stuck_events_by_sensor', 'neighbour_real', 'neighbour_thr']}, indent=1, default=str)); print(E_.head(6).to_string())
