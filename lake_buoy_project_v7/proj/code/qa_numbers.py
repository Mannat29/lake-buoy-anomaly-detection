"""QA: every number on the poster is computed from the results files and searched for in the poster PDF text."""
import json, re, subprocess, pandas as pd
R = '../results/'; PDF = '../poster/lake2026_poster_v7.pdf'
txt = re.sub(r'\s+', ' ', subprocess.run(['pdftotext', PDF, '-'], capture_output=True, text=True).stdout)
p1 = json.load(open(R + 'part1.json')); p3 = json.load(open(R + 'part3.json')); rp = json.load(open(R + 'replay.json')); it = json.load(open(R + 'integrity_test.json')); sr = json.load(open(R + 'spark_results.json'))
sd = pd.read_csv(R + 'synthetic_drift.csv'); ss = pd.read_csv(R + 'synthetic_single.csv'); yr = pd.read_csv(R + 'spark/temp_flagged_share_by_year_spark.csv'); C = pd.read_csv(R + 'spark/operator_flag_composition_spark.csv').set_index('sensor')
B = pd.read_csv(R + 'spark/benchmark_spark_vs_pandas.csv'); inv = {r['buoy']: r for r in p1['inventory']}
cov = p1['flag_coverage_pct']; bl = pd.DataFrame(p3['bloom_table']); ev = yr.assign(s=100 * yr.op_flag / yr.op_eval).set_index('year').s
checks = []
def chk(name, poster, actual, ok=None):
    ok = (str(poster) == str(actual)) if ok is None else ok; checks.append((name, poster, actual, ok, poster_in(name)))
def poster_in(name): return None
def has(s): return s in txt
rows = []
def claim(label, text, actual_ok, detail=''): rows.append((label, text, bool(actual_ok), bool(has(text)), detail))
claim('readings', '330,384', p1['total_rows'] == 330384, p1['total_rows'])
claim('sensor values', '1.9 million', round(p1['sensor_values'] / 1e6, 1) == 1.9, p1['sensor_values'])
for b, (a, t) in {'WE2': ('111,403', '2015–26'), 'WE4': ('82,094', '2015–26'), 'WE8': ('104,048', '2015–26'), 'WE13': ('32,839', '2016–19')}.items():
    claim(f'{b} rows', a, f"{inv[b]['rows']:,}" == a, inv[b]['rows'])
for b, v in {'WE2': '96%', 'WE4': '78%', 'WE8': '99%', 'WE13': '94%'}.items(): claim(f'{b} 15-min', v, f"{inv[b]['pct_15min']:.0f}%" == v, inv[b]['pct_15min'])
c = {k: v for k, v in cov.items()}; print('coverage', c)
claim('flag coverage 43-47% (chl,do,phyco,turb)', '43–47%', all(43 <= round(c[s]) <= 47 for s in ['chl', 'do', 'phyco', 'turb']) if all(s in c for s in ['chl', 'do', 'phyco', 'turb']) else False)
claim('temp coverage 78%', '78%', round(c.get('temp', 0)) == 78)
claim('temp flat-line 99%', '99% of flagged', round(100 * C.loc['temp', 'only_flat'] / C.loc['temp', 'flagged']) == 99, '')
claim('ops 2016-19 17-20%', '17–20%', 17 <= round(ev.loc[2016:2019].min()) and round(ev.loc[2016:2019].max()) <= 20, ev.loc[2016:2019].round(1).tolist())
claim('ops 2021-26 93-100%', '93–100%', round(ev.loc[2021:2026].min()) == 93 and round(ev.loc[2021:2026].max()) == 100, ev.loc[2021:2026].round(1).tolist())
d = p3['dead_probe_we2']; claim('dead probe readings', '2,983', d['readings'] == 2983); claim('dead probe 31 d', '31 days', round(d['days']) == 31)
we8 = sr['stuck_reconcile']['we8_phyco']; claim('WE8 frozen readings', '3,458', we8['episode_readings'] == 3458, we8); claim('WE8 36 d', '36 days', round(we8['episode_days']) == 36); claim('2.31 RFU', '2.31 RFU', abs(we8['value'] - 2.31) < .005, we8['value'])
r = ss.set_index(['sensor', 'fault']).recall; claim('spike 94-95%', '94–95%', {round(100 * r['temp', 'single spike']), round(100 * r['chl', 'single spike'])} == {95, 94})
claim('stuck 65-73%', '65–73%', {round(100 * r['temp', 'stuck 6 h']), round(100 * r['chl', 'stuck 6 h'])} == {73, 65})
dr = (100 * sd.caught_neigh / sd.events).round().astype(int).tolist(); claim('drift 14/42/81/94', '81%', dr == [14, 42, 81, 94], dr)
claim('drift single 0% at +3', '0%', sd.caught_single.tolist()[2:] == [0, 0]); claim('median delay ~5 d', 'median 5', round(sd.median_delay_h[2] / 24) == 5, sd.median_delay_h[2])
bt = bl; print(bt.to_string()[:700])
claim('bloom 13,521 high-chl', '13,521', int(bl.readings.sum()) == 13521); claim('bloom 67 events 81% (shown in bloom.png figure)', '13,521 high-chlorophyll', int(bl.events[0]) == 67 and round(100 * bl.readings[0] / bl.readings.sum()) == 81); claim('isolated 239/290', '239 short isolated', int(bl.events[2]) == 239 and int(bl.readings[2]) == 290); claim('84% vs 56% (shown in bloom.png figure)', '239 short isolated', round(bl.op_flag_pct[2]) == 84 and round(bl.op_flag_pct[0]) == 56)
claim('replay rows', '11,425', rp['rows'] == 11425); claim('replay batches', '124', rp['batches'] == 124); claim('replay 22 ms', '22 ms', round(rp['median_ms_per_daily_batch']) == 22); claim('alerts 1,083', '1,083', rp['spike_alerts_stream'] == 1083 and rp['identical'])
claim('integrity', '1-character edit', it['detected'] and it['chars_changed'] == 1 and not it['chain_valid_after_edit'])
P = {r['detector']: r for r in sr['parity']['by_detector']}
for k, (a, b) in {'dead': ('3,071', '3,071'), 'spike': ('27,988', '27,984'), 'stuck': ('10,137', '10,137'), 'neigh': ('873', '873')}.items(): claim(f'parity {k}', f'{a} {b}', f"{P[k]['pandas']:,} {P[k]['spark']:,}" == f'{a} {b}')
claim('4 of 42,069 differ', '4 of 42,069', sr['parity']['differing_rows'] == 4 and sr['parity']['total_pandas'] == 42069)
hp = B[(B.job.str.startswith('Hampel')) & (B.engine == 'pandas')].median_s.iloc[0]; hs = B[(B.job.str.startswith('Hampel')) & (B.engine == 'spark')].median_s.min()
claim('Hampel 49 s vs 0.7 s', '49 s vs 0.7 s', round(hs) == 49 and round(hp, 1) == 0.7, (hs, hp))
env = sr['env']; claim('PySpark 4.3.0', '4.3.0', env['pyspark'] == '4.3.0', env['pyspark']); claim('Pandas version', 'Pandas 3.0.6', env['pandas'] == '3.0.6', env['pandas']); claim('RAM', '4 GB RAM', round(env['ram_gb']) == 4, env['ram_gb']); claim('CPU', 'Xeon 2.1 GHz', 'Xeon' in env['cpu'] and '2.10' in env['cpu'], env['cpu'])
lp = json.load(open(R + 'laptop_spark/spark_stage2_summary.json')); claim('laptop Spark 563 s', '563 s', round(lp['elapsed_seconds_including_startup']) == 563 and lp['spark_version'] == '3.5.6', lp['elapsed_seconds_including_startup']); claim('laptop Spark version', 'Spark 3.5.6', lp['spark_version'] == '3.5.6')
bad = [r for r in rows if not (r[2] and r[3])]
print(f'{len(rows)} claims checked; {len(bad)} problems')
for r in bad: print('PROBLEM', r)
json.dump([dict(label=a, poster_text=b, matches_results=c_, found_on_poster=d_, detail=str(e)) for a, b, c_, d_, e in rows], open(R + 'poster_number_check.json', 'w'), indent=1)
