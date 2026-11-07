"""ONE script: Spark vs Pandas parity (same rules), stuck-run reconciliation, operator-flag checks (part d), fair timing.
Usage: python spark_reconcile.py A   (parity + reconcile + part d)   |   python spark_reconcile.py B   (benchmark)   |   all
Saves ../results/spark_results.json and CSVs in ../results/spark/."""
import sys, os, json, time, platform, pickle, subprocess, numpy as np, pandas as pd
import pyspark
from pyspark.sql import Window, functions as F
from lib import *
from ours import hampel_flags, FLOOR
from spark_port import *

RES = '../results/'; OUT = RES + 'spark/'; os.makedirs(OUT, exist_ok=True); WORK = '/home/claude/work/'; os.makedirs(WORK, exist_ok=True)
JS = RES + 'spark_results.json'
R = json.load(open(JS)) if os.path.exists(JS) else {}
def save(): json.dump(R, open(JS, 'w'), indent=1, default=str)
spark = get_spark(1, '2g'); spark.sparkContext.setLogLevel('ERROR')
phase = sys.argv[1] if len(sys.argv) > 1 else 'all'

cpu = subprocess.run("lscpu | grep 'Model name' | cut -d: -f2", shell=True, capture_output=True, text=True).stdout.strip()
R['env'] = dict(cpu=cpu, cores=os.cpu_count(), ram_gb=round(os.sysconf('SC_PAGE_SIZE') * os.sysconf('SC_PHYS_PAGES') / 1e9, 1), python=platform.python_version(),
                pandas=pd.__version__, pyspark=pyspark.__version__, java=subprocess.run('java -version 2>&1 | head -1', shell=True, capture_output=True, text=True).stdout.strip(),
                spark_master='local[1]', spark_driver_memory='2g')

if phase in ('A', 'all'):
    spark.conf.set('spark.sql.shuffle.partitions', '8')
    T = build_tidy(spark)
    df, meta, W = run_pipeline(T)
    df.write.mode('overwrite').parquet(WORK + 'flags.parquet'); W.unpersist()
    S = spark.read.parquet(WORK + 'flags.parquet')
    # ---- (b) parity vs Pandas
    fl = [c for c in S.columns if c.startswith('f_')]
    Sp = S.select('buoy', 'time', *SENSORS, *fl).toPandas()
    D = pickle.load(open(RES + 'D_flags.pkl', 'rb'))
    rows = []
    for b in BUOYS:
        p = D[b]; q = Sp[Sp.buoy == b].sort_values('time').reset_index(drop=True)
        assert len(p) == len(q) and (p.time.values == q.time.values).all()
        for c in fl:
            pc = p[c].fillna(False).astype(bool).to_numpy(); qc = q[c].fillna(False).astype(bool).to_numpy()
            kind = c.split('_')[1]; sen = c.split('_', 2)[2] if kind in ('spike', 'stuck') else ('temp' if kind == 'neigh' else 'all')
            inter = int((pc & qc).sum()); uni = int((pc | qc).sum())
            rows.append(dict(buoy=b, detector=kind, sensor=sen, pandas=int(pc.sum()), spark=int(qc.sum()), both=inter, only_pandas=int((pc & ~qc).sum()), only_spark=int((~pc & qc).sum()),
                             jaccard=(inter / uni if uni else 1.0), identical_rows_share=float((pc == qc).mean())))
    P = pd.DataFrame(rows); P.to_csv(OUT + 'spark_vs_pandas_by_buoy_sensor.csv', index=False)
    g = P.groupby('detector')[['pandas', 'spark', 'both', 'only_pandas', 'only_spark']].sum()
    g['jaccard'] = g.both / (g.both + g.only_pandas + g.only_spark); g['rows_total'] = len(Sp)
    g['identical_rows_share'] = 1 - (g.only_pandas + g.only_spark) / (g.rows_total * P.groupby('detector').sensor.nunique() )
    g.to_csv(OUT + 'spark_vs_pandas_by_detector.csv'); R['parity'] = dict(by_detector=g.round(6).reset_index().to_dict('records'),
        total_pandas=int(P.pandas.sum()), total_spark=int(P.spark.sum()), differing_rows=int((P.only_pandas + P.only_spark).sum()),
        neighbour_thr_spark={b: meta[b]['thr'] for b in BUOYS}, neighbour_thr_pandas={b: float(pickle.load(open(RES + 'NB.pkl', 'rb'))[b]['thr']) for b in BUOYS})
    # tidy parity (missing counts, values)
    t = []
    for b in BUOYS:
        p = D[b]; q = Sp[Sp.buoy == b].sort_values('time').reset_index(drop=True)
        for s in SENSORS:
            both = p[s].notna() & q[s].notna(); t.append((bool((p[s].isna() == q[s].isna()).all()), float((p[s][both] - q[s][both]).abs().max()) if both.any() else 0.0))
    R['parity']['tidy_missing_identical_all'] = all(x[0] for x in t); R['parity']['tidy_max_abs_diff'] = max(x[1] for x in t)
    # why do a few rows differ? re-read Pandas with exact float parsing (round_trip) and re-run Hampel on those buoy/sensors
    diff = P[(P.detector == 'spike') & ((P.only_pandas + P.only_spark) > 0)]; rt = []
    for _, r in diff.iterrows():
        raw = pd.read_csv(UP + FILES[r.buoy], skiprows=[1], float_precision='round_trip', usecols=['time', SENS[r.sensor]])
        raw['time'] = pd.to_datetime(raw['time'], utc=True).dt.tz_localize(None); raw = raw.sort_values('time').reset_index(drop=True)
        x = raw[SENS[r.sensor]].astype(float).mask(lambda v: v == -999)
        fl_, _, _ = hampel_flags(x, raw.time, FLOOR[r.sensor]); fl_ = fl_ & ~D[r.buoy].f_dead.to_numpy()
        q = Sp[Sp.buoy == r.buoy].sort_values('time').reset_index(drop=True)[f'f_spike_{r.sensor}'].fillna(False).astype(bool).to_numpy()
        rt.append(dict(buoy=r.buoy, sensor=r.sensor, rows_differing_default_pandas=int(r.only_pandas + r.only_spark), rows_differing_pandas_round_trip_parse=int((fl_ != q).sum())))
    R['parity']['float_parse_check'] = rt

    # ---- (a) stuck runs from Spark
    w = Window.partitionBy('buoy').orderBy('time'); wu = w.rowsBetween(Window.unboundedPreceding, Window.currentRow)
    runs_all, eps_all = [], []
    for s in SENSORS:
        x = S.select('buoy', 'time', F.col(s).alias('v'), F.col(f'f_stuck_{s}').alias('f'))
        x = x.withColumn('pf', F.coalesce(F.lag('f').over(w), F.lit(False))).withColumn('pv', F.lag('v').over(w)).withColumn('pt', F.lag('time').over(w))
        gap = (F.unix_timestamp('time') - F.unix_timestamp('pt')) / 60
        epb = F.col('f') & ~F.col('pf'); srb = F.col('f') & (epb | (gap > 20) | (F.col('v') != F.col('pv')))
        x = x.withColumn('ep', F.sum(epb.cast('int')).over(wu)).withColumn('sr', F.sum(srb.cast('int')).over(wu)).filter('f')
        runs = x.groupBy('buoy', 'ep', 'sr').agg(F.min('time').alias('start'), F.max('time').alias('end'), F.count('*').alias('readings'), F.first('v').alias('value')).withColumn('sensor', F.lit(s))
        runs_all.append(runs.toPandas())
    RUN = pd.concat(runs_all); RUN['hours'] = ((RUN.end - RUN.start).dt.total_seconds() / 3600).round(1)
    RUN.drop(columns='sr').sort_values('readings', ascending=False).to_csv(OUT + 'stuck_runs_spark.csv', index=False)
    EP = RUN.groupby(['buoy', 'sensor', 'ep']).agg(start=('start', 'min'), end=('end', 'max'), readings=('readings', 'sum'), n_runs=('readings', 'size'), longest_run=('readings', 'max'), value=('value', 'first')).reset_index().drop(columns='ep')
    EP['days'] = ((EP.end - EP.start).dt.total_seconds() / 86400).round(1); EP = EP.sort_values('readings', ascending=False); EP.to_csv(OUT + 'stuck_episodes_spark.csv', index=False)
    we8 = EP[(EP.buoy == 'WE8') & (EP.sensor == 'phyco')].iloc[0]; we2 = EP[(EP.buoy == 'WE2') & (EP.sensor == 'temp')].iloc[0]
    d2 = S.filter("buoy = 'WE2'").agg(F.sum(F.col('f_dead').cast('int')).alias('dead'), F.sum((F.col('f_dead') & F.col('f_stuck_temp')).cast('int')).alias('dead_and_stuck'),
                                       F.sum((~F.col('f_dead') & F.col('f_stuck_temp')).cast('int')).alias('stuck_not_dead')).first().asDict()
    top2 = RUN[(RUN.buoy == 'WE2') & (RUN.sensor == 'temp')].sort_values('readings', ascending=False).head(4)
    R['stuck_reconcile'] = dict(
        we8_phyco=dict(episode_readings=int(we8.readings), episode_start=str(we8.start), episode_end=str(we8.end), episode_days=float(we8.days), n_unbroken_runs=int(we8.n_runs), longest_unbroken_run_readings=int(we8.longest_run), value=float(we8.value)),
        we2_temp=dict(episode_readings=int(we2.readings), episode_start=str(we2.start), episode_end=str(we2.end), episode_days=float(we2.days), n_unbroken_runs=int(we2.n_runs), longest_unbroken_run_readings=int(we2.longest_run),
                      top_runs=top2[['start', 'end', 'readings', 'value']].astype(str).to_dict('records')),
        we2_dead_probe_rows=d2,
        note='Episode = all stuck-flagged readings of one constant value, joined across data gaps. Unbroken run = consecutive readings <= 20 min apart. Dead probe = rows where >=4 of 5 sensors read exactly 0.')
    R['stuck_events_by_sensor_spark'] = EP.groupby('sensor').size().to_dict()

    # ---- (d) operator-flag reproduction in Spark
    T2 = S.select('buoy', 'year' if 'year' in S.columns else F.year('time').alias('year'), 'f_dead', *[f'f_{k}_temp' for k in ('spike', 'stuck')], 'f_neigh_temp')
    # operator flags need the tidy table again
    Tt = T.select('buoy', 'time', 'year', 'f_dead', *[f'{s}_{t}' for s in ['chl', 'phyco', 'do', 'temp', 'turb'] for t in TESTS], *SENSORS)
    ours = S.select('buoy', 'time', 'f_neigh_temp', 'f_spike_temp', 'f_stuck_temp')
    TY = Tt.join(ours, ['buoy', 'time'])
    has = F.col('temp').isNotNull(); ev = F.col('temp_agg').isin(1, 3, 4) & has; fg = F.col('temp_agg').isin(3, 4) & ev
    ou = (F.col('f_spike_temp') | F.col('f_stuck_temp') | F.col('f_dead') | F.col('f_neigh_temp')) & has
    yr = TY.groupBy('year').agg(F.sum(has.cast('int')).alias('n'), F.sum(ev.cast('int')).alias('op_eval'), F.sum(fg.cast('int')).alias('op_flag'), F.sum(ou.cast('int')).alias('ours_any')).orderBy('year').toPandas()
    yr['op_flagged_share_of_readings'] = (yr.op_flag / yr.n).round(4); yr['ours_share'] = (yr.ours_any / yr.n).round(4); yr.to_csv(OUT + 'temp_flagged_share_by_year_spark.csv', index=False)
    old = pd.read_csv(RES + 'our_flags_by_year.csv'); o = old[old.sensor == 'temp'].groupby('year')[['n', 'op_eval', 'op_flag', 'ours_any']].sum().reset_index()
    m = yr.merge(o, on='year', suffixes=('_spark', '_pandas'))
    R['partd_temp_by_year_identical'] = bool(all((m[f'{c}_spark'] == m[f'{c}_pandas']).all() for c in ['n', 'op_eval', 'op_flag', 'ours_any']))
    comp = []
    for s in ['chl', 'phyco', 'do', 'temp', 'turb']:
        pos = F.col(f'{s}_agg').isin(3, 4); evs = F.col(f'{s}_agg').isin(1, 3, 4)
        tt = {t: F.col(f'{s}_{t}').isin(3, 4) for t in ['gross', 'spike', 'roc', 'flat']}
        agg = [F.sum(evs.cast('int')).alias('evaluated'), F.sum(pos.cast('int')).alias('flagged')]
        for t in tt:
            rest = [v for u, v in tt.items() if u != t]; only = pos & tt[t] & ~rest[0] & ~rest[1] & ~rest[2]
            agg.append(F.sum(only.cast('int')).alias(f'only_{t}'))
        comp.append(dict(sensor=s, **Tt.agg(*agg).first().asDict()))
    C = pd.DataFrame(comp); C['rows'] = [int(Tt.filter(F.col(s).isNotNull()).count()) for s in C.sensor]; C.to_csv(OUT + 'operator_flag_composition_spark.csv', index=False)
    p1 = json.load(open(RES + 'part1.json'))['flag_composition']
    R['partd_composition_identical'] = bool(all(int(C.set_index('sensor').loc[s, k]) == p1[s][k] for s in p1 for k in ['evaluated', 'flagged', 'only_gross', 'only_spike', 'only_roc', 'only_flat']))
    R['partd_composition'] = C.to_dict('records')
    dead_by = S.filter('f_dead').groupBy('buoy').count().toPandas().set_index('buoy')['count'].to_dict(); pd1 = json.load(open(RES + 'part1.json'))['dead_probe']
    R['partd_dead_probe'] = dict(spark_rows_by_buoy=dead_by, pandas_rows_by_buoy=pd1['by_buoy'], identical=dead_by == pd1['by_buoy'])
    save(); print('PHASE A DONE'); print(json.dumps({k: R[k] for k in ['parity']}, default=str)[:1500]); print(R['stuck_reconcile']); print(R['partd_temp_by_year_identical'], R['partd_composition_identical'], R['partd_dead_probe'])

if phase in ('B', 'B2', 'all'):
    D = {b: load(b) for b in FILES}
    def timeit(fn, runs=3, warm=True, max_warm=100):
        t0 = time.perf_counter(); fn(); cold = time.perf_counter() - t0
        if cold > max_warm: runs = 1
        ts = []
        for _ in range(runs):
            t = time.perf_counter(); fn(); ts.append(time.perf_counter() - t)
        return dict(median_s=round(float(np.median(ts)), 3), runs_s=[round(x, 3) for x in ts], first_run_s=round(cold, 3))
    RESUME = phase == 'B2'
    B = json.load(open(RES + 'spark/_bench_partial.json')) if RESUME else []
    have = lambda j, e, v: any(r['job'] == j and r['engine'] == e and r['variant'] == v for r in B)
    def add(job, engine, variant, d, **kw): B.append(dict(job=job, engine=engine, variant=variant, **d, **kw)); print(B[-1]['job'], engine, variant, d['median_s'], flush=True)
    # ---------- Pandas (in-memory frames for aggregate / detectors; same tidy table)
    if not RESUME: add('ingest (read 4 CSV)', 'pandas', 'read_csv', timeit(lambda: [pd.read_csv(UP + f, skiprows=[1]) for f in FILES.values()]))
    if not RESUME: add('ingest + tidy', 'pandas', 'load_all', timeit(lambda: {b: load(b) for b in FILES}))
    def p_agg():
        A = pd.concat(D.values()); return A.groupby(['buoy', 'year']).agg(n=('chl', 'size'), chl=('chl', 'median'), temp=('temp', 'mean'))
    if not RESUME: add('aggregate (buoy x year)', 'pandas', 'groupby', timeit(p_agg))
    def p_hampel():
        for b, d in D.items():
            for s in SENSORS: hampel_flags(d[s], d.time, FLOOR[s])
    if not RESUME: add('Hampel (6 sensors x 4 buoys)', 'pandas', 'rolling median', timeit(p_hampel))
    def p_neigh():
        cols = {}
        for b, d in D.items():
            x = d['temp'].where(~(d['do'].eq(0) & d['chl'].eq(0))); t = d.time.dt.round('15min'); ser = pd.Series(x.values, index=t); cols[b] = ser[~ser.index.duplicated()]
        Wd = pd.DataFrame(cols).sort_index()
        for b in Wd:
            oth = Wd.drop(columns=b); n = oth.notna().sum(axis=1); ref = oth.median(axis=1).where(n >= 2); roll = (Wd[b] - ref).rolling(24, min_periods=12).median()
            sig = 1.4826 * np.nanmedian(np.abs(roll.dropna() - np.nanmedian(roll.dropna()))); (roll.abs() > max(5 * sig, 1.0)).sum()
    if not RESUME: add('neighbour check (temperature)', 'pandas', 'rolling median', timeit(p_neigh))
    # ---------- Spark variants
    def noop(df): df.write.format('noop').mode('overwrite').save()
    spark.conf.set('spark.sql.shuffle.partitions', '8')
    if not RESUME: add('ingest (read 4 CSV)', 'spark', 'CSV, parse only', timeit(lambda: noop(spark.read.csv([UP + f for f in FILES.values()], header=True)) if False else [noop(ingest(spark, b)) for b in BUOYS]))
    if not RESUME: add('ingest + tidy', 'spark', 'CSV + tidy', timeit(lambda: noop(build_tidy(spark))))
    T = build_tidy(spark).persist(); T.count()
    if not RESUME: T.write.mode('overwrite').parquet(WORK + 'tidy.parquet')
    if not RESUME: add('ingest + tidy', 'spark', 'Parquet read of tidy table (stored form)', timeit(lambda: noop(spark.read.parquet(WORK + 'tidy.parquet'))))
    def s_agg(X): return X.groupBy('buoy', 'year').agg(F.count('*'), F.percentile('chl', F.lit(0.5)), F.avg('temp')).collect()
    def s_ham(X, native): return hampel(X, native=native).agg(*[F.sum(F.col(f'f_spike_{s}').cast('int')) for s in SENSORS]).collect()
    def s_neigh(X):
        o, m, Wc = neighbour_check(X); o.agg(F.sum(F.col('f_neigh_temp').cast('int'))).collect(); Wc.unpersist()
    PQ = lambda: spark.read.parquet(WORK + 'tidy.parquet')
    for name, part, src, native in [('A: shuffle=200, in-memory, collect_list', '200', lambda: T, False), ('B: shuffle=8, in-memory, collect_list', '8', lambda: T, False),
                                    ('C: shuffle=8, Parquet input, collect_list', '8', PQ, False), ('D: shuffle=8, Parquet input, lag/lead window', '8', PQ, True)]:
        spark.conf.set('spark.sql.shuffle.partitions', part)
        if name[0] in 'AB' and not have('aggregate (buoy x year)', 'spark', name): add('aggregate (buoy x year)', 'spark', name, timeit(lambda: s_agg(src())))
        if not have('Hampel (6 sensors x 4 buoys)', 'spark', name): add('Hampel (6 sensors x 4 buoys)', 'spark', name, timeit(lambda: s_ham(src(), native)))
        if not have('neighbour check (temperature)', 'spark', name): add('neighbour check (temperature)', 'spark', name, timeit(lambda: s_neigh(src())))
        json.dump(B, open(RES + 'spark/_bench_partial.json', 'w'))
    # ---------- SYNTHETIC replicated test: WE2 temperature Hampel only, x10 and x50
    spark.conf.set('spark.sql.shuffle.partitions', '8')
    base = D['WE2'][['time', 'temp']].copy()
    for N in (10, 50):
        big = pd.concat([base] * N, ignore_index=True); big['time'] = pd.date_range('2000-01-01', periods=len(big), freq='15min')
        add(f'SYNTHETIC x{N} Hampel temperature ({len(big):,} rows)', 'pandas', 'rolling median', timeit(lambda: hampel_flags(big['temp'], big['time'], FLOOR['temp']), runs=3 if N == 10 else 1), rows=int(len(big)))
        del big
        for nat in (False, True):
            def syn():
                X = T.filter("buoy = 'WE2'").select('time', 'temp', 'f_dead').crossJoin(spark.range(N).withColumnRenamed('id', 'rep')).withColumn('buoy', F.concat(F.lit('WE2_'), F.col('rep').cast('string'))).drop('rep')
                return hampel(X, ['temp'], native=nat).agg(F.sum(F.col('f_spike_temp').cast('int'))).collect()
            add(f'SYNTHETIC x{N} Hampel temperature ({len(base) * N:,} rows)', 'spark', 'lag/lead window' if nat else 'collect_list', timeit(syn, runs=3 if N == 10 else 1, max_warm=60), rows=int(len(base) * N))
        json.dump(B, open(RES + 'spark/_bench_partial.json', 'w'))
    BD = pd.DataFrame(B); BD.to_csv(OUT + 'benchmark_spark_vs_pandas.csv', index=False); R['benchmark'] = B; R['benchmark_protocol'] = '1 untimed warm-up run, then median of 3 timed runs (1 run where the warm-up took > 60-100 s; marked by runs_s length). Same machine, same data, one core. Spark JVM start-up (not included) measured separately.'
    save(); print(BD[['job', 'engine', 'variant', 'median_s']].to_string())
