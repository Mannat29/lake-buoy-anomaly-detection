# LAKE 2026 poster: 2-minute script and judge questions
Mannat Tomar, Chanakya University. All numbers are from results/ (see results/poster_number_check.json).

## 2-minute script (about 290 words)
Hello, I am Mannat Tomar, a Data Science student with a minor in Cybersecurity at Chanakya University.

Lake buoys send water-quality readings every 15 minutes. But sensors can fail, freeze, drift or be tampered with. So can we trust the data? I looked at 330,384 readings from four NOAA-GLERL buoys in western Lake Erie, from 2015 to 2026.

First, the operators' own quality flags are not a fault list. One flat-line rule causes 99% of the flagged temperature readings. Of the temperature readings the operators evaluated, 93 to 100% are flagged from 2021 on, but only 17 to 20% in 2016 to 2019.

Second, simple, explainable tests find real faults. At buoy WE2, every sensor read zero for 31 days in autumn 2015. At WE8, the phycocyanin sensor was frozen at 2.31 for 36 days.

Third, slow drift is hard for one sensor alone. In a synthetic test, a plus 3 degree drift was caught 81% of the time by comparing neighbouring buoys, and 0% by single-sensor tests. But it is caught late, after about 5 days, and drift of 1 to 2 degrees is mostly missed.

Fourth, I ported the tests to PySpark. Spark gives the same flags as Pandas: 4 of 42,069 flags differ, and those come from how the CSV numbers are read. But on one CPU core and this small data set, Spark was slower: 49 seconds against 0.7 seconds for the spike test.

For security, the local replay and hash checks worked: a one-character edit was caught. The cloud design, with mutual TLS, immutable storage and encryption, is a design only. It is not built.

This is US archived data, not a live feed. Next, I want to ask NOAA and GLOS why flags stop, and test Spark on much larger data. Thank you.

## 8 likely judge questions
1. **Why US data, not Indian lakes?** Open, long, multi-sensor buoy data with quality flags is available for Lake Erie; I did not find comparable open Indian data. The method is simple and could be tried on Indian data, but I have not tested that.
2. **Why was Spark slower?** One CPU core and only 330,384 rows: Spark pays for start-up, task scheduling and sorting for window functions, while Pandas runs one optimised loop. I tried 8 shuffle partitions, Parquet and lag/lead windows; none helped. I did not measure where Spark would win.
3. **Are the flags the truth?** No. Operator flags are automatic tests, and mine are tests too. Both give candidates for faults. Only the operators can confirm a fault.
4. **Is it real-time?** No. It is a replay of archived data. The WE2 2018 replay ran 124 daily batches at a median 22 ms each, with alerts identical to the batch run. That shows the logic can work in batches, not that a live system exists.
5. **Is the cloud part built?** No. Mutual TLS, Object Lock, IAM and KMS are a design (amber on the poster). What I tested locally: SHA-256 manifests and a hash-chained log.
6. **What are the limits for drift?** +3 °C drift: 81% caught, median delay about 5 days; +1 °C: only 14%. Tests used synthetic drift on a copy, and thresholds were chosen by me.
7. **How does this help security?** Flat-line, spike and neighbour checks flag odd data, which can be a fault or tampering. Hashes show silent edits to stored data. Spoofing and eavesdropping defences are not tested.
8. **What next?** Ask NOAA and GLOS why flags stop after 2019; confirm candidates with the operators; test Spark on much larger data or more cores; build a small cloud sandbox.
