-- Grounded Fleet & Plant Hire Finance App
-- 03_business_queries.sql
-- Named business queries for dashboard, reconciliation and compliance review.
-- Amounts are returned in cents unless an alias explicitly says pct or hours.

/*
Q01: Monthly revenue summary by equipment type
Answers: how much ex-GST revenue, hire revenue, float revenue and GST output each equipment type earned by month.
*/
SELECT
    DATE_TRUNC('month', usage_date)::DATE AS month_start,
    equipment_type,
    SUM(hire_revenue_cents)::INTEGER AS hire_revenue_cents,
    SUM(float_applied_cents)::INTEGER AS float_revenue_cents,
    SUM(total_revenue_cents)::INTEGER AS total_revenue_cents,
    SUM(gst_output_cents)::INTEGER AS gst_output_cents
FROM revenue_engine
GROUP BY 1, 2
ORDER BY 1, 2;

/*
Q02: Top 10 jobs by total revenue
Answers: which customer jobs generated the highest earned revenue.
*/
SELECT
    jm.job_id,
    jm.customer_name,
    jm.site_name,
    SUM(re.total_revenue_cents)::INTEGER AS total_revenue_cents
FROM revenue_engine re
JOIN job_master jm ON jm.job_id = re.job_id
GROUP BY jm.job_id, jm.customer_name, jm.site_name
ORDER BY total_revenue_cents DESC
LIMIT 10;

/*
Q03: WIP report - all jobs with unbilled revenue > $5,000
Answers: job-plus-asset earned revenue that has not yet been invoiced and exceeds the review threshold.
*/
SELECT
    job_id,
    customer_name,
    asset_id,
    equipment_type,
    earned_revenue_cents,
    invoiced_amount_cents,
    wip_cents
FROM wip_summary
WHERE wip_cents > 500000
ORDER BY wip_cents DESC;

/*
Q04: Underbilled detection - where earned > invoiced by more than $500
Answers: job-plus-asset lines where invoices are materially below model-earned revenue.
*/
SELECT
    job_id,
    customer_name,
    asset_id,
    equipment_type,
    earned_revenue_cents,
    invoiced_amount_cents,
    wip_cents AS underbilled_cents
FROM wip_summary
WHERE wip_cents > 50000
ORDER BY underbilled_cents DESC;

/*
Q05: Overbilled detection - where invoiced > earned by more than $500
Answers: job-plus-asset lines where MYOB invoices exceed model-earned revenue.
*/
SELECT
    job_id,
    customer_name,
    asset_id,
    equipment_type,
    earned_revenue_cents,
    invoiced_amount_cents,
    ABS(wip_cents)::INTEGER AS overbilled_cents
FROM wip_summary
WHERE wip_cents < -50000
ORDER BY overbilled_cents DESC;

/*
Q06: Job profit and margin by job, sorted by margin ascending (worst first)
Answers: full job profitability view with worst margins first.
*/
SELECT
    jp.job_id,
    jm.customer_name,
    jm.site_name,
    jp.revenue_cents,
    jp.total_cost_cents,
    jp.profit_cents,
    jp.margin_pct
FROM job_profit jp
JOIN job_master jm ON jm.job_id = jp.job_id
ORDER BY jp.margin_pct ASC, jp.profit_cents ASC;

/*
Q07: Asset utilisation - actual hours vs forecast hours by asset
Answers: actual worked hours compared with forecast available utilised hours for each asset.
*/
SELECT
    fr.asset_id,
    fr.equipment_type,
    COALESCE(a.actual_hours, 0)::NUMERIC(12,1) AS actual_hours,
    COALESCE(f.forecast_hours, 0)::NUMERIC(12,1) AS forecast_hours,
    CASE
        WHEN COALESCE(f.forecast_hours, 0) = 0 THEN 0
        ELSE ROUND(a.actual_hours::NUMERIC / f.forecast_hours * 100, 2)
    END AS utilisation_vs_forecast_pct
FROM fleet_register fr
LEFT JOIN (
    SELECT asset_id, SUM(hours_worked) AS actual_hours
    FROM usage_log
    GROUP BY asset_id
) a ON a.asset_id = fr.asset_id
LEFT JOIN (
    SELECT asset_id, SUM(hours_per_day * working_days * utilisation_pct) AS forecast_hours
    FROM forecast_assumptions
    GROUP BY asset_id
) f ON f.asset_id = fr.asset_id
ORDER BY utilisation_vs_forecast_pct DESC;

/*
Q08: Rain-off days by month - count and revenue impact
Answers: monthly count of rain-off usage days and the extra billable revenue created by rain minimums.
*/
SELECT
    DATE_TRUNC('month', re.usage_date)::DATE AS month_start,
    COUNT(*) FILTER (WHERE ul.rain_flag) AS rain_usage_rows,
    SUM(CASE WHEN ul.rain_flag THEN re.total_revenue_cents ELSE 0 END)::INTEGER AS rain_day_total_revenue_cents,
    SUM(CASE WHEN ul.rain_flag THEN GREATEST(re.billable_hours - re.actual_hours, 0) * re.rate_used_cents ELSE 0 END)::INTEGER AS rain_minimum_impact_cents
FROM revenue_engine re
JOIN usage_log ul ON ul.usage_id = re.usage_id
GROUP BY 1
ORDER BY 1;

/*
Q09: Float fee revenue by job - flag jobs where float > 40% of total revenue
Answers: jobs where mobilisation charges dominate the earned revenue mix.
*/
SELECT
    re.job_id,
    jm.customer_name,
    SUM(re.float_applied_cents)::INTEGER AS float_revenue_cents,
    SUM(re.total_revenue_cents)::INTEGER AS total_revenue_cents,
    ROUND(SUM(re.float_applied_cents)::NUMERIC / NULLIF(SUM(re.total_revenue_cents), 0) * 100, 2) AS float_pct,
    (SUM(re.float_applied_cents)::NUMERIC / NULLIF(SUM(re.total_revenue_cents), 0) > 0.40) AS float_over_40_pct
FROM revenue_engine re
JOIN job_master jm ON jm.job_id = re.job_id
GROUP BY re.job_id, jm.customer_name
ORDER BY float_pct DESC NULLS LAST;

/*
Q10: GST reconciliation - model output GST vs myob_gl_extract GST balance
Answers: monthly model GST payable/credit compared with MYOB GST ledger balances.
*/
WITH model_gst AS (
    SELECT
        period_start,
        SUM(CASE WHEN bas_field = '1A' THEN amount_cents ELSE 0 END)::INTEGER AS model_gst_output_cents,
        SUM(CASE WHEN bas_field = '1B' THEN amount_cents ELSE 0 END)::INTEGER AS model_gst_input_cents
    FROM bas_check
    GROUP BY period_start
),
myob_gst AS (
    SELECT
        period_start,
        SUM(CASE WHEN account_name = 'GST Collected' THEN gst_cents ELSE 0 END)::INTEGER AS myob_gst_output_cents,
        ABS(SUM(CASE WHEN account_name = 'GST Paid' THEN gst_cents ELSE 0 END))::INTEGER AS myob_gst_input_cents
    FROM myob_gl_extract
    WHERE tax_code = 'GST'
    GROUP BY period_start
)
SELECT
    COALESCE(m.period_start, g.period_start) AS period_start,
    COALESCE(m.model_gst_output_cents, 0) AS model_gst_output_cents,
    COALESCE(g.myob_gst_output_cents, 0) AS myob_gst_output_cents,
    COALESCE(m.model_gst_input_cents, 0) AS model_gst_input_cents,
    COALESCE(g.myob_gst_input_cents, 0) AS myob_gst_input_cents,
    (COALESCE(m.model_gst_output_cents, 0) - COALESCE(g.myob_gst_output_cents, 0))::INTEGER AS output_variance_cents,
    (COALESCE(m.model_gst_input_cents, 0) - COALESCE(g.myob_gst_input_cents, 0))::INTEGER AS input_variance_cents
FROM model_gst m
FULL OUTER JOIN myob_gst g ON g.period_start = m.period_start
ORDER BY 1;

/*
Q11: ABN withholding summary - total W4 liability, confirm not in GST
Answers: no-ABN withholding liability by period with an explicit non-GST confirmation.
*/
SELECT
    DATE_TRUNC('month', c.cost_date)::DATE AS month_start,
    SUM(p.gross_ex_gst_cents)::INTEGER AS gross_subject_to_withholding_cents,
    SUM(p.withholding_cents)::INTEGER AS w4_liability_cents,
    BOOL_AND(p.bas_field = 'W4') AS posted_to_w4,
    FALSE AS included_in_net_gst
FROM payg_withholding p
JOIN costs c ON c.cost_id = p.cost_id
GROUP BY 1
ORDER BY 1;

/*
Q12: BAS summary - all BAS fields G1 G2 G3 G10 G11 1A 1B W4 Net GST
Answers: monthly BAS field summary with net GST excluding PAYG W4.
*/
SELECT
    period_start,
    SUM(CASE WHEN bas_field = 'G1' THEN amount_cents ELSE 0 END)::INTEGER AS g1_cents,
    SUM(CASE WHEN bas_field = 'G2' THEN amount_cents ELSE 0 END)::INTEGER AS g2_cents,
    SUM(CASE WHEN bas_field = 'G3' THEN amount_cents ELSE 0 END)::INTEGER AS g3_cents,
    SUM(CASE WHEN bas_field = 'G10' THEN amount_cents ELSE 0 END)::INTEGER AS g10_cents,
    SUM(CASE WHEN bas_field = 'G11' THEN amount_cents ELSE 0 END)::INTEGER AS g11_cents,
    SUM(CASE WHEN bas_field = '1A' THEN amount_cents ELSE 0 END)::INTEGER AS one_a_cents,
    SUM(CASE WHEN bas_field = '1B' THEN amount_cents ELSE 0 END)::INTEGER AS one_b_cents,
    SUM(CASE WHEN bas_field = 'W4' THEN amount_cents ELSE 0 END)::INTEGER AS w4_cents,
    (
        SUM(CASE WHEN bas_field = '1A' THEN amount_cents ELSE 0 END)
        - SUM(CASE WHEN bas_field = '1B' THEN amount_cents ELSE 0 END)
    )::INTEGER AS net_gst_cents
FROM bas_check
GROUP BY period_start
ORDER BY period_start;

/*
Q13: Payroll compliance - super expected vs super paid, variance
Answers: super guarantee expected at configured rate compared with payroll super amount.
*/
WITH cfg AS (
    SELECT config_value AS super_rate
    FROM payroll_config
    WHERE config_key = 'super_guarantee_rate'
)
SELECT
    pm.month_start,
    pm.pay_group,
    pm.gross_wages_cents,
    ROUND(pm.gross_wages_cents * cfg.super_rate)::INTEGER AS expected_super_cents,
    pm.super_guarantee_cents AS super_paid_cents,
    (pm.super_guarantee_cents - ROUND(pm.gross_wages_cents * cfg.super_rate))::INTEGER AS variance_cents
FROM payroll_monthly pm
CROSS JOIN cfg
ORDER BY pm.month_start, pm.pay_group;

/*
Q14: VIC payroll tax - monthly taxable wages above threshold
Answers: wages above the monthly threshold and expected payroll tax at 4.85%.
*/
WITH cfg AS (
    SELECT
        MAX(CASE WHEN config_key = 'vic_payroll_tax_monthly_threshold' THEN config_value END) * 100 AS threshold_cents,
        MAX(CASE WHEN config_key = 'vic_payroll_tax_rate' THEN config_value END) AS payroll_tax_rate
    FROM payroll_config
),
month_wages AS (
    SELECT month_start, SUM(gross_wages_cents)::INTEGER AS gross_wages_cents, SUM(payroll_tax_cents)::INTEGER AS payroll_tax_recorded_cents
    FROM payroll_monthly
    GROUP BY month_start
)
SELECT
    mw.month_start,
    mw.gross_wages_cents,
    cfg.threshold_cents::INTEGER AS threshold_cents,
    GREATEST(mw.gross_wages_cents - cfg.threshold_cents, 0)::INTEGER AS taxable_wages_cents,
    ROUND(GREATEST(mw.gross_wages_cents - cfg.threshold_cents, 0) * cfg.payroll_tax_rate)::INTEGER AS expected_payroll_tax_cents,
    mw.payroll_tax_recorded_cents
FROM month_wages mw
CROSS JOIN cfg
ORDER BY mw.month_start;

/*
Q15: Fuel tax credit summary by asset and month
Answers: eligible litres and placeholder FTC estimate by asset and month.
*/
SELECT
    ftc.month_start,
    ftc.asset_id,
    fr.equipment_type,
    ftc.fuel_cost_cents,
    ftc.litres,
    ftc.ato_eligible_rate_cents_per_litre,
    ftc.fuel_tax_credit_cents,
    ftc.note
FROM fuel_tax_credit ftc
JOIN fleet_register fr ON fr.asset_id = ftc.asset_id
ORDER BY ftc.month_start, ftc.asset_id;

/*
Q16: Exception log - all open exceptions by severity
Answers: unresolved finance-control exceptions sorted by severity and value.
*/
SELECT
    exception_id,
    severity,
    exception_type,
    job_id,
    asset_id,
    amount_cents,
    message,
    created_at
FROM exception_log
WHERE severity <> 'Closed'
ORDER BY
    CASE severity WHEN 'Critical' THEN 1 WHEN 'High' THEN 2 WHEN 'Medium' THEN 3 WHEN 'Low' THEN 4 ELSE 5 END,
    amount_cents DESC;

/*
Q17: Month-on-month revenue trend - all 6 months
Answers: total revenue trend for January through June 2026, including months with zero revenue.
*/
WITH months AS (
    SELECT generate_series(DATE '2026-01-01', DATE '2026-06-01', INTERVAL '1 month')::DATE AS month_start
),
revenue AS (
    SELECT DATE_TRUNC('month', usage_date)::DATE AS month_start, SUM(total_revenue_cents)::INTEGER AS revenue_cents
    FROM revenue_engine
    GROUP BY 1
)
SELECT
    m.month_start,
    COALESCE(r.revenue_cents, 0) AS revenue_cents,
    COALESCE(r.revenue_cents, 0) - LAG(COALESCE(r.revenue_cents, 0)) OVER (ORDER BY m.month_start) AS mom_change_cents
FROM months m
LEFT JOIN revenue r ON r.month_start = m.month_start
ORDER BY m.month_start;

/*
Q18: Customer revenue ranking with YTD and margin
Answers: customer-level revenue, cost, profit and margin ranked by YTD revenue.
*/
SELECT
    jm.customer_name,
    SUM(jp.revenue_cents)::INTEGER AS ytd_revenue_cents,
    SUM(jp.total_cost_cents)::INTEGER AS ytd_cost_cents,
    SUM(jp.profit_cents)::INTEGER AS ytd_profit_cents,
    CASE
        WHEN SUM(jp.revenue_cents) = 0 THEN 0
        ELSE ROUND(SUM(jp.profit_cents)::NUMERIC / SUM(jp.revenue_cents) * 100, 2)
    END AS margin_pct,
    RANK() OVER (ORDER BY SUM(jp.revenue_cents) DESC) AS revenue_rank
FROM job_profit jp
JOIN job_master jm ON jm.job_id = jp.job_id
GROUP BY jm.customer_name
ORDER BY revenue_rank;

/*
Q19: Cost breakdown by type as % of revenue
Answers: direct cost category mix compared with total earned revenue.
*/
WITH total_revenue AS (
    SELECT SUM(total_revenue_cents)::NUMERIC AS revenue_cents
    FROM revenue_engine
)
SELECT
    c.cost_category,
    SUM(c.amount_cents)::INTEGER AS cost_cents,
    ROUND(SUM(c.amount_cents)::NUMERIC / NULLIF((SELECT revenue_cents FROM total_revenue), 0) * 100, 2) AS pct_of_revenue
FROM costs c
GROUP BY c.cost_category
ORDER BY cost_cents DESC;

/*
Q20: Operator hours - total hours per operator, cost per hour
Answers: operator utilisation hours and labour cost per actual hour.
*/
SELECT
    ul.operator_name,
    SUM(ul.hours_worked)::NUMERIC(12,1) AS total_hours,
    SUM(COALESCE(l.labour_cost_cents, 0))::INTEGER AS labour_cost_cents,
    ROUND(
        SUM(COALESCE(l.labour_cost_cents, 0))::NUMERIC
        / NULLIF(SUM(ul.hours_worked), 0),
        0
    )::INTEGER AS labour_cost_per_hour_cents
FROM usage_log ul
LEFT JOIN (
    SELECT usage_id, SUM(amount_cents)::INTEGER AS labour_cost_cents
    FROM costs
    WHERE cost_category = 'Labour'
    GROUP BY usage_id
) l ON l.usage_id = ul.usage_id
GROUP BY ul.operator_name
ORDER BY total_hours DESC;
