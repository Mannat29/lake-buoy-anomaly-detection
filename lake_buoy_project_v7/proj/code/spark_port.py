"""PySpark port of the Pandas pipeline: ingest, tidy, dead probe, Hampel spike, stuck, neighbour check.
Same rules and thresholds as analysis2.py / ours.py. No ties in time stamps, so window order is exact."""
import os
from pyspark.sql import SparkSession, Window, functions as F
from lib import UP, FILES, SENS, SENSORS, TESTS
from ours import FLOOR, K, STUCK_N, WIN

BUOYS = list(FILES)


def get_spark(cores=1, mem='2g'):
    return (SparkSession.builder.master(f'local[{cores}]').appName('lake_buoy')
            .config('spark.driver.memory', mem).config('spark.sql.shuffle.partitions', '4')
            .config('spark.sql.session.timeZone', 'UTC').config('spark.ui.enabled', 'false')
            .config('spark.sql.ansi.enabled', 'false').getOrCreate())


def ingest(spark, buoy):
    """Read CSV as strings, drop the units row (row 2), keep needed columns only."""
    raw = spark.read.csv(UP + FILES[buoy], header=True, inferSchema=False)
    raw = raw.filter(F.col('time') != 'UTC')
    return raw


def tidy(raw, buoy):
    """-999 -> null, K -> degC, merge phycocyanin + blue-green-algae RFU (values and operator flags), UTC time."""
    cols = set(raw.columns); bga = SENS['bga'] in cols
    sel = [F.lit(buoy).alias('buoy'), F.to_timestamp('time', "yyyy-MM-dd'T'HH:mm:ssX").alias('time')]
    for s in SENSORS:
        c = SENS[s]
        if c not in cols:
            sel += [F.lit(None).cast('double').alias(s), F.lit(False).alias('sent_' + s)]
            sel += [F.lit(None).cast('int').alias(f'{s}_{t}') for t in TESTS]; continue
        v = F.col(c).cast('double'); vv = F.when(F.isnan(v) | (v == -999), None).otherwise(v)
        use_b = None
        if s == 'phyco' and bga:
            b_ = F.col(SENS['bga']).cast('double'); bb = F.when(F.isnan(b_) | (b_ == -999), None).otherwise(b_)
            use_b = vv.isNull() & bb.isNotNull(); vv = F.coalesce(vv, bb)
        sel += [vv.alias(s), (v == -999).alias('sent_' + s)]
        for t, tn in TESTS.items():
            fv = F.col(f'{c}_{tn}').cast('int')
            if use_b is not None:
                fv = F.when(use_b, F.col(f'{SENS["bga"]}_{tn}').cast('int')).otherwise(fv)
            sel.append(fv.alias(f'{s}_{t}'))
    df = raw.select(sel)
    return df.withColumn('temp', F.col('temp') - 273.15).withColumn('year', F.year('time'))


def median_arr(arr):
    """Median of a non-null array (average of two middle values if even), as in Pandas."""
    a = F.array_sort(F.filter(arr, lambda x: x.isNotNull()))
    n = F.size(a)
    return F.when(n == 0, F.lit(None)).when(n % 2 == 1, F.element_at(a, (n / 2).cast('int') + 1)).otherwise(
        (F.element_at(a, (n / 2).cast('int')) + F.element_at(a, (n / 2).cast('int') + 1)) / 2)


def dead_probe(df):
    w = Window.partitionBy('buoy').orderBy('time')
    z = sum(F.coalesce((F.col(c) == 0).cast('int'), F.lit(0)) for c in ['do', 'chl', 'phyco', 'turb'])
    z = z + F.coalesce((F.col('temp') <= 0.05).cast('int'), F.lit(0))
    return df.withColumn('f_dead', z >= 4)


def hampel(df, sensors=SENSORS, native=False):
    """Adds f_spike_<s>. 9-reading centred median (min 5), 6 x robust sigma, sensor floor, span <= 150 min.
    native=True builds the window from lag()/lead() columns instead of collect_list()."""
    w = Window.partitionBy('buoy').orderBy('time'); wm = w.rowsBetween(-(WIN // 2), WIN // 2)
    df = df.withColumn('_ok', (F.unix_timestamp(F.lead('time', 4).over(w)) - F.unix_timestamp(F.lag('time', 4).over(w))) / 60 <= 150)
    for s in sensors:
        if native:
            arr = F.array(*[F.lag(s, k).over(w) for k in (4, 3, 2, 1)], F.col(s), *[F.lead(s, k).over(w) for k in (1, 2, 3, 4)])
            nn = F.filter(arr, lambda v: v.isNotNull())
        else:
            nn = F.filter(F.collect_list(F.col(s)).over(wm), lambda v: v.isNotNull())
        df = df.withColumn(f'_r_{s}', F.col(s) - F.when(F.size(nn) >= 5, median_arr(nn)))
    m = df.groupBy('buoy').agg(*[F.percentile(F.when(F.col('_ok'), F.col(f'_r_{s}')), F.lit(0.5)).alias(f'_m_{s}') for s in sensors])
    df = df.join(F.broadcast(m), 'buoy')
    g = df.groupBy('buoy').agg(*[F.percentile(F.when(F.col('_ok'), F.abs(F.col(f'_r_{s}') - F.col(f'_m_{s}'))), F.lit(0.5)).alias(f'sigma_{s}') for s in sensors])
    df = df.join(F.broadcast(g), 'buoy')
    for s in sensors:
        df = df.withColumn(f'sigma_{s}', F.lit(1.4826) * F.col(f'sigma_{s}'))
        df = df.withColumn(f'thr_{s}', F.greatest(F.lit(K) * F.col(f'sigma_{s}'), F.lit(FLOOR[s])))
        df = df.withColumn(f'f_spike_{s}', (F.abs(F.col(f'_r_{s}')) > F.col(f'thr_{s}')) & F.col('_ok') & ~F.col('f_dead'))
    return df.drop(*[c for c in df.columns if c.startswith('_')])


def stuck(df, sensors=SENSORS):
    """Adds f_stuck_<s>: >= 24 identical non-zero consecutive readings, steps <= 20 min, plus the first value of the run."""
    w = Window.partitionBy('buoy').orderBy('time'); wu = w.rowsBetween(Window.unboundedPreceding, Window.currentRow)
    df = df.withColumn('_dt', (F.unix_timestamp('time') - F.unix_timestamp(F.lag('time').over(w))) / 60)
    for s in sensors:
        same = F.coalesce(((F.col(s) - F.lag(s).over(w)) == 0) & (F.col('_dt') <= 20) & (F.col(s) != 0), F.lit(False))
        df = df.withColumn('_same', same).withColumn('_grp', F.sum((~F.col('_same')).cast('int')).over(wu))
        rl = F.when(F.col('_same'), F.count(F.when(F.col('_same'), 1)).over(Window.partitionBy('buoy', '_grp'))).otherwise(0)
        df = df.withColumn('_f', rl >= STUCK_N)
        df = df.withColumn(f'f_stuck_{s}', F.col('_f') | F.coalesce(F.lead('_f').over(w), F.lit(False)))
    return df.drop(*[c for c in df.columns if c.startswith('_')])


def neighbour_check(df):
    """Temperature: median of the other buoys on a 15-min grid, 24-row rolling median of the residual, 5 robust sigma (>= 1 C)."""
    g = df.withColumn('t15', (F.floor(F.unix_timestamp('time') / 900 + 0.5) * 900).cast('long'))
    x = g.withColumn('tx', F.when(F.col('f_dead'), None).otherwise(F.col('temp')))
    # dedupe: keep the earliest reading per (buoy, 15-min slot), as Pandas does
    xs = x.select('t15', 'buoy', 'time', 'tx')
    ww = Window.partitionBy('buoy', 't15').orderBy('time')
    first = xs.withColumn('_rn', F.row_number().over(ww)).filter('_rn = 1').drop('_rn')
    W = first.groupBy('t15').pivot('buoy', BUOYS).agg(F.first('tx'))
    wr = Window.orderBy('t15').rowsBetween(-23, 0)
    outs = []
    meta = {}
    for b in BUOYS:
        others = [c for c in BUOYS if c != b]
        arr = F.array(*[F.col(c) for c in others])
        ref = F.when(F.size(F.filter(arr, lambda v: v.isNotNull())) >= 2, median_arr(arr))
        res = F.col(b) - ref
        W = W.withColumn(f'_res_{b}', res)
    # rolling median over 24 rows of the union grid, min 12 non-null
    for b in BUOYS:
        arr = F.collect_list(F.col(f'_res_{b}')).over(wr)
        n = F.size(arr)
        W = W.withColumn(f'roll_{b}', F.when(n >= 12, median_arr(arr)))
    W = W.cache()
    rows = []
    for b in BUOYS:
        r = W.select('t15', F.col(f'roll_{b}').alias('roll')).filter('roll is not null')
        med = r.agg(F.percentile('roll', F.lit(0.5))).first()[0]
        sig = 1.4826 * r.agg(F.percentile(F.abs(F.col('roll') - F.lit(med)), F.lit(0.5))).first()[0]
        thr = max(5 * sig, 1.0)
        meta[b] = dict(sigma=sig, thr=thr)
        rows.append(W.select(F.lit(b).alias('buoy'), 't15', F.col(f'roll_{b}').alias('nb_roll_temp')))
    R = rows[0]
    for r in rows[1:]:
        R = R.unionByName(r)
    out = g.join(R, ['buoy', 't15'], 'left')
    thr_map = F.create_map(*[v for b in BUOYS for v in (F.lit(b), F.lit(meta[b]['thr']))])
    out = out.withColumn('f_neigh_temp', (F.abs(F.col('nb_roll_temp')) > thr_map[F.col('buoy')]) & ~F.col('f_dead'))
    return out.drop('t15'), meta, W


def build_tidy(spark):
    parts = [tidy(ingest(spark, b), b) for b in BUOYS]
    df = parts[0]
    for p in parts[1:]:
        df = df.unionByName(p, allowMissingColumns=True)
    return dead_probe(df)


def run_pipeline(df, native=False):
    df = stuck(hampel(df, native=native))
    df, meta, W = neighbour_check(df)
    return df, meta, W
