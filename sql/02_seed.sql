-- Grounded Fleet & Plant Hire Finance App
-- 02_seed.sql
-- Load generated CSV data and calculate finance-control outputs.
--
-- Run with psql, for example:
-- psql "$DATABASE_URL" -f sql/01_schema.sql -f sql/02_seed.sql

\set ON_ERROR_STOP on

BEGIN;

TRUNCATE TABLE
    asset_profit,
    job_profit,
    revenue_engine,
    staging_revenue_engine,
    bas_check,
    payg_withholding,
    fuel_tax_credit,
    payroll_monthly,
    payroll_config,
    myob_gl_extract,
    invoice_myob,
    costs,
    job_rates,
    usage_log,
    job_master,
    fleet_register,
    forecast_assumptions,
    exception_log,
    rate_card
RESTART IDENTITY CASCADE;

COPY rate_card(rate_card_id, equipment_type, hourly_rate_cents, float_fee_cents, effective_from, effective_to, source_note) FROM 'C:/Users/julal/Documents/Codex/2026-05-01/you-are-helping-me-build-a/data/csv/rate_card.csv' WITH (FORMAT csv, HEADER true, NULL '');
COPY fleet_register(asset_id, equipment_type, serial_number, purchase_date, status, home_depot) FROM 'C:/Users/julal/Documents/Codex/2026-05-01/you-are-helping-me-build-a/data/csv/fleet_register.csv' WITH (FORMAT csv, HEADER true, NULL '');
COPY job_master(job_id, customer_name, site_name, site_address, start_date, end_date, duration_days, status, purchase_order) FROM 'C:/Users/julal/Documents/Codex/2026-05-01/you-are-helping-me-build-a/data/csv/job_master.csv' WITH (FORMAT csv, HEADER true, NULL '');
COPY usage_log(usage_id, job_id, asset_id, equipment_type, usage_date, site_name, hours_worked, rain_flag, float_required, operator_name) FROM 'C:/Users/julal/Documents/Codex/2026-05-01/you-are-helping-me-build-a/data/csv/usage_log.csv' WITH (FORMAT csv, HEADER true, NULL '');
COPY job_rates(job_rate_id, job_id, equipment_type, override_rate_cents, standard_rate_cents, override_reason) FROM 'C:/Users/julal/Documents/Codex/2026-05-01/you-are-helping-me-build-a/data/csv/job_rates.csv' WITH (FORMAT csv, HEADER true, NULL '');
COPY costs(cost_id, usage_id, job_id, asset_id, cost_date, cost_category, amount_cents, gst_input_cents, tax_code, bas_g11_cents, bas_1b_cents, supplier_name, withholding_cents) FROM 'C:/Users/julal/Documents/Codex/2026-05-01/you-are-helping-me-build-a/data/csv/costs.csv' WITH (FORMAT csv, HEADER true, NULL '');
COPY invoice_myob(invoice_id, myob_invoice_number, job_id, asset_id, invoice_date, amount_ex_gst_cents, gst_cents, amount_inc_gst_cents, status, tax_code) FROM 'C:/Users/julal/Documents/Codex/2026-05-01/you-are-helping-me-build-a/data/csv/invoice_myob.csv' WITH (FORMAT csv, HEADER true, NULL '');
COPY payroll_config(config_key, config_value, effective_from, note) FROM 'C:/Users/julal/Documents/Codex/2026-05-01/you-are-helping-me-build-a/data/csv/payroll_config.csv' WITH (FORMAT csv, HEADER true, NULL '');
COPY payroll_monthly(payroll_month_id, month_start, pay_group, gross_wages_cents, super_guarantee_cents, payroll_tax_cents, coinvest_cents, tax_code) FROM 'C:/Users/julal/Documents/Codex/2026-05-01/you-are-helping-me-build-a/data/csv/payroll_monthly.csv' WITH (FORMAT csv, HEADER true, NULL '');
COPY payg_withholding(payg_withholding_id, job_id, cost_id, supplier_name, gross_ex_gst_cents, withholding_rate, withholding_cents, liability_account, bas_field, note) FROM 'C:/Users/julal/Documents/Codex/2026-05-01/you-are-helping-me-build-a/data/csv/payg_withholding.csv' WITH (FORMAT csv, HEADER true, NULL '');
COPY fuel_tax_credit(fuel_tax_credit_id, asset_id, month_start, fuel_cost_cents, diesel_price_estimate_cents_per_litre, litres, ato_eligible_rate_cents_per_litre, fuel_tax_credit_cents, note) FROM 'C:/Users/julal/Documents/Codex/2026-05-01/you-are-helping-me-build-a/data/csv/fuel_tax_credit.csv' WITH (FORMAT csv, HEADER true, NULL '');
COPY exception_log(exception_id, exception_type, job_id, asset_id, amount_cents, message) FROM 'C:/Users/julal/Documents/Codex/2026-05-01/you-are-helping-me-build-a/data/csv/exception_log.csv' WITH (FORMAT csv, HEADER true, NULL '');
COPY staging_revenue_engine(revenue_id, usage_id, job_id, asset_id, equipment_type, usage_date, actual_hours, billable_hours, rate_used_cents, rate_source, hire_revenue_cents, float_applied_cents, total_revenue_cents, gst_output_cents, tax_code, bas_g1_cents, bas_1a_cents) FROM 'C:/Users/julal/Documents/Codex/2026-05-01/you-are-helping-me-build-a/data/csv/revenue_engine.csv' WITH (FORMAT csv, HEADER true, NULL '');

-- Revenue engine: database-owned calculation applying contract rules exactly.
INSERT INTO revenue_engine (
    revenue_id,
    usage_id,
    job_id,
    asset_id,
    equipment_type,
    usage_date,
    actual_hours,
    billable_hours,
    rate_used_cents,
    rate_source,
    hire_revenue_cents,
    float_applied_cents,
    total_revenue_cents,
    gst_output_cents,
    tax_code,
    bas_g1_cents,
    bas_1a_cents
)
WITH term_hours AS (
    SELECT
        job_id,
        asset_id,
        SUM(hours_worked) AS total_term_hours
    FROM usage_log
    GROUP BY job_id, asset_id
),
calc AS (
    SELECT
        u.usage_id,
        u.job_id,
        u.asset_id,
        u.equipment_type,
        u.usage_date,
        u.hours_worked AS actual_hours,
        CASE
            WHEN u.rain_flag THEN GREATEST(u.hours_worked, 6.0)
            ELSE GREATEST(u.hours_worked, 8.0)
        END AS billable_hours,
        COALESCE(jr.override_rate_cents, rc.hourly_rate_cents) AS rate_used_cents,
        CASE
            WHEN jr.override_rate_cents IS NOT NULL THEN 'Override'
            ELSE 'Rate card'
        END AS rate_source,
        CASE
            WHEN u.float_required AND th.total_term_hours < 16 THEN rc.float_fee_cents * 2
            WHEN u.float_required THEN rc.float_fee_cents
            ELSE 0
        END AS float_applied_cents
    FROM usage_log u
    JOIN rate_card rc
        ON rc.equipment_type = u.equipment_type
    JOIN term_hours th
        ON th.job_id = u.job_id
       AND th.asset_id = u.asset_id
    LEFT JOIN job_rates jr
        ON jr.job_id = u.job_id
       AND jr.equipment_type = u.equipment_type
)
SELECT
    'REV' || LPAD(ROW_NUMBER() OVER (ORDER BY usage_date, job_id, asset_id, usage_id)::TEXT, 5, '0') AS revenue_id,
    usage_id,
    job_id,
    asset_id,
    equipment_type,
    usage_date,
    actual_hours,
    billable_hours,
    rate_used_cents,
    rate_source,
    ROUND(billable_hours * rate_used_cents)::INTEGER AS hire_revenue_cents,
    float_applied_cents,
    (ROUND(billable_hours * rate_used_cents)::INTEGER + float_applied_cents) AS total_revenue_cents,
    ROUND((ROUND(billable_hours * rate_used_cents)::INTEGER + float_applied_cents) * 0.10)::INTEGER AS gst_output_cents,
    'GST' AS tax_code,
    (ROUND(billable_hours * rate_used_cents)::INTEGER + float_applied_cents) AS bas_g1_cents,
    ROUND((ROUND(billable_hours * rate_used_cents)::INTEGER + float_applied_cents) * 0.10)::INTEGER AS bas_1a_cents
FROM calc;

-- Forecast assumptions: one row per asset per month using the forecast formula.
INSERT INTO forecast_assumptions (
    forecast_assumption_id,
    period_start,
    asset_id,
    equipment_type,
    fleet_count,
    hours_per_day,
    working_days,
    utilisation_pct,
    rate_cents,
    forecast_revenue_cents
)
WITH months AS (
    SELECT generate_series(DATE '2026-01-01', DATE '2026-06-01', INTERVAL '1 month')::DATE AS period_start
),
working_days AS (
    SELECT
        m.period_start,
        COUNT(*)::INTEGER AS working_days
    FROM months m
    CROSS JOIN LATERAL generate_series(
        m.period_start,
        (m.period_start + INTERVAL '1 month - 1 day')::DATE,
        INTERVAL '1 day'
    ) AS day_value(work_day)
    WHERE EXTRACT(ISODOW FROM day_value.work_day) BETWEEN 1 AND 6
    GROUP BY m.period_start
)
SELECT
    'FA' || TO_CHAR(m.period_start, 'YYYYMM') || '-' || fr.asset_id AS forecast_assumption_id,
    m.period_start,
    fr.asset_id,
    fr.equipment_type,
    1 AS fleet_count,
    9.0 AS hours_per_day,
    wd.working_days,
    0.72 AS utilisation_pct,
    rc.hourly_rate_cents AS rate_cents,
    ROUND(1 * 9.0 * wd.working_days * 0.72 * rc.hourly_rate_cents)::INTEGER AS forecast_revenue_cents
FROM months m
JOIN working_days wd
    ON wd.period_start = m.period_start
CROSS JOIN fleet_register fr
JOIN rate_card rc
    ON rc.equipment_type = fr.equipment_type;

-- Seed a model-aligned MYOB GST extract so reconciliation queries have a ledger side.
INSERT INTO myob_gl_extract (
    gl_extract_id,
    period_start,
    account_code,
    account_name,
    tax_code,
    debit_cents,
    credit_cents,
    gst_cents,
    source_reference
)
WITH gst_output AS (
    SELECT
        DATE_TRUNC('month', usage_date)::DATE AS period_start,
        SUM(gst_output_cents)::INTEGER AS gst_cents
    FROM revenue_engine
    GROUP BY 1
),
gst_input AS (
    SELECT
        DATE_TRUNC('month', cost_date)::DATE AS period_start,
        SUM(gst_input_cents)::INTEGER AS gst_cents
    FROM costs
    GROUP BY 1
)
SELECT
    'GL-GSTOUT-' || TO_CHAR(period_start, 'YYYYMM') AS gl_extract_id,
    period_start,
    '2-2200' AS account_code,
    'GST Collected' AS account_name,
    'GST' AS tax_code,
    0 AS debit_cents,
    gst_cents AS credit_cents,
    gst_cents,
    'Synthetic MYOB Advanced GST output extract' AS source_reference
FROM gst_output
UNION ALL
SELECT
    'GL-GSTIN-' || TO_CHAR(period_start, 'YYYYMM') AS gl_extract_id,
    period_start,
    '2-2210' AS account_code,
    'GST Paid' AS account_name,
    'GST' AS tax_code,
    gst_cents AS debit_cents,
    0 AS credit_cents,
    -gst_cents AS gst_cents,
    'Synthetic MYOB Advanced GST input extract' AS source_reference
FROM gst_input;

-- BAS check lines. W4 is kept separate from net GST.
INSERT INTO bas_check (bas_check_id, period_start, bas_field, amount_cents, source_table, notes)
WITH months AS (
    SELECT generate_series(DATE '2026-01-01', DATE '2026-06-01', INTERVAL '1 month')::DATE AS period_start
),
bas_lines AS (
    SELECT DATE_TRUNC('month', usage_date)::DATE AS period_start, 'G1' AS bas_field, SUM(bas_g1_cents)::INTEGER AS amount_cents, 'revenue_engine' AS source_table, 'GST sales' AS notes
    FROM revenue_engine GROUP BY 1
    UNION ALL
    SELECT DATE_TRUNC('month', usage_date)::DATE, '1A', SUM(bas_1a_cents)::INTEGER, 'revenue_engine', 'GST payable on sales'
    FROM revenue_engine GROUP BY 1
    UNION ALL
    SELECT DATE_TRUNC('month', cost_date)::DATE, 'G11', SUM(bas_g11_cents)::INTEGER, 'costs', 'GST-creditable non-capital purchases'
    FROM costs GROUP BY 1
    UNION ALL
    SELECT DATE_TRUNC('month', cost_date)::DATE, '1B', SUM(bas_1b_cents)::INTEGER, 'costs', 'GST input credits'
    FROM costs GROUP BY 1
    UNION ALL
    SELECT DATE_TRUNC('month', c.cost_date)::DATE, 'W4', SUM(p.withholding_cents)::INTEGER, 'payg_withholding', 'No-ABN PAYG withholding liability, excluded from net GST'
    FROM payg_withholding p
    JOIN costs c ON c.cost_id = p.cost_id
    GROUP BY 1
    UNION ALL
    SELECT period_start, 'G2', 0, 'model', 'Export sales placeholder'
    FROM months
    UNION ALL
    SELECT period_start, 'G3', 0, 'model', 'GST-free sales placeholder'
    FROM months
    UNION ALL
    SELECT period_start, 'G10', 0, 'model', 'Capital purchases placeholder'
    FROM months
)
SELECT
    'BAS' || TO_CHAR(period_start, 'YYYYMM') || '-' || bas_field AS bas_check_id,
    period_start,
    bas_field,
    COALESCE(amount_cents, 0) AS amount_cents,
    source_table,
    notes
FROM bas_lines;

CREATE OR REPLACE VIEW wip_summary AS
WITH earned AS (
    SELECT
        job_id,
        asset_id,
        SUM(total_revenue_cents)::INTEGER AS earned_revenue_cents
    FROM revenue_engine
    GROUP BY job_id, asset_id
),
invoiced AS (
    SELECT
        job_id,
        asset_id,
        SUM(amount_ex_gst_cents)::INTEGER AS invoiced_amount_cents
    FROM invoice_myob
    GROUP BY job_id, asset_id
)
SELECT
    e.job_id,
    jm.customer_name,
    e.asset_id,
    fr.equipment_type,
    e.earned_revenue_cents,
    COALESCE(i.invoiced_amount_cents, 0) AS invoiced_amount_cents,
    (e.earned_revenue_cents - COALESCE(i.invoiced_amount_cents, 0))::INTEGER AS wip_cents
FROM earned e
JOIN job_master jm
    ON jm.job_id = e.job_id
JOIN fleet_register fr
    ON fr.asset_id = e.asset_id
LEFT JOIN invoiced i
    ON i.job_id = e.job_id
   AND i.asset_id = e.asset_id;

COMMENT ON VIEW wip_summary IS 'Job-plus-asset WIP summary calculated across all dates as earned revenue less invoiced amount.';

INSERT INTO job_profit (
    job_id,
    revenue_cents,
    fuel_direct_cents,
    labour_direct_cents,
    maintenance_cents,
    transport_cents,
    other_costs_cents,
    total_cost_cents,
    profit_cents,
    margin_pct
)
WITH revenue AS (
    SELECT job_id, SUM(total_revenue_cents)::INTEGER AS revenue_cents
    FROM revenue_engine
    GROUP BY job_id
),
cost_summary AS (
    SELECT
        job_id,
        SUM(CASE WHEN cost_category = 'Fuel' THEN amount_cents ELSE 0 END)::INTEGER AS fuel_direct_cents,
        SUM(CASE WHEN cost_category = 'Labour' THEN amount_cents ELSE 0 END)::INTEGER AS labour_direct_cents,
        SUM(CASE WHEN cost_category = 'Maintenance' THEN amount_cents ELSE 0 END)::INTEGER AS maintenance_cents,
        SUM(CASE WHEN cost_category = 'Transport/float' THEN amount_cents ELSE 0 END)::INTEGER AS transport_cents,
        SUM(CASE WHEN cost_category NOT IN ('Fuel', 'Labour', 'Maintenance', 'Transport/float') THEN amount_cents ELSE 0 END)::INTEGER AS other_costs_cents,
        SUM(amount_cents)::INTEGER AS total_cost_cents
    FROM costs
    GROUP BY job_id
)
SELECT
    jm.job_id,
    COALESCE(r.revenue_cents, 0),
    COALESCE(c.fuel_direct_cents, 0),
    COALESCE(c.labour_direct_cents, 0),
    COALESCE(c.maintenance_cents, 0),
    COALESCE(c.transport_cents, 0),
    COALESCE(c.other_costs_cents, 0),
    COALESCE(c.total_cost_cents, 0),
    COALESCE(r.revenue_cents, 0) - COALESCE(c.total_cost_cents, 0),
    CASE
        WHEN COALESCE(r.revenue_cents, 0) = 0 THEN 0
        ELSE ROUND(((COALESCE(r.revenue_cents, 0) - COALESCE(c.total_cost_cents, 0))::NUMERIC / r.revenue_cents) * 100, 4)
    END
FROM job_master jm
LEFT JOIN revenue r ON r.job_id = jm.job_id
LEFT JOIN cost_summary c ON c.job_id = jm.job_id;

INSERT INTO asset_profit (
    asset_id,
    revenue_cents,
    fuel_direct_cents,
    labour_direct_cents,
    maintenance_cents,
    transport_cents,
    other_costs_cents,
    total_cost_cents,
    profit_cents,
    margin_pct
)
WITH revenue AS (
    SELECT asset_id, SUM(total_revenue_cents)::INTEGER AS revenue_cents
    FROM revenue_engine
    GROUP BY asset_id
),
cost_summary AS (
    SELECT
        asset_id,
        SUM(CASE WHEN cost_category = 'Fuel' THEN amount_cents ELSE 0 END)::INTEGER AS fuel_direct_cents,
        SUM(CASE WHEN cost_category = 'Labour' THEN amount_cents ELSE 0 END)::INTEGER AS labour_direct_cents,
        SUM(CASE WHEN cost_category = 'Maintenance' THEN amount_cents ELSE 0 END)::INTEGER AS maintenance_cents,
        SUM(CASE WHEN cost_category = 'Transport/float' THEN amount_cents ELSE 0 END)::INTEGER AS transport_cents,
        SUM(CASE WHEN cost_category NOT IN ('Fuel', 'Labour', 'Maintenance', 'Transport/float') THEN amount_cents ELSE 0 END)::INTEGER AS other_costs_cents,
        SUM(amount_cents)::INTEGER AS total_cost_cents
    FROM costs
    WHERE asset_id IS NOT NULL
    GROUP BY asset_id
)
SELECT
    fr.asset_id,
    COALESCE(r.revenue_cents, 0),
    COALESCE(c.fuel_direct_cents, 0),
    COALESCE(c.labour_direct_cents, 0),
    COALESCE(c.maintenance_cents, 0),
    COALESCE(c.transport_cents, 0),
    COALESCE(c.other_costs_cents, 0),
    COALESCE(c.total_cost_cents, 0),
    COALESCE(r.revenue_cents, 0) - COALESCE(c.total_cost_cents, 0),
    CASE
        WHEN COALESCE(r.revenue_cents, 0) = 0 THEN 0
        ELSE ROUND(((COALESCE(r.revenue_cents, 0) - COALESCE(c.total_cost_cents, 0))::NUMERIC / r.revenue_cents) * 100, 4)
    END
FROM fleet_register fr
LEFT JOIN revenue r ON r.asset_id = fr.asset_id
LEFT JOIN cost_summary c ON c.asset_id = fr.asset_id;

COMMIT;

SELECT 'seed_complete' AS status;
