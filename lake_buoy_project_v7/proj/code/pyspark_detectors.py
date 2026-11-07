"""PySpark port of the Pandas cleaning/tidying and detectors (dead probe, Hampel spike, stuck, neighbour check).
Same rules and thresholds as lib.py / ours.py / analysis2.py. Row-order rules use Spark window functions."""
from functools import reduce
from pyspark.sql import SparkSession, Window, functions as F
from lib import UP, FILES, SENS, TESTS, SENSORS
from ours import FLOOR, K, STUCK_N

BUOYS = list(FILES)


def get_spark(cores=1, mem='2g', name='lake'):
    return (SparkSession.builder.master(f'local[{cores}]').appName(name)
            .config('spark.driver.memory', mem).config('spark.ui.enabled', 'false')
            .config('spark.sql.shuffle.partitions', '4').config('spark.sql.session.timeZone', 'UTC')
            .config('spark.sql.ansi.enabled', 'false').getOrCreate())


def _num(c):
    x = F.col(c).cast('double')                      # ERDDAP writes missing as 'NaN' -> null (as pandas NaN)
    return F.when(F.isnan(x), F.lit(None)).otherwise(x)


def read_raw(spark, buoy):
    df = spark.read.csv(UP + FILES[buoy], header=True, inferSchema=False).filter(F.col('time') != 'UTC')  # drop units row
    cols = [c for c in df.columns if c != 'time']
    return df.select(F.to_timestamp('time').alias('time'), *[_num(c).alias(c) for c in cols])


def tidy(raw, buoy):
    """-999 -> null (kept as sent_*), K -> degC, phycocyanin + blue-green-algae columns merged."""
    have = set(raw.columns)
    out = {'time': F.col('time'), 'buoy': F.lit(buoy), 'batt': F.col('battery_voltage')}
    for s, col in SENS.items():
        if col not in have:
            continue
        v = F.col(col)
        out['sent_' + s] = (v == -999)
        out[s] = F.when(v == -999, F.lit(None)).otherwise(v)
        for t, tn in TESTS.items():
            out[f'{s}_{t}'] = F.col(f'{col}_{tn}')
    if 'bga' in out:
        use_b = out['phyco'].isNull() & out['bga'].isNotNull()
        for t in [''] + ['_' + k for k in TESTS]:
            out['phyco' + t] = F.when(use_b, out['bga' + t]).otherwise(out['phyco' + t])
        for k in [k for k in out if k.startswith('bga') or k == 'sent_bga']:
            del out[k]
    out['temp'] = out['temp'] - 273.15
    return raw.select(*[v.alias(k) for k, v in out.items()]).withColumn('year', F.year('time'))


def load_all(spark):
    return reduce(lambda a, b: a.unionByName(b, allowMissingColumns=True), [tidy(read_raw(spark, b), b) for b in BUOYS])


def dead_probe(df):
    n0 = sum(F.coalesce((F.col(c) == 0).cast('int'), F.lit(0)) for c in ['do', 'chl', 'phyco', 'turb'])
    n0 = n0 + F.coalesce((F.col('temp') <= 0.05).cast('int'), F.lit(0))
    return df.withColumn('f_dead', n0 >= 4)


def _w():
    return Window.partitionBy('buoy').orderBy('time')


def hampel(df, s, k=K):
    """9-reading centred median (>=5 values), robust scale (MAD), flag |x-median| > max(k*sigma, floor); 4 neighbours each side within 150 min."""
    w, w9 = _w(), _w().rowsBetween(-4, 4)
    med = F.when(F.count(s).over(w9) >= 5, F.median(s).over(w9))
    span = (F.unix_timestamp(F.lead('time', 4).over(w)) - F.unix_timestamp(F.lag('time', 4).over(w))) / 60.0
    d = df.withColumn('_r', F.col(s) - med).withColumn('_ok', span <= 150)
    use = d.filter(F.col('_ok') & F.col('_r').isNotNull())
    m1 = use.groupBy('buoy').agg(F.median('_r').alias('_m'))
    sg = use.join(m1, 'buoy').groupBy('buoy').agg((1.4826 * F.median(F.abs(F.col('_r') - F.col('_m')))).alias('_sig'))
    d = d.join(F.broadcast(sg), 'buoy', 'left')
    thr = F.greatest(k * F.col('_sig'), F.lit(FLOOR[s]))
    flag = F.coalesce((F.abs(F.col('_r')) > thr) & F.col('_ok'), F.lit(False))
    return d.withColumn(f'f_spike_{s}', flag & ~F.col('f_dead')).drop('_r', '_ok', '_sig')


def stuck(df, s, n=STUCK_N):
    """>= n identical non-zero readings in a row, each <= 20 min after the last; the run's first value is flagged too."""
    w = _w()
    dt = (F.unix_timestamp('time') - F.unix_timestamp(F.lag('time', 1).over(w))) / 60.0
    same = F.coalesce((F.col(s) == F.lag(s, 1).over(w)) & (dt <= 20.0) & (F.col(s) != 0) & F.col(s).isNotNull(), F.lit(False))
    d = df.withColumn('_same', same)
    d = d.withColumn('_g', F.sum(F.when(~F.col('_same'), 1).otherwise(0)).over(w.rowsBetween(Window.unboundedPreceding, 0)))
    rl = F.sum(F.col('_same').cast('int')).over(Window.partitionBy('buoy', '_g'))
    d = d.withColumn('_f', F.col('_same') & (rl >= n))
    d = d.withColumn(f'f_stuck_{s}', F.col('_f') | F.coalesce(F.lead('_f', 1).over(w), F.lit(False)))
    return d.drop('_same', '_g', '_f')


def neighbour_temp(df):
    """Temperature vs median of the other buoys on a shared 15-min grid; 24-slot rolling median; flag |roll| > max(5*sigma, 1 C)."""
    slot = F.timestamp_seconds(F.round(F.unix_timestamp('time') / 900.0) * 900)
    g = df.select('buoy', 'time', slot.alias('slot'), F.when(F.col('f_dead'), F.lit(None)).otherwise(F.col('temp')).alias('tm'))
    g = g.withColumn('_rn', F.row_number().over(Window.partitionBy('buoy', 'slot').orderBy('time'))).filter('_rn = 1')
    wide = g.groupBy('slot').pivot('buoy', BUOYS).agg(F.first('tm'))
    wg = Window.orderBy('slot').rowsBetween(-23, 0)
    for b in BUOYS:
        arr = F.array_sort(F.filter(F.array(*[F.col(o) for o in BUOYS if o != b]), lambda x: x.isNotNull()))
        n = F.size(arr)
        ref = F.when(n == 3, arr[1]).when(n == 2, (arr[0] + arr[1]) / 2.0)
        wide = wide.withColumn(f'_res_{b}', F.col(b) - ref)
        wide = wide.withColumn(f'_roll_{b}', F.when(F.count(f'_res_{b}').over(wg) >= 12, F.median(f'_res_{b}').over(wg)))
    wide = wide.select('slot', *[f'_roll_{b}' for b in BUOYS]).cache()
    thr, sig = {}, {}
    for b in BUOYS:
        r = wide.select(F.col(f'_roll_{b}').alias('v')).filter(F.col('v').isNotNull())
        m = r.agg(F.median('v')).first()[0]
        sig[b] = 1.4826 * r.agg(F.median(F.abs(F.col('v') - F.lit(m)))).first()[0]
        thr[b] = max(5 * sig[b], 1.0)
    j = df.withColumn('slot', slot).join(F.broadcast(wide), 'slot', 'left')
    nb = F.create_map(*[x for b in BUOYS for x in (F.lit(b), F.col(f'_roll_{b}'))])[F.col('buoy')]
    tm = F.create_map(*[x for b in BUOYS for x in (F.lit(b), F.lit(thr[b]))])[F.col('buoy')]
    j = j.withColumn('nb_roll_temp', nb).withColumn('f_neigh_temp', F.coalesce(F.abs(nb) > tm, F.lit(False)) & ~F.col('f_dead'))
    return j.drop('slot', *[f'_roll_{b}' for b in BUOYS]), {b: dict(sigma=sig[b], thr=thr[b]) for b in BUOYS}


def detect(df, sensors=SENSORS, neighbour=True):
    df = dead_probe(df)
    for s in sensors:
        df = stuck(hampel(df, s), s)
    meta = {}
    if neighbour:
        df, meta = neighbour_temp(df)
    return df, meta
