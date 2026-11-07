"""Pandas timing on the real data (1 core). Spark is NOT available in this workspace, so no Spark numbers are claimed."""
import time, json, resource, numpy as np, pandas as pd
from lib import *
from ours import *
def med(f, n=3):
    ts = []
    for _ in range(n):
        t = time.perf_counter(); r = f(); ts.append(time.perf_counter() - t)
    return float(np.median(ts)), r
out = {}
out['ingest_csv_s'], _ = med(lambda: [pd.read_csv(UP + f, skiprows=[1]) for f in FILES.values()])
out['tidy_merge_s'], D = med(lambda: load_all())
def agg(): 
    A = pd.concat(D.values()); return A.groupby(['buoy', 'year']).agg(n=('chl', 'size'), chl=('chl', 'median'), temp=('temp', 'mean'))
out['aggregate_s'], _ = med(agg)
def det():
    for b, d in D.items():
        for s in SENSORS: hampel_flags(d[s], d.time, FLOOR[s]); stuck_flags(d[s], d.time)
out['all_detectors_s'], _ = med(det, n=3)
big = pd.concat([D['WE2']] * 20, ignore_index=True); big['time'] = pd.date_range('2000-01-01', periods=len(big), freq='15min')
out['rows_real'] = int(sum(len(d) for d in D.values())); out['rows_replicated_x20'] = int(len(big))
out['hampel_temp_x20_s'], _ = med(lambda: hampel_flags(big['temp'], big['time'], FLOOR['temp']), n=1)
out['peak_mem_MB'] = round(resource.getrusage(resource.RUSAGE_SELF).ru_maxrss / 1024)
import platform, os; out['machine'] = dict(cores=os.cpu_count(), python=platform.python_version(), pandas=pd.__version__)
json.dump(out, open('../results/benchmark.json', 'w'), indent=1); print(json.dumps(out, indent=1))
