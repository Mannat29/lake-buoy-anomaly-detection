# Lake Buoy Anomaly Detection

Code, results and figures for the poster **"A Secure Cloud-Based Framework for Smart Lake Water-Quality Monitoring and Anomaly Detection"**, LAKE 2026 (Mannat Tomar, Chanakya University, Bengaluru).

## What this project does
- Screens 330,384 readings from four NOAA-GLERL buoys in western Lake Erie (WE2, WE4, WE8, WE13), 2015–2026.
- Uses simple, explainable tests: dead probe, Hampel spike, stuck value and a neighbour-buoy check.
- Compares our tests with the operators' own quality flags.
- Runs the same tests in Pandas and PySpark and compares the flags and timing.
- Includes a local replay prototype and hash-based integrity checks. The cloud design is a design only; it is not built.

## Main findings
- 99% of flagged temperature readings come from one flat-line rule.
- A 31-day dead probe (WE2) and a 36-day frozen sensor (WE8) were found.
- The neighbour check caught 81% of +3 °C synthetic drifts; single-sensor tests caught 0%.
- Spark gave the same flags as Pandas (4 of 42,069 differ) but was slower on one CPU core with this small data set.

## Limits
US lake data, not Indian. Archived replay, not a live feed. Flags are automatic tests, not confirmed faults. Thresholds are my own choices. Drift of 1–2 °C is mostly missed.

## Folders
- `code/` Pandas and PySpark code (`spark_reconcile.py`, `spark_port.py`, `figures3.py`)
- `results/` result files and CSVs
- `figures/` poster figures
- `poster/` poster PDF and PPTX

## How to run
1. Download the raw CSVs from GLOS Seagull (NOAA GLERL buoys) and set the paths in `code/lib.py`.
2. `pip install pandas numpy matplotlib pyspark` (Java is needed for Spark).
3. `python code/spark_reconcile.py A` for the Spark vs Pandas check, then `B` for the benchmark.

## Data credit
NOAA GLERL buoys, served by the Great Lakes Observing System (GLOS Seagull, glos.org/seagull). Raw data is not included here.

## Licence
MIT
