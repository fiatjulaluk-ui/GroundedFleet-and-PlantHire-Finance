# Grounded Finance Dashboard

Finance control app for Grounded Fleet & Plant Hire Finance, covering wet-hire revenue, WIP, profitability, MYOB reconciliation, BAS, PAYG withholding, payroll compliance, Fuel Tax Credits, journals and exceptions.

## Project Structure

```text
analysis/   Python analysis and compliance modules
dashboard/  Streamlit dashboard
data/       Synthetic data generator and CSV demo data
sql/        PostgreSQL schema, seed, business queries and journal SQL
tests/      Pytest tests for core finance rules
```

## Setup

```bash
python -m pip install -r requirements.txt
copy .env.example .env
```

Edit `.env` and set `DATABASE_URL` when you have PostgreSQL ready.

## Generate Synthetic Data

```bash
python data/generate_synthetic_data.py
```

This writes CSV files to `data/csv/`.

## Run The Dashboard

```bash
python -m streamlit run dashboard/app.py --server.port 8502
```

Open:

```text
http://localhost:8502
```

The dashboard currently falls back to `data/csv/` synthetic data, so it can run before PostgreSQL is wired up.

## PostgreSQL SQL Layer

Run these after creating a local database and setting permissions for `COPY` paths:

```bash
psql "$DATABASE_URL" -f sql/01_schema.sql
psql "$DATABASE_URL" -f sql/02_seed.sql
```

Business queries are in `sql/03_business_queries.sql`.
Journal pack SQL is in `sql/04_journal_pack.sql`.

## Tests

```bash
python -m pytest
```

## GitHub Notes

Commit these files and folders:

```text
analysis/
dashboard/
data/
sql/
tests/
.env.example
.gitignore
README.md
requirements.txt
```

Do not commit a real `.env` file. It may contain database passwords or other secrets.

