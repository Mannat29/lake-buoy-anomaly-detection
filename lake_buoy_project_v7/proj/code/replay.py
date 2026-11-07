"""Local prototype: replay one archived buoy season as daily micro-batches through
ingest -> validate -> store (SQLite) -> detect -> alert. This is a REPLAY of archived data, not a live feed."""
import sqlite3, time, json, os, pickle, numpy as np, pandas as pd
from lib import *
from ours import *
D = pickle.load(open('../results/D_flags.pkl', 'rb')); meta = json.load(open('../results/detector_meta.json'))
BUOY, YEAR = 'WE2', 2018
d = D[BUOY]; d = d[d.year == YEAR].reset_index(drop=True)
db = '../results/replay.sqlite'
if os.path.exists(db): os.remove(db)
con = sqlite3.connect(db)
con.execute('create table raw(time text, sensor text, value real)')
con.execute('create table alerts(time text, sensor text, kind text, value real)')
S5 = ['temp', 'chl', 'phyco', 'do', 'turb']
buf = pd.DataFrame(); done = 0; lat = []; alerts = []; stuck_seen = {s: set() for s in S5}; rejected = 0
for day, b in d.groupby(d.time.dt.date):
    t0 = time.perf_counter()
    # 1 validate: schema, strictly increasing time, drop rows with no sensors
    b = b[['time'] + S5]
    if not b.time.is_monotonic_increasing: b = b.sort_values('time')
    rejected += int(b[S5].isna().all(axis=1).sum()); b = b[~b[S5].isna().all(axis=1)]
    # 2 store
    con.executemany('insert into raw values (?,?,?)', [(str(t), s, float(v)) for s in S5 for t, v in zip(b.time, b[s]) if v == v])
    buf = pd.concat([buf, b], ignore_index=True).iloc[-600:].reset_index(drop=True) if len(buf) else b.reset_index(drop=True)
    # 3 detect: spikes need 4 readings of future context -> alert delay of 1 h; stuck alerts when the run reaches 24
    final_upto = len(buf) - 4
    for s in S5:
        thr = meta[f'{BUOY}_{s}']['thr']; sig = meta[f'{BUOY}_{s}']['sigma']
        fl, _, _ = hampel_flags(buf[s], buf.time, FLOOR[s], sigma=sig)
        for i in np.flatnonzero(fl[:max(0, final_upto)]):
            key = (str(buf.time.iloc[i]), s)
            if key not in stuck_seen.get('spk', set()):
                stuck_seen.setdefault('spk', set()).add(key); alerts.append((key[0], s, 'spike', float(buf[s].iloc[i])))
        st = stuck_flags(buf[s], buf.time)
        idx = np.flatnonzero(np.diff(np.r_[0, st.astype(int), 0]))
        for a, z in zip(idx[::2], idx[1::2]):
            k = str(buf.time.iloc[a])
            if k not in stuck_seen[s]: stuck_seen[s].add(k); alerts.append((k, s, 'stuck', float(buf[s].iloc[a])))
    lat.append((time.perf_counter() - t0) * 1000)
con.executemany('insert into alerts values (?,?,?,?)', alerts); con.commit()
# equivalence with the one-shot batch run (rows with full 9-reading window only)
batch = set()
for s in S5:
    fl = D[BUOY][f'f_spike_{s}'].to_numpy(); sub = D[BUOY].year.to_numpy() == YEAR
    ix = np.flatnonzero(fl & sub); batch |= {(str(D[BUOY].time.iloc[i]), s) for i in ix if not D[BUOY].f_dead.iloc[i]}
stream = {(t, s) for t, s, k, v in alerts if k == 'spike'}
last4 = set(str(t) for t in d.time.iloc[-4:])
res = dict(buoy=BUOY, year=YEAR, rows=len(d), batches=len(lat), median_ms_per_daily_batch=round(float(np.median(lat)), 1), max_ms=round(float(max(lat)), 1),
           spike_alerts_stream=len(stream), spike_flags_batch=len(batch), identical=len(stream ^ {k for k in batch if k[0] not in last4}) == 0,
           stuck_alerts=sum(1 for a in alerts if a[2] == 'stuck'), raw_rows_stored=con.execute('select count(*) from raw').fetchone()[0], rows_rejected=rejected,
           alert_delay_readings=4)
json.dump(res, open('../results/replay.json', 'w'), indent=1); print(json.dumps(res, indent=1))
