from lib import *
from detectors import *
import numpy as np, pandas as pd, json, itertools

def series(d, s):
    x = d[s].to_numpy(float)
    tmin = (d.time.values - d.time.values[0]).astype('timedelta64[s]').astype(float) / 60
    adx, cont, dx = step_arrays(x, tmin)
    return x, tmin, adx

def truth_eval(d, s, test):
    f = d[f'{s}_{test}'].to_numpy(float)
    return np.isin(f, [3, 4]), np.isin(f, [1, 3, 4])

def tune_sensor(D, s, train_buoy='WE2', train_years=(2015, 2016)):
    d = D[train_buoy]; d = d[d.year.isin(train_years)].reset_index(drop=True)
    x, tmin, adx = series(d, s); ok = ~np.isnan(x)
    P = {}
    # range: one-sided threshold scans against operator gross-range flag, then combine
    truth, ev = truth_eval(d, s, 'gross'); ev &= ok
    if truth[ev].sum() >= 30:
        xs = x[ev]
        grid = np.unique(np.nanquantile(xs, np.linspace(0, 1, 801)))
        f_hi, hi = best_threshold(x, truth, ev, grid)
        f_lo, lo = best_threshold(-x, truth, ev, -grid)
        lo = -lo if lo is not None else None
        cands = [(None, None), (None, hi), (lo, None), (lo, hi)]
        best = max(((prf(t_range(x, a, b), truth, ev)['f1'], a, b) for a, b in cands), key=lambda r: (r[0] if r[0] == r[0] else -1))
        P['range'] = dict(lo=best[1], hi=best[2], f1_train=best[0])
    # spike
    truth, ev = truth_eval(d, s, 'spike'); ev &= ok
    if truth[ev].sum() >= 30:
        g = np.nanquantile(adx, [.9, .95, .98, .99, .995, .999, .9995, .9999])
        f1, T = best_threshold(adx, truth, ev, np.unique(g))
        P['spike'] = dict(T=float(T), f1_train=f1)
    # rate of change (4 steps in a row above r)
    truth, ev = truth_eval(d, s, 'roc'); ev &= ok
    if truth[ev].sum() >= 30:
        best = (-1, None)
        for r in np.unique(np.nanquantile(adx, [.3, .5, .6, .7, .8, .9, .95, .98, .99])):
            res = prf(t_roc(adx, r), truth, ev)
            if res['f1'] == res['f1'] and res['f1'] > best[0]: best = (res['f1'], r)
        P['roc'] = dict(r=float(best[1]), f1_train=best[0])
    # flat line
    truth, ev = truth_eval(d, s, 'flat'); ev &= ok
    if truth[ev].sum() >= 30:
        best = (-1, None)
        pos_x = np.nan_to_num(x, nan=0)
        gates = {'all': None, 'x>1': pos_x > 1, 'x>2': pos_x > 2, 'x>5': pos_x > 5, 'x<100': pos_x < 100, 'x<110': pos_x < 110}
        for eps in [.0005, .001, .002, .005, .01, .02, .05, .1, .2, .5]:
            for N in [4, 6, 8, 12, 16, 24, 32, 48, 96]:
                for gn, gm in gates.items():
                    res = prf(t_flat(x, adx, eps, N, gm), truth, ev)
                    if res['f1'] == res['f1'] and res['f1'] > best[0]: best = (res['f1'], (eps, N, gn))
        P['flat'] = dict(eps=best[1][0], N=best[1][1], gate=best[1][2], f1_train=best[0])
    return P

def apply(d, s, P):
    """Apply tuned tests to one buoy frame; return dict of boolean flag arrays."""
    x, tmin, adx = series(d, s); out = {}
    if 'range' in P: out['range'] = t_range(x, P['range']['lo'], P['range']['hi'])
    if 'spike' in P: out['spike'] = t_step(x, adx, P['spike']['T'])
    if 'roc' in P: out['roc'] = t_roc(adx, P['roc']['r'])
    if 'flat' in P:
        pos = np.nan_to_num(x, nan=0)
        g = {'all': None, 'x>1': pos > 1, 'x>2': pos > 2, 'x>5': pos > 5, 'x<100': pos < 100, 'x<110': pos < 110}[P['flat']['gate']]
        out['flat'] = t_flat(x, adx, P['flat']['eps'], P['flat']['N'], g)
    return out

if __name__ == '__main__':
    D = load_all(); params = {}
    for s in ['chl', 'phyco', 'do', 'temp', 'turb']:
        params[s] = tune_sensor(D, s)
        print(s, json.dumps(params[s], default=float))
    json.dump(params, open('../results/tuned_params.json', 'w'), indent=1, default=float)
