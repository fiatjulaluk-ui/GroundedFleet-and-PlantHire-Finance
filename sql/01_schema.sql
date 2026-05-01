-- Grounded Fleet & Plant Hire Finance App
-- 01_schema.sql
-- PostgreSQL schema for synthetic finance-control data.

DROP VIEW IF EXISTS wip_summary CASCADE;
DROP TABLE IF EXISTS asset_profit CASCADE;
DROP TABLE IF EXISTS job_profit CASCADE;
DROP TABLE IF EXISTS revenue_engine CASCADE;
DROP TABLE IF EXISTS staging_revenue_engine CASCADE;
DROP TABLE IF EXISTS bas_check CASCADE;
DROP TABLE IF EXISTS payg_withholding CASCADE;
DROP TABLE IF EXISTS fuel_tax_credit CASCADE;
DROP TABLE IF EXISTS payroll_monthly CASCADE;
DROP TABLE IF EXISTS payroll_config CASCADE;
DROP TABLE IF EXISTS myob_gl_extract CASCADE;
DROP TABLE IF EXISTS invoice_myob CASCADE;
DROP TABLE IF EXISTS costs CASCADE;
DROP TABLE IF EXISTS job_rates CASCADE;
DROP TABLE IF EXISTS usage_log CASCADE;
DROP TABLE IF EXISTS job_master CASCADE;
DROP TABLE IF EXISTS fleet_register CASCADE;
DROP TABLE IF EXISTS forecast_assumptions CASCADE;
DROP TABLE IF EXISTS exception_log CASCADE;
DROP TABLE IF EXISTS rate_card CASCADE;

CREATE TABLE rate_card (
    rate_card_id TEXT PRIMARY KEY,
    equipment_type TEXT NOT NULL UNIQUE,
    hourly_rate_cents INTEGER NOT NULL CHECK (hourly_rate_cents >= 0),
    float_fee_cents INTEGER NOT NULL CHECK (float_fee_cents >= 0),
    effective_from DATE NOT NULL,
    effective_to DATE,
    source_note TEXT NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
COMMENT ON TABLE rate_card IS 'Commercial source of truth for hire hourly rates and float fees by equipment type.';
COMMENT ON COLUMN rate_card.rate_card_id IS 'Stable primary key for a rate-card line.';
COMMENT ON COLUMN rate_card.equipment_type IS 'Equipment category charged to customers.';
COMMENT ON COLUMN rate_card.hourly_rate_cents IS 'Standard wet-hire hourly rate, stored as cents ex-GST.';
COMMENT ON COLUMN rate_card.float_fee_cents IS 'Standard mobilisation float fee, stored as cents ex-GST.';
COMMENT ON COLUMN rate_card.effective_from IS 'First date this rate-card line applies.';
COMMENT ON COLUMN rate_card.effective_to IS 'Last date this rate-card line applies, null when current.';
COMMENT ON COLUMN rate_card.source_note IS 'Business note describing source and update cadence.';
COMMENT ON COLUMN rate_card.created_at IS 'Timestamp when this row was loaded into the app database.';
COMMENT ON COLUMN rate_card.updated_at IS 'Timestamp when this row was last updated in the app database.';

CREATE TABLE fleet_register (
    asset_id TEXT PRIMARY KEY,
    equipment_type TEXT NOT NULL REFERENCES rate_card(equipment_type),
    serial_number TEXT NOT NULL,
    purchase_date DATE NOT NULL,
    status TEXT NOT NULL CHECK (status IN ('Active', 'In Workshop', 'On Hire')),
    home_depot TEXT NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
COMMENT ON TABLE fleet_register IS 'Owned fleet assets available for wet hire and profitability reporting.';
COMMENT ON COLUMN fleet_register.asset_id IS 'Internal fleet asset identifier.';
COMMENT ON COLUMN fleet_register.equipment_type IS 'Rate-card equipment type for the asset.';
COMMENT ON COLUMN fleet_register.serial_number IS 'Manufacturer or internal serial number.';
COMMENT ON COLUMN fleet_register.purchase_date IS 'Date the business acquired the asset.';
COMMENT ON COLUMN fleet_register.status IS 'Current operating status of the asset.';
COMMENT ON COLUMN fleet_register.home_depot IS 'Depot where the asset is normally based.';
COMMENT ON COLUMN fleet_register.created_at IS 'Timestamp when this row was loaded into the app database.';
COMMENT ON COLUMN fleet_register.updated_at IS 'Timestamp when this row was last updated in the app database.';

CREATE TABLE job_master (
    job_id TEXT PRIMARY KEY,
    customer_name TEXT NOT NULL,
    site_name TEXT NOT NULL,
    site_address TEXT NOT NULL,
    start_date DATE NOT NULL,
    end_date DATE NOT NULL,
    duration_days INTEGER NOT NULL CHECK (duration_days > 0),
    status TEXT NOT NULL CHECK (status IN ('Open', 'Completed', 'Invoiced')),
    purchase_order TEXT NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    CHECK (end_date >= start_date)
);
COMMENT ON TABLE job_master IS 'Customer jobs and hire terms used to drive usage, billing, WIP and profitability.';
COMMENT ON COLUMN job_master.job_id IS 'Internal job identifier.';
COMMENT ON COLUMN job_master.customer_name IS 'Customer receiving the wet-hire service.';
COMMENT ON COLUMN job_master.site_name IS 'Named work site for the job.';
COMMENT ON COLUMN job_master.site_address IS 'Street address for the work site.';
COMMENT ON COLUMN job_master.start_date IS 'First calendar date of the hire term.';
COMMENT ON COLUMN job_master.end_date IS 'Last calendar date of the hire term.';
COMMENT ON COLUMN job_master.duration_days IS 'Planned hire duration in calendar days.';
COMMENT ON COLUMN job_master.status IS 'Operational and billing status of the job.';
COMMENT ON COLUMN job_master.purchase_order IS 'Customer purchase-order reference.';
COMMENT ON COLUMN job_master.created_at IS 'Timestamp when this row was loaded into the app database.';
COMMENT ON COLUMN job_master.updated_at IS 'Timestamp when this row was last updated in the app database.';

CREATE TABLE usage_log (
    usage_id TEXT PRIMARY KEY,
    job_id TEXT NOT NULL REFERENCES job_master(job_id),
    asset_id TEXT NOT NULL REFERENCES fleet_register(asset_id),
    equipment_type TEXT NOT NULL REFERENCES rate_card(equipment_type),
    usage_date DATE NOT NULL,
    site_name TEXT NOT NULL,
    hours_worked NUMERIC(5,1) NOT NULL CHECK (hours_worked >= 0),
    rain_flag BOOLEAN NOT NULL,
    float_required BOOLEAN NOT NULL,
    operator_name TEXT NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
COMMENT ON TABLE usage_log IS 'Daily asset usage by job, used as the operational source for revenue and direct costs.';
COMMENT ON COLUMN usage_log.usage_id IS 'Primary key for a daily asset usage row.';
COMMENT ON COLUMN usage_log.job_id IS 'Job that consumed the asset hours.';
COMMENT ON COLUMN usage_log.asset_id IS 'Fleet asset used on the job.';
COMMENT ON COLUMN usage_log.equipment_type IS 'Equipment type used for rate lookup.';
COMMENT ON COLUMN usage_log.usage_date IS 'Date the asset worked, Monday to Saturday in synthetic data.';
COMMENT ON COLUMN usage_log.site_name IS 'Site where the usage occurred.';
COMMENT ON COLUMN usage_log.hours_worked IS 'Actual physical hours worked by the asset.';
COMMENT ON COLUMN usage_log.rain_flag IS 'True when rain-off minimum hire rules apply.';
COMMENT ON COLUMN usage_log.float_required IS 'True when mobilisation or site movement float fee is billable.';
COMMENT ON COLUMN usage_log.operator_name IS 'Operator assigned to the asset for the day.';
COMMENT ON COLUMN usage_log.created_at IS 'Timestamp when this row was loaded into the app database.';
COMMENT ON COLUMN usage_log.updated_at IS 'Timestamp when this row was last updated in the app database.';

CREATE TABLE job_rates (
    job_rate_id TEXT PRIMARY KEY,
    job_id TEXT NOT NULL REFERENCES job_master(job_id),
    equipment_type TEXT NOT NULL REFERENCES rate_card(equipment_type),
    override_rate_cents INTEGER NOT NULL CHECK (override_rate_cents >= 0),
    standard_rate_cents INTEGER NOT NULL CHECK (standard_rate_cents >= 0),
    override_reason TEXT NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (job_id, equipment_type)
);
COMMENT ON TABLE job_rates IS 'Job-specific rate overrides, which take priority over the standard rate card.';
COMMENT ON COLUMN job_rates.job_rate_id IS 'Primary key for a job-specific rate override.';
COMMENT ON COLUMN job_rates.job_id IS 'Job receiving the override rate.';
COMMENT ON COLUMN job_rates.equipment_type IS 'Equipment type affected by the override.';
COMMENT ON COLUMN job_rates.override_rate_cents IS 'Approved override hourly rate, stored as cents ex-GST.';
COMMENT ON COLUMN job_rates.standard_rate_cents IS 'Rate-card hourly rate captured for variance comparison.';
COMMENT ON COLUMN job_rates.override_reason IS 'Business reason for the override.';
COMMENT ON COLUMN job_rates.created_at IS 'Timestamp when this row was loaded into the app database.';
COMMENT ON COLUMN job_rates.updated_at IS 'Timestamp when this row was last updated in the app database.';

CREATE TABLE costs (
    cost_id TEXT PRIMARY KEY,
    usage_id TEXT REFERENCES usage_log(usage_id),
    job_id TEXT NOT NULL REFERENCES job_master(job_id),
    asset_id TEXT REFERENCES fleet_register(asset_id),
    cost_date DATE NOT NULL,
    cost_category TEXT NOT NULL,
    amount_cents INTEGER NOT NULL CHECK (amount_cents >= 0),
    gst_input_cents INTEGER NOT NULL DEFAULT 0 CHECK (gst_input_cents >= 0),
    tax_code TEXT NOT NULL,
    bas_g11_cents INTEGER NOT NULL DEFAULT 0,
    bas_1b_cents INTEGER NOT NULL DEFAULT 0,
    supplier_name TEXT NOT NULL,
    withholding_cents INTEGER NOT NULL DEFAULT 0 CHECK (withholding_cents >= 0),
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
COMMENT ON TABLE costs IS 'Direct and job-linked costs, including fuel, labour, maintenance, transport, tolls and no-ABN subcontract costs.';
COMMENT ON COLUMN costs.cost_id IS 'Primary key for a cost transaction.';
COMMENT ON COLUMN costs.usage_id IS 'Usage row that caused the cost, null for job-level subcontract no-ABN costs.';
COMMENT ON COLUMN costs.job_id IS 'Job to which the cost belongs; no orphan costs are allowed.';
COMMENT ON COLUMN costs.asset_id IS 'Asset to which the cost belongs, null when cost is job-level.';
COMMENT ON COLUMN costs.cost_date IS 'Date the cost was incurred.';
COMMENT ON COLUMN costs.cost_category IS 'Business category of cost.';
COMMENT ON COLUMN costs.amount_cents IS 'Cost amount ex-GST or GST-free amount, stored as cents.';
COMMENT ON COLUMN costs.gst_input_cents IS 'GST input tax credit amount in cents.';
COMMENT ON COLUMN costs.tax_code IS 'Tax treatment code such as GST, N-T or ABN.';
COMMENT ON COLUMN costs.bas_g11_cents IS 'BAS G11 non-capital purchase amount in cents.';
COMMENT ON COLUMN costs.bas_1b_cents IS 'BAS 1B GST credit amount in cents.';
COMMENT ON COLUMN costs.supplier_name IS 'Supplier or internal source for the cost.';
COMMENT ON COLUMN costs.withholding_cents IS 'PAYG withholding amount for no-ABN costs.';
COMMENT ON COLUMN costs.created_at IS 'Timestamp when this row was loaded into the app database.';
COMMENT ON COLUMN costs.updated_at IS 'Timestamp when this row was last updated in the app database.';

CREATE TABLE invoice_myob (
    invoice_id TEXT PRIMARY KEY,
    myob_invoice_number TEXT NOT NULL UNIQUE,
    job_id TEXT NOT NULL REFERENCES job_master(job_id),
    asset_id TEXT NOT NULL REFERENCES fleet_register(asset_id),
    invoice_date DATE NOT NULL,
    amount_ex_gst_cents INTEGER NOT NULL CHECK (amount_ex_gst_cents >= 0),
    gst_cents INTEGER NOT NULL CHECK (gst_cents >= 0),
    amount_inc_gst_cents INTEGER NOT NULL CHECK (amount_inc_gst_cents >= 0),
    status TEXT NOT NULL CHECK (status IN ('Issued', 'Paid', 'Draft')),
    tax_code TEXT NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
COMMENT ON TABLE invoice_myob IS 'MYOB invoice lines by completed job and asset for billing and WIP reconciliation.';
COMMENT ON COLUMN invoice_myob.invoice_id IS 'Internal invoice row identifier.';
COMMENT ON COLUMN invoice_myob.myob_invoice_number IS 'Invoice number from MYOB Advanced.';
COMMENT ON COLUMN invoice_myob.job_id IS 'Job billed on the invoice line.';
COMMENT ON COLUMN invoice_myob.asset_id IS 'Asset billed on the invoice line.';
COMMENT ON COLUMN invoice_myob.invoice_date IS 'Invoice issue date.';
COMMENT ON COLUMN invoice_myob.amount_ex_gst_cents IS 'Invoice amount excluding GST, stored as cents.';
COMMENT ON COLUMN invoice_myob.gst_cents IS 'GST on the invoice amount, stored as cents.';
COMMENT ON COLUMN invoice_myob.amount_inc_gst_cents IS 'Invoice amount including GST, stored as cents.';
COMMENT ON COLUMN invoice_myob.status IS 'Invoice lifecycle status from MYOB.';
COMMENT ON COLUMN invoice_myob.tax_code IS 'Tax code applied to invoice revenue.';
COMMENT ON COLUMN invoice_myob.created_at IS 'Timestamp when this row was loaded into the app database.';
COMMENT ON COLUMN invoice_myob.updated_at IS 'Timestamp when this row was last updated in the app database.';

CREATE TABLE myob_gl_extract (
    gl_extract_id TEXT PRIMARY KEY,
    period_start DATE NOT NULL,
    account_code TEXT NOT NULL,
    account_name TEXT NOT NULL,
    tax_code TEXT NOT NULL,
    debit_cents INTEGER NOT NULL DEFAULT 0,
    credit_cents INTEGER NOT NULL DEFAULT 0,
    gst_cents INTEGER NOT NULL DEFAULT 0,
    source_reference TEXT NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
COMMENT ON TABLE myob_gl_extract IS 'Imported MYOB Advanced general-ledger balances for reconciliation against model outputs.';
COMMENT ON COLUMN myob_gl_extract.gl_extract_id IS 'Primary key for an imported GL extract row.';
COMMENT ON COLUMN myob_gl_extract.period_start IS 'Accounting month or BAS period start date.';
COMMENT ON COLUMN myob_gl_extract.account_code IS 'MYOB account code.';
COMMENT ON COLUMN myob_gl_extract.account_name IS 'MYOB account name.';
COMMENT ON COLUMN myob_gl_extract.tax_code IS 'Tax code on the GL row.';
COMMENT ON COLUMN myob_gl_extract.debit_cents IS 'Debit movement or balance in cents.';
COMMENT ON COLUMN myob_gl_extract.credit_cents IS 'Credit movement or balance in cents.';
COMMENT ON COLUMN myob_gl_extract.gst_cents IS 'GST component reported by MYOB in cents.';
COMMENT ON COLUMN myob_gl_extract.source_reference IS 'File, batch or report reference for audit trail.';
COMMENT ON COLUMN myob_gl_extract.created_at IS 'Timestamp when this row was loaded into the app database.';
COMMENT ON COLUMN myob_gl_extract.updated_at IS 'Timestamp when this row was last updated in the app database.';

CREATE TABLE payroll_config (
    config_key TEXT PRIMARY KEY,
    config_value NUMERIC(15,4) NOT NULL,
    effective_from DATE NOT NULL,
    note TEXT NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
COMMENT ON TABLE payroll_config IS 'Payroll, super, payroll-tax and CoINVEST configuration values.';
COMMENT ON COLUMN payroll_config.config_key IS 'Configuration key name.';
COMMENT ON COLUMN payroll_config.config_value IS 'Configuration value; rates are decimals and thresholds are dollars where noted.';
COMMENT ON COLUMN payroll_config.effective_from IS 'First date the configuration applies.';
COMMENT ON COLUMN payroll_config.note IS 'Business interpretation of the configuration.';
COMMENT ON COLUMN payroll_config.created_at IS 'Timestamp when this row was loaded into the app database.';
COMMENT ON COLUMN payroll_config.updated_at IS 'Timestamp when this row was last updated in the app database.';

CREATE TABLE payroll_monthly (
    payroll_month_id TEXT PRIMARY KEY,
    month_start DATE NOT NULL,
    pay_group TEXT NOT NULL,
    gross_wages_cents INTEGER NOT NULL CHECK (gross_wages_cents >= 0),
    super_guarantee_cents INTEGER NOT NULL CHECK (super_guarantee_cents >= 0),
    payroll_tax_cents INTEGER NOT NULL CHECK (payroll_tax_cents >= 0),
    coinvest_cents INTEGER NOT NULL CHECK (coinvest_cents >= 0),
    tax_code TEXT NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (month_start, pay_group)
);
COMMENT ON TABLE payroll_monthly IS 'Monthly payroll summaries by pay group for super, payroll tax and wage compliance.';
COMMENT ON COLUMN payroll_monthly.payroll_month_id IS 'Primary key for a monthly pay-group row.';
COMMENT ON COLUMN payroll_monthly.month_start IS 'First day of the payroll month.';
COMMENT ON COLUMN payroll_monthly.pay_group IS 'Payroll cohort such as Operators, Workshop or Admin.';
COMMENT ON COLUMN payroll_monthly.gross_wages_cents IS 'Gross wages for the month and pay group, stored as cents.';
COMMENT ON COLUMN payroll_monthly.super_guarantee_cents IS 'Expected super guarantee for ordinary time earnings, stored as cents.';
COMMENT ON COLUMN payroll_monthly.payroll_tax_cents IS 'Allocated VIC payroll tax for the pay group, stored as cents.';
COMMENT ON COLUMN payroll_monthly.coinvest_cents IS 'CoINVEST accrual, held at zero until confirmed.';
COMMENT ON COLUMN payroll_monthly.tax_code IS 'GST tax code; wages are N-T and outside GST.';
COMMENT ON COLUMN payroll_monthly.created_at IS 'Timestamp when this row was loaded into the app database.';
COMMENT ON COLUMN payroll_monthly.updated_at IS 'Timestamp when this row was last updated in the app database.';

CREATE TABLE revenue_engine (
    revenue_id TEXT PRIMARY KEY,
    usage_id TEXT NOT NULL UNIQUE REFERENCES usage_log(usage_id),
    job_id TEXT NOT NULL REFERENCES job_master(job_id),
    asset_id TEXT NOT NULL REFERENCES fleet_register(asset_id),
    equipment_type TEXT NOT NULL REFERENCES rate_card(equipment_type),
    usage_date DATE NOT NULL,
    actual_hours NUMERIC(5,1) NOT NULL,
    billable_hours NUMERIC(5,1) NOT NULL,
    rate_used_cents INTEGER NOT NULL CHECK (rate_used_cents >= 0),
    rate_source TEXT NOT NULL,
    hire_revenue_cents INTEGER NOT NULL CHECK (hire_revenue_cents >= 0),
    float_applied_cents INTEGER NOT NULL DEFAULT 0 CHECK (float_applied_cents >= 0),
    total_revenue_cents INTEGER NOT NULL CHECK (total_revenue_cents >= 0),
    gst_output_cents INTEGER NOT NULL CHECK (gst_output_cents >= 0),
    tax_code TEXT NOT NULL,
    bas_g1_cents INTEGER NOT NULL DEFAULT 0,
    bas_1a_cents INTEGER NOT NULL DEFAULT 0,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
COMMENT ON TABLE revenue_engine IS 'Calculated revenue by usage row after applying minimum hire, rain-off, float and override-rate rules.';
COMMENT ON COLUMN revenue_engine.revenue_id IS 'Primary key for calculated revenue row.';
COMMENT ON COLUMN revenue_engine.usage_id IS 'Usage row from which revenue is calculated.';
COMMENT ON COLUMN revenue_engine.job_id IS 'Job earning the revenue.';
COMMENT ON COLUMN revenue_engine.asset_id IS 'Asset earning the revenue.';
COMMENT ON COLUMN revenue_engine.equipment_type IS 'Equipment type used for rate-card or override lookup.';
COMMENT ON COLUMN revenue_engine.usage_date IS 'Date on which revenue was earned.';
COMMENT ON COLUMN revenue_engine.actual_hours IS 'Actual physical hours worked.';
COMMENT ON COLUMN revenue_engine.billable_hours IS 'Billable hours after 8-hour or rain-off 6-hour minimum.';
COMMENT ON COLUMN revenue_engine.rate_used_cents IS 'Hourly rate selected by job override priority then rate card.';
COMMENT ON COLUMN revenue_engine.rate_source IS 'Indicates whether the selected rate came from override or rate card.';
COMMENT ON COLUMN revenue_engine.hire_revenue_cents IS 'Billable-hours revenue only, excluding float fees.';
COMMENT ON COLUMN revenue_engine.float_applied_cents IS 'Float fee charged on this usage row, doubled when term hours are under 16.';
COMMENT ON COLUMN revenue_engine.total_revenue_cents IS 'Hire revenue plus float fee, excluding GST.';
COMMENT ON COLUMN revenue_engine.gst_output_cents IS 'GST output payable on hire revenue.';
COMMENT ON COLUMN revenue_engine.tax_code IS 'Revenue GST tax code.';
COMMENT ON COLUMN revenue_engine.bas_g1_cents IS 'BAS G1 sales amount.';
COMMENT ON COLUMN revenue_engine.bas_1a_cents IS 'BAS 1A GST payable amount.';
COMMENT ON COLUMN revenue_engine.created_at IS 'Timestamp when this row was loaded into the app database.';
COMMENT ON COLUMN revenue_engine.updated_at IS 'Timestamp when this row was last updated in the app database.';

CREATE TABLE staging_revenue_engine (LIKE revenue_engine INCLUDING DEFAULTS);
COMMENT ON TABLE staging_revenue_engine IS 'Loaded copy of generator revenue output, retained for comparison with SQL-calculated revenue_engine rows.';
COMMENT ON COLUMN staging_revenue_engine.revenue_id IS 'Generator revenue row identifier.';
COMMENT ON COLUMN staging_revenue_engine.usage_id IS 'Generator usage-row reference.';
COMMENT ON COLUMN staging_revenue_engine.job_id IS 'Generator job reference.';
COMMENT ON COLUMN staging_revenue_engine.asset_id IS 'Generator asset reference.';
COMMENT ON COLUMN staging_revenue_engine.equipment_type IS 'Generator equipment type.';
COMMENT ON COLUMN staging_revenue_engine.usage_date IS 'Generator revenue date.';
COMMENT ON COLUMN staging_revenue_engine.actual_hours IS 'Generator actual hours.';
COMMENT ON COLUMN staging_revenue_engine.billable_hours IS 'Generator billable hours.';
COMMENT ON COLUMN staging_revenue_engine.rate_used_cents IS 'Generator selected hourly rate in cents.';
COMMENT ON COLUMN staging_revenue_engine.rate_source IS 'Generator rate source label.';
COMMENT ON COLUMN staging_revenue_engine.hire_revenue_cents IS 'Generator hire revenue excluding float.';
COMMENT ON COLUMN staging_revenue_engine.float_applied_cents IS 'Generator float fee amount.';
COMMENT ON COLUMN staging_revenue_engine.total_revenue_cents IS 'Generator total revenue excluding GST.';
COMMENT ON COLUMN staging_revenue_engine.gst_output_cents IS 'Generator GST output amount.';
COMMENT ON COLUMN staging_revenue_engine.tax_code IS 'Generator tax code.';
COMMENT ON COLUMN staging_revenue_engine.bas_g1_cents IS 'Generator BAS G1 amount.';
COMMENT ON COLUMN staging_revenue_engine.bas_1a_cents IS 'Generator BAS 1A amount.';
COMMENT ON COLUMN staging_revenue_engine.created_at IS 'Timestamp when this row was loaded into the app database.';
COMMENT ON COLUMN staging_revenue_engine.updated_at IS 'Timestamp when this row was last updated in the app database.';

CREATE TABLE job_profit (
    job_id TEXT PRIMARY KEY REFERENCES job_master(job_id),
    revenue_cents INTEGER NOT NULL DEFAULT 0,
    fuel_direct_cents INTEGER NOT NULL DEFAULT 0,
    labour_direct_cents INTEGER NOT NULL DEFAULT 0,
    maintenance_cents INTEGER NOT NULL DEFAULT 0,
    transport_cents INTEGER NOT NULL DEFAULT 0,
    other_costs_cents INTEGER NOT NULL DEFAULT 0,
    total_cost_cents INTEGER NOT NULL DEFAULT 0,
    profit_cents INTEGER NOT NULL DEFAULT 0,
    margin_pct NUMERIC(8,4) NOT NULL DEFAULT 0,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
COMMENT ON TABLE job_profit IS 'Calculated job-level profitability from revenue less direct costs.';
COMMENT ON COLUMN job_profit.job_id IS 'Job being measured for profitability.';
COMMENT ON COLUMN job_profit.revenue_cents IS 'Total earned revenue excluding GST.';
COMMENT ON COLUMN job_profit.fuel_direct_cents IS 'Fuel direct costs linked to the job.';
COMMENT ON COLUMN job_profit.labour_direct_cents IS 'Labour direct costs linked to the job.';
COMMENT ON COLUMN job_profit.maintenance_cents IS 'Maintenance direct costs linked to the job.';
COMMENT ON COLUMN job_profit.transport_cents IS 'Transport and float costs linked to the job.';
COMMENT ON COLUMN job_profit.other_costs_cents IS 'Other job costs such as tolls or no-ABN subcontract costs.';
COMMENT ON COLUMN job_profit.total_cost_cents IS 'Total direct cost for the job.';
COMMENT ON COLUMN job_profit.profit_cents IS 'Revenue less total direct cost.';
COMMENT ON COLUMN job_profit.margin_pct IS 'Profit divided by revenue as a percentage.';
COMMENT ON COLUMN job_profit.created_at IS 'Timestamp when this row was calculated.';
COMMENT ON COLUMN job_profit.updated_at IS 'Timestamp when this row was last recalculated.';

CREATE TABLE asset_profit (
    asset_id TEXT PRIMARY KEY REFERENCES fleet_register(asset_id),
    revenue_cents INTEGER NOT NULL DEFAULT 0,
    fuel_direct_cents INTEGER NOT NULL DEFAULT 0,
    labour_direct_cents INTEGER NOT NULL DEFAULT 0,
    maintenance_cents INTEGER NOT NULL DEFAULT 0,
    transport_cents INTEGER NOT NULL DEFAULT 0,
    other_costs_cents INTEGER NOT NULL DEFAULT 0,
    total_cost_cents INTEGER NOT NULL DEFAULT 0,
    profit_cents INTEGER NOT NULL DEFAULT 0,
    margin_pct NUMERIC(8,4) NOT NULL DEFAULT 0,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
COMMENT ON TABLE asset_profit IS 'Calculated asset-level profitability from revenue less asset-linked costs.';
COMMENT ON COLUMN asset_profit.asset_id IS 'Asset being measured for profitability.';
COMMENT ON COLUMN asset_profit.revenue_cents IS 'Total earned revenue excluding GST.';
COMMENT ON COLUMN asset_profit.fuel_direct_cents IS 'Fuel direct costs linked to the asset.';
COMMENT ON COLUMN asset_profit.labour_direct_cents IS 'Labour direct costs linked to the asset.';
COMMENT ON COLUMN asset_profit.maintenance_cents IS 'Maintenance direct costs linked to the asset.';
COMMENT ON COLUMN asset_profit.transport_cents IS 'Transport and float costs linked to the asset.';
COMMENT ON COLUMN asset_profit.other_costs_cents IS 'Other asset-linked costs such as tolls.';
COMMENT ON COLUMN asset_profit.total_cost_cents IS 'Total direct cost for the asset.';
COMMENT ON COLUMN asset_profit.profit_cents IS 'Revenue less total direct cost.';
COMMENT ON COLUMN asset_profit.margin_pct IS 'Profit divided by revenue as a percentage.';
COMMENT ON COLUMN asset_profit.created_at IS 'Timestamp when this row was calculated.';
COMMENT ON COLUMN asset_profit.updated_at IS 'Timestamp when this row was last recalculated.';

CREATE TABLE forecast_assumptions (
    forecast_assumption_id TEXT PRIMARY KEY,
    period_start DATE NOT NULL,
    asset_id TEXT REFERENCES fleet_register(asset_id),
    equipment_type TEXT NOT NULL REFERENCES rate_card(equipment_type),
    fleet_count INTEGER NOT NULL CHECK (fleet_count >= 0),
    hours_per_day NUMERIC(5,1) NOT NULL CHECK (hours_per_day >= 0),
    working_days INTEGER NOT NULL CHECK (working_days >= 0),
    utilisation_pct NUMERIC(6,4) NOT NULL CHECK (utilisation_pct >= 0),
    rate_cents INTEGER NOT NULL CHECK (rate_cents >= 0),
    forecast_revenue_cents INTEGER NOT NULL CHECK (forecast_revenue_cents >= 0),
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
COMMENT ON TABLE forecast_assumptions IS 'Monthly forecast drivers for fleet utilisation and revenue planning.';
COMMENT ON COLUMN forecast_assumptions.forecast_assumption_id IS 'Primary key for a forecast assumption row.';
COMMENT ON COLUMN forecast_assumptions.period_start IS 'First day of the forecast month.';
COMMENT ON COLUMN forecast_assumptions.asset_id IS 'Optional asset-specific forecast driver.';
COMMENT ON COLUMN forecast_assumptions.equipment_type IS 'Equipment type forecasted.';
COMMENT ON COLUMN forecast_assumptions.fleet_count IS 'Number of assets assumed available.';
COMMENT ON COLUMN forecast_assumptions.hours_per_day IS 'Assumed productive hours per working day.';
COMMENT ON COLUMN forecast_assumptions.working_days IS 'Assumed working days in the period.';
COMMENT ON COLUMN forecast_assumptions.utilisation_pct IS 'Assumed utilisation percentage as a decimal.';
COMMENT ON COLUMN forecast_assumptions.rate_cents IS 'Assumed hourly rate in cents.';
COMMENT ON COLUMN forecast_assumptions.forecast_revenue_cents IS 'Calculated forecast revenue in cents.';
COMMENT ON COLUMN forecast_assumptions.created_at IS 'Timestamp when this row was loaded into the app database.';
COMMENT ON COLUMN forecast_assumptions.updated_at IS 'Timestamp when this row was last updated in the app database.';

CREATE TABLE bas_check (
    bas_check_id TEXT PRIMARY KEY,
    period_start DATE NOT NULL,
    bas_field TEXT NOT NULL,
    amount_cents INTEGER NOT NULL,
    source_table TEXT NOT NULL,
    notes TEXT NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
COMMENT ON TABLE bas_check IS 'Stored BAS check lines by period and BAS field for review and export.';
COMMENT ON COLUMN bas_check.bas_check_id IS 'Primary key for a BAS check line.';
COMMENT ON COLUMN bas_check.period_start IS 'First day of the BAS reporting month or period.';
COMMENT ON COLUMN bas_check.bas_field IS 'BAS field such as G1, G11, 1A, 1B or W4.';
COMMENT ON COLUMN bas_check.amount_cents IS 'Amount reported to the BAS field in cents.';
COMMENT ON COLUMN bas_check.source_table IS 'Model source used for the BAS check amount.';
COMMENT ON COLUMN bas_check.notes IS 'Business note or reconciliation explanation.';
COMMENT ON COLUMN bas_check.created_at IS 'Timestamp when this row was calculated.';
COMMENT ON COLUMN bas_check.updated_at IS 'Timestamp when this row was last recalculated.';

CREATE TABLE payg_withholding (
    payg_withholding_id TEXT PRIMARY KEY,
    job_id TEXT NOT NULL REFERENCES job_master(job_id),
    cost_id TEXT NOT NULL REFERENCES costs(cost_id),
    supplier_name TEXT NOT NULL,
    gross_ex_gst_cents INTEGER NOT NULL CHECK (gross_ex_gst_cents >= 0),
    withholding_rate NUMERIC(6,4) NOT NULL,
    withholding_cents INTEGER NOT NULL CHECK (withholding_cents >= 0),
    liability_account TEXT NOT NULL,
    bas_field TEXT NOT NULL CHECK (bas_field = 'W4'),
    note TEXT NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
COMMENT ON TABLE payg_withholding IS 'No-ABN PAYG withholding liabilities reported at BAS W4 and excluded from net GST.';
COMMENT ON COLUMN payg_withholding.payg_withholding_id IS 'Primary key for a PAYG withholding row.';
COMMENT ON COLUMN payg_withholding.job_id IS 'Job linked to the no-ABN supplier cost.';
COMMENT ON COLUMN payg_withholding.cost_id IS 'Cost row that triggered withholding.';
COMMENT ON COLUMN payg_withholding.supplier_name IS 'Supplier with no ABN or withholding requirement.';
COMMENT ON COLUMN payg_withholding.gross_ex_gst_cents IS 'Gross ex-GST supplier charge subject to withholding.';
COMMENT ON COLUMN payg_withholding.withholding_rate IS 'Withholding rate, 0.47 for no-ABN scenario.';
COMMENT ON COLUMN payg_withholding.withholding_cents IS 'PAYG withholding liability amount in cents.';
COMMENT ON COLUMN payg_withholding.liability_account IS 'Balance sheet liability account for withholding.';
COMMENT ON COLUMN payg_withholding.bas_field IS 'BAS field W4 for PAYG withholding.';
COMMENT ON COLUMN payg_withholding.note IS 'Compliance note explaining treatment.';
COMMENT ON COLUMN payg_withholding.created_at IS 'Timestamp when this row was loaded into the app database.';
COMMENT ON COLUMN payg_withholding.updated_at IS 'Timestamp when this row was last updated in the app database.';

CREATE TABLE exception_log (
    exception_id TEXT PRIMARY KEY,
    exception_type TEXT NOT NULL,
    job_id TEXT REFERENCES job_master(job_id),
    asset_id TEXT REFERENCES fleet_register(asset_id),
    amount_cents INTEGER NOT NULL DEFAULT 0,
    message TEXT NOT NULL,
    severity TEXT NOT NULL DEFAULT 'Open',
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
COMMENT ON TABLE exception_log IS 'Open finance-control exceptions such as underbilling, overbilling, missing withholding and orphan costs.';
COMMENT ON COLUMN exception_log.exception_id IS 'Primary key for an exception.';
COMMENT ON COLUMN exception_log.exception_type IS 'Exception category used for dashboard filtering.';
COMMENT ON COLUMN exception_log.job_id IS 'Job affected by the exception.';
COMMENT ON COLUMN exception_log.asset_id IS 'Asset affected by the exception.';
COMMENT ON COLUMN exception_log.amount_cents IS 'Financial value associated with the exception.';
COMMENT ON COLUMN exception_log.message IS 'Human-readable exception explanation.';
COMMENT ON COLUMN exception_log.severity IS 'Exception status or severity label.';
COMMENT ON COLUMN exception_log.created_at IS 'Timestamp when this row was detected.';
COMMENT ON COLUMN exception_log.updated_at IS 'Timestamp when this row was last updated.';

CREATE TABLE fuel_tax_credit (
    fuel_tax_credit_id TEXT PRIMARY KEY,
    asset_id TEXT NOT NULL REFERENCES fleet_register(asset_id),
    month_start DATE NOT NULL,
    fuel_cost_cents INTEGER NOT NULL CHECK (fuel_cost_cents >= 0),
    diesel_price_estimate_cents_per_litre INTEGER NOT NULL CHECK (diesel_price_estimate_cents_per_litre > 0),
    litres NUMERIC(12,2) NOT NULL CHECK (litres >= 0),
    ato_eligible_rate_cents_per_litre NUMERIC(8,2) NOT NULL CHECK (ato_eligible_rate_cents_per_litre >= 0),
    fuel_tax_credit_cents INTEGER NOT NULL CHECK (fuel_tax_credit_cents >= 0),
    note TEXT NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (asset_id, month_start)
);
COMMENT ON TABLE fuel_tax_credit IS 'Fuel Tax Credit estimate by asset and month based on diesel cost, litres and ATO rate.';
COMMENT ON COLUMN fuel_tax_credit.fuel_tax_credit_id IS 'Primary key for a fuel-tax-credit estimate row.';
COMMENT ON COLUMN fuel_tax_credit.asset_id IS 'Asset consuming eligible fuel.';
COMMENT ON COLUMN fuel_tax_credit.month_start IS 'First day of the claim month.';
COMMENT ON COLUMN fuel_tax_credit.fuel_cost_cents IS 'Fuel cost used to estimate litres.';
COMMENT ON COLUMN fuel_tax_credit.diesel_price_estimate_cents_per_litre IS 'Diesel price assumption in cents per litre.';
COMMENT ON COLUMN fuel_tax_credit.litres IS 'Estimated eligible litres.';
COMMENT ON COLUMN fuel_tax_credit.ato_eligible_rate_cents_per_litre IS 'ATO eligible FTC rate in cents per litre.';
COMMENT ON COLUMN fuel_tax_credit.fuel_tax_credit_cents IS 'Estimated FTC amount in cents.';
COMMENT ON COLUMN fuel_tax_credit.note IS 'Reminder to update the placeholder rate from ATO guidance.';
COMMENT ON COLUMN fuel_tax_credit.created_at IS 'Timestamp when this row was loaded into the app database.';
COMMENT ON COLUMN fuel_tax_credit.updated_at IS 'Timestamp when this row was last updated in the app database.';

CREATE INDEX idx_fleet_register_asset_id ON fleet_register(asset_id);
CREATE INDEX idx_fleet_register_equipment_type ON fleet_register(equipment_type);
CREATE INDEX idx_job_master_job_id ON job_master(job_id);
CREATE INDEX idx_job_master_dates ON job_master(start_date, end_date);
CREATE INDEX idx_usage_log_job_id ON usage_log(job_id);
CREATE INDEX idx_usage_log_asset_id ON usage_log(asset_id);
CREATE INDEX idx_usage_log_usage_date ON usage_log(usage_date);
CREATE INDEX idx_job_rates_job_id ON job_rates(job_id);
CREATE INDEX idx_costs_job_id ON costs(job_id);
CREATE INDEX idx_costs_asset_id ON costs(asset_id);
CREATE INDEX idx_costs_cost_date ON costs(cost_date);
CREATE INDEX idx_costs_tax_code ON costs(tax_code);
CREATE INDEX idx_invoice_myob_job_id ON invoice_myob(job_id);
CREATE INDEX idx_invoice_myob_asset_id ON invoice_myob(asset_id);
CREATE INDEX idx_invoice_myob_invoice_date ON invoice_myob(invoice_date);
CREATE INDEX idx_invoice_myob_tax_code ON invoice_myob(tax_code);
CREATE INDEX idx_myob_gl_extract_period ON myob_gl_extract(period_start);
CREATE INDEX idx_myob_gl_extract_tax_code ON myob_gl_extract(tax_code);
CREATE INDEX idx_payroll_monthly_period ON payroll_monthly(month_start);
CREATE INDEX idx_payroll_monthly_tax_code ON payroll_monthly(tax_code);
CREATE INDEX idx_revenue_engine_job_id ON revenue_engine(job_id);
CREATE INDEX idx_revenue_engine_asset_id ON revenue_engine(asset_id);
CREATE INDEX idx_revenue_engine_usage_date ON revenue_engine(usage_date);
CREATE INDEX idx_revenue_engine_tax_code ON revenue_engine(tax_code);
CREATE INDEX idx_forecast_assumptions_period ON forecast_assumptions(period_start);
CREATE INDEX idx_forecast_assumptions_asset_id ON forecast_assumptions(asset_id);
CREATE INDEX idx_bas_check_period ON bas_check(period_start);
CREATE INDEX idx_payg_withholding_job_id ON payg_withholding(job_id);
CREATE INDEX idx_fuel_tax_credit_asset_id ON fuel_tax_credit(asset_id);
CREATE INDEX idx_fuel_tax_credit_period ON fuel_tax_credit(month_start);
CREATE INDEX idx_exception_log_job_id ON exception_log(job_id);
CREATE INDEX idx_exception_log_asset_id ON exception_log(asset_id);
