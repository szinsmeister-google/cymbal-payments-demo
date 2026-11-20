-- ==============================================================================
-- Demo 1: Cloud Bigtable Studio (BTQL) Query Bank
-- Instance: cymbal-payments-prod
-- ==============================================================================

-- 1. Inspect the active Intelligent Acceptance routing rule for Albion Bank UK (BIN 4532)
--    Shows whether force_network_token is currently 'false' (RAW_PAN) or 'true' (NETWORK_TOKEN).
SELECT
  CAST(_key AS STRING) AS rule_key,
  CAST(rule['issuer_bank'] AS STRING) AS issuer_bank,
  CAST(rule['force_network_token'] AS STRING) AS force_network_token,
  CAST(rule['expected_uplift_bps'] AS STRING) AS expected_uplift_bps,
  CAST(audit['updated_by'] AS STRING) AS updated_by,
  CAST(audit['last_updated'] AS STRING) AS last_updated
FROM intelligent_acceptance_rules
WHERE _key = 'cymbal_retail_uk#4532';

-- 2. Verify live Checkout App writes in acquired_payments_live (replace <ROW_KEY> with the pill copied from the app)
SELECT
  CAST(_key AS STRING) AS row_key,
  CAST(tx['auth_status'] AS STRING) AS auth_status,
  CAST(tx['decline_code'] AS STRING) AS decline_code,
  CAST(tx['credential_type'] AS STRING) AS credential_type,
  CAST(tx['amount'] AS STRING) AS amount_gbp,
  CAST(routing['p99_latency_ms'] AS STRING) AS p99_latency_ms
FROM acquired_payments_live
WHERE _key LIKE 'cymbal_retail_uk#4532#%#tx_live_%'
LIMIT 10;

-- 3. Query the Logical View (v_acquired_payments_btql) for UK Issuer Approval Rate Breakdown
SELECT
  issuer_bin,
  issuer_bank,
  credential_type,
  COUNT(1) AS attempts,
  SUM(CASE WHEN auth_status = 'APPROVED' THEN 1 ELSE 0 END) AS approved,
  SUM(CASE WHEN decline_code = '05' THEN 1 ELSE 0 END) AS soft_decline_05,
  ROUND(SUM(CASE WHEN auth_status = 'APPROVED' THEN 1 ELSE 0 END) * 100.0 / COUNT(1), 1) AS approval_rate_pct
FROM v_acquired_payments_btql
WHERE merchant_id = 'cymbal_retail_uk'
GROUP BY issuer_bin, issuer_bank, credential_type
ORDER BY issuer_bin, credential_type;

-- 4. Query the Continuous Materialized View (cmv_bin_acceptance_rollup) for sub-5ms pre-aggregated telemetry
SELECT
  issuer_bin,
  issuer_bank,
  credential_type,
  auth_status,
  decline_code,
  tx_count
FROM cmv_bin_acceptance_rollup
WHERE issuer_bin = '4532'
ORDER BY credential_type, auth_status;
