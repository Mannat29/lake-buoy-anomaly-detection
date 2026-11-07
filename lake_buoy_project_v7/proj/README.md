# LAKE 2026 poster project: IoT buoy anomaly screening (western Lake Erie)
Data: NOAA GLERL Western Erie nutrient buoys WE2/WE4/WE8/WE13 via GLOS Seagull (ERDDAP: obs_80, obs_81, obs_82, obs_215).
Run order (Python 3.12, pandas, numpy, matplotlib): tune.py, analysis1.py, analysis2.py, analysis3.py, bench.py, integrity.py, replay.py, figures2.py.
Raw CSVs are not included; set UP/FILES in code/lib.py. SHA-256 fingerprints: data_manifest/manifest.json.
Note: PySpark was not available when this was built, so every number comes from Pandas. No Spark result is claimed.

## Spark port (added)
- `code/spark_port.py`: PySpark versions of tidy, dead probe, Hampel spike, stuck and neighbour check (same rules as `ours.py`).
- `code/spark_reconcile.py` (run `A` then `B`): parity vs Pandas, stuck-run reconciliation, operator-flag checks in Spark, benchmark. Output: `results/spark_results.json`, `results/spark/*.csv`.
- `code/figures3.py` draws the final poster figures; `code/qa_numbers.py` checks poster numbers against results (`results/poster_number_check.json`).
- `poster/build_v7.py` builds `poster/lake2026_poster_v7.pptx` on the template; PDF via LibreOffice.
- Raw CSV paths are set in `code/lib.py` (UP / FILES). Raw CSVs are not in this ZIP.
