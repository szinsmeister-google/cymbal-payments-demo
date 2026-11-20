-- ==============================================================================
-- BigQuery Studio Federated Queries (Zero-ETL Bigtable & Spanner Data Boost)
-- Replace <PROJECT_ID> with your Google Cloud Project ID.
-- ==============================================================================

-- Demo 1 (BigQuery + Bigtable External Table):
-- Joins live Bigtable swipes (`acquired_payments_bigtable_ext`) against 90-day baselines (`issuer_baselines_90d`)
SELECT
  issuer_bank,
  issuer_bin,
  credential_type,
  ROUND(live_auth_rate * 100, 1) AS bt_live_auth_pct,
  ROUND(historical_90d_auth_rate * 100, 1) AS bq_90d_baseline_pct,
  auth_rate_delta_bps,
  soft_decline_05_count,
  daily_false_decline_gmv_at_risk_gbp,
  recommended_intelligent_acceptance_action
FROM `<PROJECT_ID>.cymbal_payments_warehouse.v_intelligent_acceptance_live_vs_baseline`
WHERE issuer_bin = '4532'
ORDER BY credential_type DESC;

-- Demo 2 (BigQuery + Spanner Data Boost EXTERNAL_QUERY):
-- Joins live Spanner T+0 payout state (on isolated serverless Data Boost compute, 0% OLTP CPU impact)
-- against 12 months of historical BigQuery chargeback dossiers (`€375,000` prior syndicate loss).
SELECT
  merchant_name,
  jurisdiction,
  requested_t0_payout_eur,
  tabular_fraud_score,
  cycled_prepaid_cards,
  shared_headless_devices,
  shared_ubo_iban,
  prior_chargeback_loss_eur,
  recommended_ledger_action
FROM `<PROJECT_ID>.cymbal_payments_warehouse.v_live_spanner_t0_fraud_ring_exposure`
ORDER BY requested_t0_payout_eur DESC;
