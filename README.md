# Lake Buoy Anomaly Detection

Code, results and figures for the poster **"A Secure Cloud-Based Framework for Smart Lake Water-Quality Monitoring and Anomaly Detection"**, LAKE 2026 (18–20 November 2026).

**Author:** Mannat Tomar, BCA (Hons.) Data Science, Minor in Cybersecurity, Chanakya University, Devanahalli, Bengaluru
**Email:** mannatt.bca23@chanakyauniversity.edu.in
**Theme:** IoT Buoys, Real-time Sensor Networks & Hydrological Monitoring

## What this project does
- Screens 330,384 readings (about 1.9 million sensor values) from four NOAA-GLERL buoys in western Lake Erie (WE2, WE4, WE8, WE13), 2015–2026.
- Uses simple, explainable tests: dead probe, Hampel spike, stuck value and a neighbour-buoy check.
- Compares our tests with the operators' own quality flags.
- Runs the same tests in Pandas and PySpark and compares the flags and the timing.
- Includes a local replay prototype and hash-based integrity checks. The secure cloud design is a design only; it is not built.

## Main findings
- 99% of flagged temperature readings come from one flat-line rule. Of the readings the operators evaluated, 17–20% were flagged in 2016–2019 and 93–100% in 2021–2026.
- A 31-day dead probe (WE2, every sensor reads 0) and a 36-day frozen phycocyanin sensor (WE8) were found by simple rules.
- In a synthetic test, the neighbour-buoy check caught 81% of +3 °C slow drifts; single-sensor tests caught 0%. The median delay was about 5 days, and +1 °C drift was caught only 14% of the time.
- Spark gave the same flags as Pandas (4 of 42,069 differ, caused by CSV number parsing at the exact threshold), but it was slower on every job on one CPU core with this small data set. For the spike test: 49 s in Spark against 0.7 s in Pandas.
- A SHA-256 manifest caught a one-character edit, and a hash-chained log caught an edited entry.

## Limits
- US lake data, not Indian. Archived replay, not a live feed.
- Flags are automatic tests, not confirmed faults. Thresholds are my own choices.
- Drift of 1–2 °C is mostly missed; the stuck test skips gaps over 20 minutes.
- Spark was timed on one CPU core of a cloud sandbox (Xeon 2.1 GHz, 4 GB RAM, PySpark 4.3.0, Pandas 3.0.6) and on a small data set. An earlier laptop run (Spark 3.5.6, older settings) was also slow: 563 s for the three detectors, start-up included.
- The cloud parts (mutual TLS, Object Lock, IAM, KMS) are a design, not built or tested.

## Folders
- `code/` Pandas and PySpark code (`spark_port.py`, `spark_reconcile.py`, `figures3.py`, `qa_numbers.py`)
- `results/` result files, CSVs and the Spark vs Pandas comparison (`results/spark/`)
- `figures/` poster figures and the QR code
- `poster/` final poster (PDF and PPTX) and the script that builds it
- `docs/` 2-minute talk script and judge questions
- `MANIFEST_SHA256.txt` SHA-256 checksum of every file

## How to run
1. Download the raw CSVs for the four buoys (WE2, WE4, WE8, WE13) from GLOS Seagull (NOAA GLERL). They are not included here.
2. Set the file paths in `code/lib.py` (`UP` and `FILES`).
3. Install: `pip install pandas numpy matplotlib pyspark python-pptx` (Java is needed for Spark).
4. Run `python spark_reconcile.py A` in `code/` for the Spark vs Pandas check, then `python spark_reconcile.py B` for the benchmark.

## Data credit
NOAA GLERL buoys, served by the Great Lakes Observing System (GLOS Seagull, glos.org/seagull). Raw data is not included in this repo.

## Licence
MIT
