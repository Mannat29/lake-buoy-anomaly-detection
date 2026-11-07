"""Part 2: our own transparent detectors on all four buoys + comparison with operator flags."""
from lib import *
from detectors import run_ids
import numpy as np, pandas as pd, json
D = load_all()
FLOOR = dict(temp=0.5, chl=0.5, phyco=0.5, do=5.0, turb=5.0, cond=0.003)   # analyst-chosen minimum jump size
K = 6.0; STUCK_N = 24; WIN = 9

def hampel(d, s):
    x = d[s]; med = x.rolling(WIN, center=True, min_periods=5).median()
    r = (x - med); span = (d.time.shift(-4) - d.time.shift(4)).dt.total_seconds() / 60
    ok = (span <= 150)
    sig = 1.4826 * np.nanmedian(np.abs(r[ok] - np.nanmedian(r[ok])))
    thr = max(K * sig, FLOOR[s])
    return ((r.abs() > thr) & ok).fillna(False).to_numpy(), float(sig), float(thr)

def stuck(d, s):
    x = d[s].to_numpy(float); dt = d.time.diff().dt.total_seconds().to_numpy() / 60
    same = (np.r_[np.nan, np.diff(x)] == 0) & (dt <= 20) & (x != 0) & ~np.isnan(x)
    rl = run_ids(same); f = rl >= STUCK_N
    f[:-1] |= (f[1:] & ~f[:-1])
    return f

# dead probe (all sensors read zero together)
for b, d in D.items():
    nz = sum((d[c] == 0).astype(int) for c in ['do', 'chl', 'phyco', 'turb']) + (d['temp'] <= 0.05).astype(int)
    d['f_dead'] = (nz >= 4).to_numpy()
# per-sensor spike & stuck
meta = {}
for b, d in D.items():
    for s in SENSORS:
        f, sig, thr = hampel(d, s); d[f'f_spike_{s}'] = f & ~d['f_dead'].to_numpy(); meta[f'{b}_{s}'] = dict(sigma=sig, thr=thr)
        d[f'f_stuck_{s}'] = stuck(d, s)
# neighbour check on temperature (aligned 15-min grid)
def grid(s, mask_dead=True):
    cols = {}
    for b, d in D.items():
        x = d[s].where(~d['f_dead']) if mask_dead else d[s]
        t = d.time.dt.round('15min'); ser = pd.Series(x.values, index=t); cols[b] = ser[~ser.index.duplicated()]
    return pd.DataFrame(cols).sort_index()
W = grid('temp'); NB = {}
for b in W:
    oth = W.drop(columns=b); n = oth.notna().sum(axis=1); ref = oth.median(axis=1).where(n >= 2)
    res = (W[b] - ref)
    roll = res.rolling(24, min_periods=12).median()           # 6-hour persistent deviation
    sig = 1.4826 * np.nanmedian(np.abs(roll.dropna() - np.nanmedian(roll.dropna())))
    thr = max(5 * sig, 1.0)
    NB[b] = dict(res=res, roll=roll, sigma=float(sig), thr=float(thr))
    d = D[b]; t = d.time.dt.round('15min'); r2 = roll.reindex(t).to_numpy()
    d['nb_roll_temp'] = r2; d['f_neigh_temp'] = (np.abs(r2) > thr) & ~d['f_dead'].to_numpy()
    meta[f'{b}_temp_neighbour'] = dict(sigma=float(sig), thr=float(thr))
json.dump(meta, open('../results/detector_meta.json', 'w'), indent=1)
# ---- summaries
rows = []
for b, d in D.items():
    for s in SENSORS:
        has = d[s].notna()
        any_f = d[f'f_spike_{s}'] | d[f'f_stuck_{s}'] | d['f_dead'] | (d['f_neigh_temp'] if s == 'temp' else False)
        d[f'f_any_{s}'] = any_f & has
        for y, g in d.groupby('year'):
            ix = g.index
            ev = d.loc[ix, f'{s}_agg'].isin([1, 3, 4]) & has[ix] if s != 'cond' else pd.Series(False, index=ix)
            rows.append(dict(buoy=b, sensor=s, year=int(y), n=int(has[ix].sum()),
                             ours_any=int(d.loc[ix, f'f_any_{s}'].sum()), ours_spike=int((d.loc[ix, f'f_spike_{s}'] & has[ix]).sum()),
                             ours_stuck=int((d.loc[ix, f'f_stuck_{s}'] & has[ix]).sum()), ours_dead=int((d.loc[ix, 'f_dead'] & has[ix]).sum()),
                             ours_neigh=int((d.loc[ix, 'f_neigh_temp'] & has[ix]).sum()) if s == 'temp' else 0,
                             op_eval=int(ev.sum()), op_flag=int((d.loc[ix, f'{s}_agg'].isin([3, 4]) & ev).sum())))
Y = pd.DataFrame(rows); Y.to_csv('../results/our_flags_by_year.csv', index=False)
# agreement with operator on operator-evaluated rows (aggregate flag 3/4 = positive)
ag = []
for s in ['chl', 'phyco', 'do', 'temp', 'turb']:
    tp = fp = fn = n = 0
    for b, d in D.items():
        ev = d[f'{s}_agg'].isin([1, 3, 4]) & d[s].notna(); op = d[f'{s}_agg'].isin([3, 4]); ours = d[f'f_any_{s}']
        tp += int((ours & op & ev).sum()); fp += int((ours & ~op & ev).sum()); fn += int((~ours & op & ev).sum()); n += int(ev.sum())
    ag.append(dict(sensor=s, evaluated=n, ours=tp + fp, operator=tp + fn, both=tp, ours_also_operator=round(tp / max(1, tp + fp), 3)))
pd.DataFrame(ag).to_csv('../results/agreement_with_operator.csv', index=False)
print(pd.DataFrame(ag).to_string())
print(Y.groupby('sensor')[['n', 'ours_any', 'ours_spike', 'ours_stuck', 'ours_dead', 'ours_neigh']].sum())
print({k: {a: round(b, 4) for a, b in v.items()} for k, v in meta.items() if 'WE2' in k})
# operator flat-line on temperature: is the series really flat there? (range over +/-4 readings)
rng = []
for b, d in D.items():
    mx = d.temp.rolling(9, center=True, min_periods=9).max(); mn = d.temp.rolling(9, center=True, min_periods=9).min()
    rng.append(pd.DataFrame({'rng': mx - mn, 'flag': d['temp_flat'], 'dead': d['f_dead']}))
rg = pd.concat(rng); rg = rg[~rg.dead].dropna()
t = rg.groupby('flag').rng.agg(['count', 'median', lambda x: x.quantile(.9)]).round(3); t.columns = ['n', 'median_range_C_over_2h', 'p90']
print(t); t.to_csv('../results/op_temp_flat_vs_actual_range.csv')
import pickle; pickle.dump({b: d for b, d in D.items()}, open('../results/D_flags.pkl', 'wb'))
pickle.dump({b: dict(res=NB[b]['res'], roll=NB[b]['roll'], sigma=NB[b]['sigma'], thr=NB[b]['thr']) for b in NB}, open('../results/NB.pkl', 'wb'))
