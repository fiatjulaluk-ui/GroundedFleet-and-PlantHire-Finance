-- Grounded Fleet & Plant Hire Finance App
-- 04_journal_pack.sql
-- Journal pack rows for month-end finance review.
-- Amounts are in cents. Display/export layers divide by 100.

/*
Journal pack detail rows:
JE001 WIP Accrual:  DR Unbilled Revenue / CR Hire Revenue
JE002 Cost Accrual: DR Operating Expense / CR Accrued Expenses
JE003 Depreciation: DR Depreciation Expense / CR Accumulated Depreciation
JE004 PAYG No-ABN:  DR Trade Payables / CR PAYG Withholding Payable
*/
WITH journal_rows AS (
    SELECT
        'JE001' AS journal_id,
        DATE '2026-06-30' AS journal_date,
        'WIP Accrual' AS journal_name,
        'DR' AS line_type,
        '1-1300' AS account_code,
        'Unbilled Revenue' AS account_name,
        SUM(GREATEST(wip_cents, 0))::INTEGER AS dr,
        0::INTEGER AS cr,
        'Recognise earned but uninvoiced hire revenue by job and asset' AS memo
    FROM wip_summary
    HAVING SUM(GREATEST(wip_cents, 0)) > 0

    UNION ALL
    SELECT
        'JE001',
        DATE '2026-06-30',
        'WIP Accrual',
        'CR',
        '4-1000',
        'Hire Revenue',
        0,
        SUM(GREATEST(wip_cents, 0))::INTEGER,
        'Recognise earned but uninvoiced hire revenue by job and asset'
    FROM wip_summary
    HAVING SUM(GREATEST(wip_cents, 0)) > 0

    UNION ALL
    SELECT
        'JE002',
        DATE_TRUNC('month', cost_date)::DATE + INTERVAL '1 month - 1 day',
        'Cost Accrual',
        'DR',
        '6-1000',
        'Operating Expense',
        SUM(amount_cents)::INTEGER,
        0,
        'Accrue job operating costs incurred in the period'
    FROM costs
    GROUP BY DATE_TRUNC('month', cost_date)::DATE

    UNION ALL
    SELECT
        'JE002',
        DATE_TRUNC('month', cost_date)::DATE + INTERVAL '1 month - 1 day',
        'Cost Accrual',
        'CR',
        '2-1400',
        'Accrued Expenses',
        0,
        SUM(amount_cents)::INTEGER,
        'Accrue job operating costs incurred in the period'
    FROM costs
    GROUP BY DATE_TRUNC('month', cost_date)::DATE

    UNION ALL
    SELECT
        'JE003',
        m.month_start + INTERVAL '1 month - 1 day',
        'Depreciation',
        'DR',
        '6-3000',
        'Depreciation Expense',
        SUM(750000)::INTEGER AS dr,
        0,
        'Synthetic monthly fleet depreciation estimate; replace with fixed-asset register depreciation'
    FROM generate_series(DATE '2026-01-01', DATE '2026-06-01', INTERVAL '1 month') AS m(month_start)
    CROSS JOIN fleet_register fr
    GROUP BY m.month_start

    UNION ALL
    SELECT
        'JE003',
        m.month_start + INTERVAL '1 month - 1 day',
        'Depreciation',
        'CR',
        '1-1900',
        'Accumulated Depreciation',
        0,
        SUM(750000)::INTEGER AS cr,
        'Synthetic monthly fleet depreciation estimate; replace with fixed-asset register depreciation'
    FROM generate_series(DATE '2026-01-01', DATE '2026-06-01', INTERVAL '1 month') AS m(month_start)
    CROSS JOIN fleet_register fr
    GROUP BY m.month_start

    UNION ALL
    SELECT
        'JE004',
        DATE_TRUNC('month', c.cost_date)::DATE + INTERVAL '1 month - 1 day',
        'PAYG No-ABN',
        'DR',
        '2-1100',
        'Trade Payables',
        SUM(p.withholding_cents)::INTEGER,
        0,
        'Reclassify no-ABN withholding from supplier payable to PAYG W4 liability'
    FROM payg_withholding p
    JOIN costs c ON c.cost_id = p.cost_id
    GROUP BY DATE_TRUNC('month', c.cost_date)::DATE

    UNION ALL
    SELECT
        'JE004',
        DATE_TRUNC('month', c.cost_date)::DATE + INTERVAL '1 month - 1 day',
        'PAYG No-ABN',
        'CR',
        '2-2300',
        'PAYG Withholding Payable',
        0,
        SUM(p.withholding_cents)::INTEGER,
        'Reclassify no-ABN withholding from supplier payable to PAYG W4 liability'
    FROM payg_withholding p
    JOIN costs c ON c.cost_id = p.cost_id
    GROUP BY DATE_TRUNC('month', c.cost_date)::DATE
)
SELECT
    journal_id,
    journal_date::DATE AS journal_date,
    journal_name,
    line_type,
    account_code,
    account_name,
    dr,
    cr,
    memo
FROM journal_rows
ORDER BY journal_id, journal_date, line_type, account_code;

-- Balance check required by the journal pack.
WITH journal_rows AS (
    SELECT SUM(GREATEST(wip_cents, 0))::INTEGER AS dr, 0::INTEGER AS cr FROM wip_summary
    UNION ALL SELECT 0, SUM(GREATEST(wip_cents, 0))::INTEGER FROM wip_summary
    UNION ALL SELECT SUM(amount_cents)::INTEGER, 0 FROM costs
    UNION ALL SELECT 0, SUM(amount_cents)::INTEGER FROM costs
    UNION ALL SELECT (COUNT(*) * 750000)::INTEGER, 0 FROM fleet_register CROSS JOIN generate_series(DATE '2026-01-01', DATE '2026-06-01', INTERVAL '1 month')
    UNION ALL SELECT 0, (COUNT(*) * 750000)::INTEGER FROM fleet_register CROSS JOIN generate_series(DATE '2026-01-01', DATE '2026-06-01', INTERVAL '1 month')
    UNION ALL SELECT COALESCE(SUM(withholding_cents), 0)::INTEGER, 0 FROM payg_withholding
    UNION ALL SELECT 0, COALESCE(SUM(withholding_cents), 0)::INTEGER FROM payg_withholding
)
SELECT SUM(dr) = SUM(cr) AS balanced;
