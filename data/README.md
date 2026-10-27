# Data

Every source used by the project is listed here with its licence and how it was obtained.
`data/raw/` is gitignored; `data/processed/` holds derived files that are safe to commit.

| Source | What | How obtained | Licence / terms | Logged in |
|---|---|---|---|---|
| SEC EDGAR | 10-K, 10-Q, S-K 1300 technical report summaries (Exhibit 96) | Official API, descriptive User-Agent, within SEC rate limits | Public | — |
| SEDAR+ | NI 43-101 technical reports, filings | Manual download into `data/raw/`, no scraping | — | — |
| Prices | LME / COMEX settlement or delayed | Not chosen yet | To record before use | — |
