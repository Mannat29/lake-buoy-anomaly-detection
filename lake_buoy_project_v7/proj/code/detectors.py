"""Transparent single-sensor tests modelled on the QARTOD-style tests described in NOAA TM GLERL-181
(range, spike/step, rate of change, flat line). Pure NumPy so they are easy to port to Spark window functions."""
import numpy as np

CONT_MIN = 20.0  # a step is 'continuous' if consecutive readings are <= 20 min apart (15-min nominal)


def step_arrays(x, tmin):
    """x: float array, tmin: minutes since start (float array). Returns |dx| (nan at start / gaps) and continuity mask."""
    dt = np.r_[np.nan, np.diff(tmin)]
    cont = dt <= CONT_MIN
    dx = np.r_[np.nan, np.diff(x)]
    adx = np.abs(dx)
    adx = np.where(cont, adx, np.nan)
    return adx, cont, dx


def t_range(x, lo=None, hi=None):
    f = np.zeros(len(x), bool)
    ok = ~np.isnan(x)
    if lo is not None:
        f |= ok & (x < lo)
    if hi is not None:
        f |= ok & (x > hi)
    return f


def t_step(x, adx, T):
    """Flag reading t when |x_t - x_{t-1}| > T. A return step right after a flagged reading is not flagged again
    unless the series has not come back near the pre-step level (as in the memo)."""
    big = np.nan_to_num(adx, nan=0.0) > T
    f = big.copy()
    prev = np.r_[False, big[:-1]]
    x2 = np.r_[np.nan, np.nan, x[:-2]]
    back = np.abs(x - x2) <= T  # returned to within T of the value two steps earlier
    f &= ~(prev & back)
    return f


def t_roc(adx, r):
    """Flag four readings when the last four consecutive steps are all larger than r (sustained fast trend)."""
    d = np.nan_to_num(adx, nan=0.0) > r
    n = len(d)
    four = d.copy()
    for k in (1, 2, 3):
        four[k:] &= d[:-k] if k else d
        four[:k] = False
    f = four.copy()
    for k in (1, 2, 3):          # flag the four values x_t .. x_{t-3}
        f[:-k] |= four[k:]
    return f


def run_ids(mask):
    """Lengths of consecutive True runs, returned per element (0 where mask False)."""
    m = mask.astype(np.int8)
    if len(m) == 0:
        return m
    edge = np.flatnonzero(np.diff(np.r_[0, m, 0]))
    starts, ends = edge[::2], edge[1::2]
    out = np.zeros(len(m), int)
    for s, e in zip(starts, ends):
        out[s:e] = e - s
    return out


def t_flat(x, adx, eps, N, gate=None):
    """Flag a run of >= N consecutive steps that each change by < eps. gate: optional boolean mask of values the test applies to
    (e.g. turbidity only when above a threshold, oxygen only when below saturation)."""
    m = (np.nan_to_num(adx, nan=np.inf) < eps)
    if gate is not None:
        m &= gate
    rl = run_ids(m)
    f = rl >= N
    # include the first value of each run
    f[:-1] |= (f[1:] & ~f[:-1])
    return f


def prf(pred, truth, evaluable):
    p = pred & evaluable
    t = truth & evaluable
    tp = int((p & t).sum()); fp = int((p & ~t).sum()); fn = int((~p & t).sum())
    prec = tp / (tp + fp) if tp + fp else float('nan')
    rec = tp / (tp + fn) if tp + fn else float('nan')
    f1 = 2 * tp / (2 * tp + fp + fn) if (2 * tp + fp + fn) else float('nan')
    return dict(tp=tp, fp=fp, fn=fn, precision=prec, recall=rec, f1=f1, n_eval=int(evaluable.sum()), n_pos=int(t.sum()))


def best_threshold(score, truth, evaluable, grid):
    """Pick the threshold t (flag when score > t) that maximises F1 on the grid."""
    best = (-1, None)
    for g in grid:
        r = prf(np.nan_to_num(score, nan=-np.inf) > g, truth, evaluable)
        if r['f1'] == r['f1'] and r['f1'] > best[0]:
            best = (r['f1'], g)
    return best
