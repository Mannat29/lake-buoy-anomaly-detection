"""Part 1: data inventory, quality, operator-flag coverage and composition, zero-probe events."""
from lib import *
from detectors import run_ids
import numpy as np, pandas as pd, json
D = load_all(); A = pd.concat(D.values(), ignore_index=True)
R = {}
# --- inventory
inv = []
for b, d in D.items():
    dt = d.time.diff().dt.total_seconds() / 60
    inv.append(dict(buoy=b, dataset_id=IDS[b], rows=len(d), first=str(d.time.min()), last=str(d.time.max()),
                    lat=round(float(load_raw(b).latitude.iloc[0]), 4), lon=round(float(load_raw(b).longitude.iloc[0]), 4),
                    pct_15min=round(float((dt == 15).mean() * 100), 1), gaps_gt7d=int((dt > 10080).sum()),
                    longest_gap_days=round(float(dt.max() / 1440), 0)))
R['inventory'] = inv
R['total_rows'] = int(len(A))
R['sensor_values'] = int(sum(A[s].notna().sum() for s in SENSORS))
# --- data quality: missing share, sentinel share per sensor/buoy
q = []
for b, d in D.items():
    for s in SENSORS:
        sent = int(d['sent_' + s].sum()) if 'sent_' + s in d else 0
        q.append(dict(buoy=b, sensor=s, n=len(d), missing=int(d[s].isna().sum()), sentinel=sent))
pd.DataFrame(q).to_csv('../results/quality_by_buoy_sensor.csv', index=False)
# --- operator flag coverage by year (share of rows with a real flag 1/3/4) per buoy x sensor-average
cov = []
for b, d in D.items():
    for s in ['chl', 'phyco', 'do', 'temp', 'turb']:
        ev = d[f'{s}_agg'].isin([1, 3, 4]); has = d[s].notna()
        for y, g in d.groupby('year'):
            cov.append(dict(buoy=b, sensor=s, year=int(y), rows=int(has[g.index].sum()), evaluated=int((ev & has)[g.index].sum())))
C = pd.DataFrame(cov); C.to_csv('../results/operator_flag_coverage.csv', index=False)
tot = C.groupby('sensor')[['rows', 'evaluated']].sum(); tot['pct'] = (tot.evaluated / tot.rows * 100).round(1)
R['flag_coverage_pct'] = tot.pct.to_dict()
# --- flag composition: which single test explains the operator "suspect/fail"?
comp = {}
for s in ['chl', 'phyco', 'do', 'temp', 'turb']:
    ev = A[f'{s}_agg'].isin([1, 3, 4]); pos = A[f'{s}_agg'].isin([3, 4])
    others = {t: A[f'{s}_{t}'].isin([3, 4]) for t in ['gross', 'spike', 'roc', 'flat']}
    n_pos = int(pos.sum())
    only = {}
    for t in others:
        rest = np.zeros(len(A), bool)
        for u, m in others.items():
            if u != t: rest |= m.to_numpy()
        only[t] = int((pos & others[t] & ~rest).sum())
    comp[s] = dict(evaluated=int(ev.sum()), flagged=n_pos, pct_flagged=round(100 * n_pos / max(1, ev.sum()), 1),
                   only_gross=only['gross'], only_spike=only['spike'], only_roc=only['roc'], only_flat=only['flat'])
R['flag_composition'] = comp
# --- oxygen >110%: is it associated with blooms (high chlorophyll)?
hi = A[A['do'] > 110]; lo = A[(A['do'] <= 110) & (A['do'] > 0)]
R['do_over110'] = dict(n=int(len(hi)), pct_of_do=round(100 * len(hi) / A['do'].notna().sum(), 1),
                       median_chl_over110=round(float(hi.chl.median()), 2), median_chl_other=round(float(lo.chl.median()), 2),
                       median_phyco_over110=round(float(hi.phyco.median()), 2), median_phyco_other=round(float(lo.phyco.median()), 2),
                       corr_do_chl=round(float(A[(A['do'] > 0)][['do', 'chl']].corr().iloc[0, 1]), 2))
tb = A[A.turb < 2].turb.notna().sum()
R['turb_under2'] = dict(n=int(tb), pct=round(100 * tb / A.turb.notna().sum(), 1))
# --- dead probe event: all sensors read exactly zero at once
zero_cols = ['do', 'chl', 'phyco', 'turb']
A['n_zero'] = sum((A[c] == 0).astype(int) for c in zero_cols) + (A['temp'] <= 0.05).astype(int)
dead = A['n_zero'] >= 4
R['dead_probe'] = dict(rows=int(dead.sum()), by_buoy=A[dead].groupby('buoy').size().to_dict(),
                       operator_agg_flagged=int(A[dead].temp_agg.isin([3, 4]).sum()),
                       operator_agg_evaluated=int(A[dead].temp_agg.isin([1, 3, 4]).sum()))
dd = A[dead & (A.buoy == 'WE2')]
R['dead_probe']['we2_start'] = str(dd.time.min()); R['dead_probe']['we2_end'] = str(dd.time.max())
R['dead_probe']['we2_days'] = round((dd.time.max() - dd.time.min()).total_seconds() / 86400, 1)
# --- yearly row counts & flagged-share for figure later
A[['buoy', 'time', 'year']].assign(dead=dead.values).to_csv('../results/dead_probe_rows.csv', index=False)
json.dump(R, open('../results/part1.json', 'w'), indent=1, default=str)
print(json.dumps(R, indent=1, default=str)[:6000])
