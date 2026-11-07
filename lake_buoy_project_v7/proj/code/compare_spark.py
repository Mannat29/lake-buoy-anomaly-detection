"""Check that Spark and Pandas give the same tidy data and the same flags (counts and row by row)."""
import pickle, json, numpy as np, pandas as pd, time
from lib import *
from spark_port import *
spark = get_spark(); spark.sparkContext.setLogLevel('ERROR')
t0 = time.perf_counter(); df, meta = run_pipeline(spark); df = df.cache(); n = df.count(); print('spark rows', n, 'build+run s', round(time.perf_counter() - t0, 1))
fcols = ['f_dead', 'f_neigh_temp'] + [f'f_{k}_{s}' for k in ('spike', 'stuck') for s in SENSORS]
S = df.select('buoy', 'time', 'year', *SENSORS, *[f'sent_{s}' for s in SENSORS], *fcols).toPandas()
D = pickle.load(open('../results/D_flags.pkl', 'rb'))
rows = []; mism = 0
for b in BUOYS:
    p = D[b]; q = S[S.buoy == b].sort_values('time').reset_index(drop=True)
    assert len(p) == len(q) and (p.time.values == q.time.values).all(), b
    for s in SENSORS:
        both = p[s].notna() & q[s].notna(); same_nan = (p[s].isna() == q[s].isna()).all()
        maxdiff = float((p[s][both] - q[s][both]).abs().max()) if both.any() else 0.0
        rows.append(dict(buoy=b, check=f'tidy_{s}', pandas=int(p[s].notna().sum()), spark=int(q[s].notna().sum()), same_missing=bool(same_nan), max_abs_diff=maxdiff))
        rows.append(dict(buoy=b, check=f'sentinel_{s}', pandas=int(p['sent_' + s].sum()), spark=int(q['sent_' + s].sum()), same_missing=True, max_abs_diff=0.0))
    for c in fcols:
        if c == 'f_neigh_temp' or c == 'f_dead' or c in p:
            pc = p[c].fillna(False).astype(bool).to_numpy(); qc = q[c].fillna(False).astype(bool).to_numpy()
            rows.append(dict(buoy=b, check=c, pandas=int(pc.sum()), spark=int(qc.sum()), differing_rows=int((pc != qc).sum())))
            mism += int((pc != qc).sum())
R = pd.DataFrame(rows); R.to_csv('../results/spark_vs_pandas.csv', index=False)
fl = R[R.check.str.startswith('f_')]
print('FLAG CHECKS:', len(fl), 'all counts equal:', bool((fl.pandas == fl.spark).all()), 'total differing rows:', mism)
print('flag totals pandas/spark:', int(fl.pandas.sum()), int(fl.spark.sum()))
td = R[R.check.str.startswith('tidy') | R.check.str.startswith('sent')]
print('TIDY: counts equal', bool((td.pandas == td.spark).all()), 'same missing', bool(td.same_missing.all()), 'max abs diff', td.max_abs_diff.max())
print(fl[fl.pandas != fl.spark].to_string())
NB = pickle.load(open('../results/NB.pkl', 'rb'))
print({b: (round(meta[b]['thr'], 6), round(NB[b]['thr'], 6)) for b in BUOYS})
json.dump(dict(flag_checks=len(fl), flag_counts_equal=bool((fl.pandas == fl.spark).all()), differing_rows=mism, flag_total_pandas=int(fl.pandas.sum()), flag_total_spark=int(fl.spark.sum()),
               tidy_counts_equal=bool((td.pandas == td.spark).all()), tidy_max_abs_diff=float(td.max_abs_diff.max()),
               nb_thr_spark={b: meta[b]['thr'] for b in BUOYS}, nb_thr_pandas={b: NB[b]['thr'] for b in BUOYS}), open('../results/spark_vs_pandas.json', 'w'), indent=1)
