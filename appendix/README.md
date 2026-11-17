# Appendix

| File | Purpose |
|---|---|
| `generate_data.py` | Generates the synthetic raw data (fixed seed, so the files are always the same) |
| `check_sql_with_duckdb.py` | Optional: runs the BigQuery SQL locally on DuckDB and compares results with the pandas numbers |

## How the data was made

The data is fictional. A small simulation of a folding-carton plant (quotes, orders, machine schedules with queues and downtime, scrap, purchases and costs) produces a consistent set of tables. Realistic data-quality problems are then added: missing values, duplicates, inconsistent labels, mixed date formats, wrong units, impossible values and orphan keys.

The generator was written with AI assistance. The case studies do not rely on knowing how it works: each analysis starts from the raw files and finds its results in the data.
