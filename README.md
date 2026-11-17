# OrygamiBox S.A. - Data Analytics Case Studies

Four business problems, one company. Each case starts from a question a manager would ask, works through messy data, and ends with a report, a dashboard and a recommendation.

> **Synthetic case.** OrygamiBox S.A. is a fictional manufacturer of custom folding cartons. All data was generated with AI, with deliberate errors, duplicates and missing values, so that each analysis starts from realistic, dirty data.

## The company

OrygamiBox makes printed packaging for cosmetics, food and beverage, e-commerce and technology companies. It grew fast and now struggles with plant bottlenecks, scrap that is hard to trace, and customers who want shorter lead times on tight budgets. [More about the company](docs/company_context.md).

## The four cases

| # | Case | Question | What the data showed | Tools |
|---|---|---|---|---|
| 1 | **[Scrap in the plant](case1_scrap/)** | *In which products, machines or shifts do we lose the most board, and how much does it cost?* | Scrap is 7.9% of units (about $113k of board). Short orders lose twice as much as long ones, foil and emboss add 2-5 points, one press on the night shift is 50% worse, and the flat 5% scrap allowance in quotes is $48k short. | Python, spreadsheet |
| 2 | **[Quote funnel](case2_quotes/)** | *Why do we lose quotes: price, response time or type of client?* | Win rate falls from 54% to 13% as the answer takes longer (for e-commerce, 61% to 2%). Price matters less than the team believes. | BigQuery SQL, Looker Studio |
| 3 | **[Bottlenecks and delivery](case3_delivery/)** | *At which stage do orders fall behind, and what causes it?* | 68% on time (54% in Q4). Orders wait in queues, mostly at die-cutting, not on the machines. Promised dates ignore real lead times, so small orders are on time only 30% of the time. | BigQuery SQL, Looker Studio |
| 4 | **[Profitability by client](case4_profitability/)** | *Which clients leave real margin and which cost more than they seem?* | The five large clients bring 55% of revenue but 36% of margin (8.4% against 16-22% for the rest). Costs above the quote estimate are the biggest leak ($175k). | Python, BigQuery SQL, Looker Studio |

Each case folder has a short `README.md` (problem, question, finding, recommendation) and a `report.md` with the full method, findings, estimated impact and limitations.

## Skills shown

| Skill | Where |
|---|---|
| Data cleaning and validation (duplicates, missing values, formats, units, keys), with a documented log | `pipelines/clean_data.py`, `docs/cleaning_log.csv`, all cases |
| Python and pandas pipelines | `pipelines/`, Cases 1 and 4 |
| Spreadsheet report and dashboard with formulas and charts | Case 1 |
| SQL in BigQuery: CTEs, `ROW_NUMBER`, `LAG` / `LEAD`, `RANK`, `NTILE`, running totals, percentiles, `ROLLUP` | Cases 2, 3 and 4 (`sql/`) |
| Looker Studio dashboards (layout, data sources and setup documented) | Cases 2, 3 and 4 (`looker_studio/`) |
| Descriptive statistics: mean vs median, distribution, outliers, percentiles, proportions, correlation, Pareto | All cases |
| Reasoning about causes: controlling for a second variable, correlation vs causation, estimated impact with stated assumptions | All cases |
| Business recommendations with impact and effort | All cases |

## How each case is organised

1. **Problem and question** in a manager's words.
2. **Data and cleaning:** what was wrong and what was decided, with numbers.
3. **Analysis:** simple methods, chosen to fit the question.
4. **Dashboard** with the key views.
5. **Recommendation** with estimated impact, effort and limitations.

## Repository structure

```
README.md                  this file
case1_scrap/               Python + spreadsheet
case2_quotes/              BigQuery SQL + Looker Studio
case3_delivery/            BigQuery SQL + Looker Studio
case4_profitability/       Python + BigQuery SQL + Looker Studio
pipelines/                 cleaning pipeline and shared helpers
data/raw/                  messy synthetic files
data/clean/                cleaned files
docs/                      company context, data dictionary, cleaning log
appendix/                  data generator and an optional SQL check
```

## How to reproduce

```bash
pip install -r requirements.txt
python appendix/generate_data.py            # optional: regenerate the raw data (fixed seed)
python pipelines/clean_data.py              # raw -> clean + cleaning log
python case1_scrap/analysis.py
python case1_scrap/build_dashboard.py
python case2_quotes/analysis.py
python case3_delivery/analysis.py
python case4_profitability/consolidate.py
python case4_profitability/analysis.py
python appendix/check_sql_with_duckdb.py    # optional: checks the SQL logic locally
```

The SQL files are written for BigQuery. Loading instructions are in each case's `looker_studio/SETUP.md`. The `dashboard_preview.png` files are static previews of the layout; the live dashboards are built in Looker Studio from the BigQuery views.
