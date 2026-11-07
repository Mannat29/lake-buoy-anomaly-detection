"""SHA-256 manifest of the raw CSVs + hash-chained run log, with tamper tests on COPIES."""
import hashlib, json, os, shutil, time
from lib import FILES, UP
def sha(path):
    h = hashlib.sha256()
    with open(path, 'rb') as f:
        for c in iter(lambda: f.read(1 << 20), b''): h.update(c)
    return h.hexdigest()
man = {b: dict(file=f, bytes=os.path.getsize(UP + f), sha256=sha(UP + f)) for b, f in FILES.items()}
json.dump(man, open('../data_manifest/manifest.json', 'w'), indent=1)
# tamper test: flip one character in a copy of the smallest file
src = UP + FILES['WE13']; cp = '/tmp/we13_copy.csv'; shutil.copy(src, cp)
raw = bytearray(open(cp, 'rb').read()); i = raw.index(b'\n', 5000) + 40
orig = raw[i]; raw[i] = ord('7') if raw[i] != ord('7') else ord('8'); open(cp, 'wb').write(raw)
t = dict(orig_sha=man['WE13']['sha256'][:16], tampered_sha=sha(cp)[:16], detected=sha(cp) != man['WE13']['sha256'], chars_changed=1)
# hash-chained log
def entry(prev, msg): 
    e = dict(ts=time.strftime('%Y-%m-%dT%H:%M:%S'), msg=msg, prev=prev); e['hash'] = hashlib.sha256(json.dumps({k: e[k] for k in ('ts', 'msg', 'prev')}, sort_keys=True).encode()).hexdigest(); return e
def verify(chain):
    prev = '0' * 64
    for e in chain:
        h = hashlib.sha256(json.dumps({k: e[k] for k in ('ts', 'msg', 'prev')}, sort_keys=True).encode()).hexdigest()
        if e['prev'] != prev or e['hash'] != h: return False
        prev = e['hash']
    return True
chain = []; prev = '0' * 64
for m in ['ingest 4 CSVs', 'validate schema + units', 'merge phycocyanin columns', 'run detectors', 'write results']:
    e = entry(prev, m); chain.append(e); prev = e['hash']
ok_before = verify(chain); chain[2]['msg'] = 'merge phycocyanin columns (edited)'; ok_after = verify(chain)
t.update(chain_valid_before_edit=ok_before, chain_valid_after_edit=ok_after)
json.dump(t, open('../results/integrity_test.json', 'w'), indent=1); print(json.dumps(t, indent=1)); print({b: v['sha256'][:12] for b, v in man.items()})
