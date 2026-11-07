"""Our transparent detectors as small reusable functions (used by synthetic tests and the replay prototype)."""
import numpy as np, pandas as pd
from detectors import run_ids
FLOOR = dict(temp=0.5, chl=0.5, phyco=0.5, do=5.0, turb=5.0, cond=0.003)
K = 6.0; STUCK_N = 24; WIN = 9

def hampel_flags(x, time, floor, sigma=None, k=K):
    x = pd.Series(np.asarray(x, float)); t = pd.Series(pd.to_datetime(time))
    med = x.rolling(WIN, center=True, min_periods=5).median(); r = x - med
    span = (t.shift(-4) - t.shift(4)).dt.total_seconds() / 60; ok = (span <= 150)
    if sigma is None:
        sigma = 1.4826 * np.nanmedian(np.abs(r[ok] - np.nanmedian(r[ok])))
    thr = max(k * sigma, floor)
    return ((r.abs() > thr) & ok).fillna(False).to_numpy(), sigma, thr

def stuck_flags(x, time, n=STUCK_N):
    x = np.asarray(x, float); t = pd.Series(pd.to_datetime(time))
    dt = t.diff().dt.total_seconds().to_numpy() / 60
    same = (np.r_[np.nan, np.diff(x)] == 0) & (dt <= 20) & (x != 0) & ~np.isnan(x)
    rl = run_ids(same); f = rl >= n
    f[:-1] |= (f[1:] & ~f[:-1])
    return f
