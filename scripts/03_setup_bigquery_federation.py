#!/usr/bin/env python3
"""Step 3: Provision BigQuery Federated Warehouse over Bigtable & Spanner Data Boost.

Creates in `<PROJECT_ID>.cymbal_payments_warehouse`:
- Table `issuer_baselines_90d` (90-day issuer baselines with fictitious UK/EU banks)
- External Table `acquired_payments_bigtable_ext` (Zero-ETL BigQuery over Cloud Bigtable)
- View `v_intelligent_acceptance_live_vs_baseline` (Demo 1 federated view)
- BigQuery Spanner Data Boost connection `cymbal-spanner-conn` (`useDataBoost=true`)
- Table `historical_fraud_and_kyc_dossiers` (12-month chargeback & KYC history)
- View `v_live_spanner_t0_fraud_ring_exposure` (Demo 2 federated view via EXTERNAL_QUERY)
"""

from __future__ import annotations

import subprocess
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import config  # noqa: E402


def run_bq_sql(token: str, sql: str, label: str) -> None:
    bq_base = f"https://bigquery.googleapis.com/bigquery/v2/projects/{config.PROJECT_ID}"
    st, jr = config.api_request(
        "POST",
        f"{bq_base}/jobs",
        token,
        body={
            "configuration": {
                "query": {
                    "query": sql,
                    "useLegacySql": False,
                    "defaultDataset": {
                        "projectId": config.PROJECT_ID,
                        "datasetId": config.BQ_DATASET,
                    },
                }
            }
        },
    )
    if st != 200 or not isinstance(jr, dict):
        print(f"  -> BQ {label} submit error (HTTP {st}): {jr}")
        return
    job_id = jr["jobReference"]["jobId"]
    for _ in range(30):
        _, poll = config.api_request(
            "GET", f"{bq_base}/jobs/{job_id}", token, params={"location": config.REGION}
        )
        if isinstance(poll, dict) and poll.get("status", {}).get("state") == "DONE":
            if "errorResult" in poll["status"]:
                print(f"  -> BQ {label} failed: {poll['status']['errorResult']}")
            else:
                print(f"  -> BQ {label} succeeded.")
            return
        time.sleep(1)


def main() -> None:
    token = config.get_access_token()
    pnum = config.get_project_number()
    bq_base = f"https://bigquery.googleapis.com/bigquery/v2/projects/{config.PROJECT_ID}"
    ds = config.BQ_DATASET
    proj = config.PROJECT_ID

    print(f"=== Step 3: BigQuery Federated Warehouse ({proj}.{ds}) ===")

    # 1. Create BigQuery dataset
    st_ds, resp_ds = config.api_request(
        "POST",
        f"{bq_base}/datasets",
        token,
        body={
            "datasetReference": {"projectId": proj, "datasetId": ds},
            "location": config.REGION,
            "description": (
                "Cymbal Payments Unified Warehouse (BigQuery + Zero-ETL Bigtable & "
                "Spanner Data Boost Federation)"
            ),
        },
    )
    print(f"  -> Dataset {ds} ready (HTTP {st_ds})." if st_ds in (200, 409) else f"  -> Dataset error: {resp_ds}")

    # 2. Create BigQuery Spanner Data Boost external connection
    conn_url = (
        f"https://bigqueryconnection.googleapis.com/v1/projects/{proj}"
        f"/locations/{config.REGION}/connections"
    )
    st_c, resp_c = config.api_request(
        "POST",
        conn_url,
        token,
        params={"connectionId": config.BQ_SPANNER_CONN},
        body={
            "friendlyName": "Cymbal Payments Spanner Data Boost Connection",
            "description": (
                f"Serverless Spanner Data Boost connection to {config.SPANNER_INSTANCE}/{config.SPANNER_DB}"
            ),
            "cloudSpanner": {
                "database": (
                    f"projects/{proj}/instances/{config.SPANNER_INSTANCE}"
                    f"/databases/{config.SPANNER_DB}"
                ),
                "useParallelism": True,
                "useDataBoost": True,
            },
        },
    )
    print(
        f"  -> Spanner Data Boost connection {config.BQ_SPANNER_CONN} ready (HTTP {st_c})."
        if st_c in (200, 409)
        else f"  -> Connection warning (HTTP {st_c}): {resp_c}"
    )

    # Grant roles/spanner.databaseReader to the BigQuery Connection Service Agent
    subprocess.run(
        [
            config.GCLOUD_BIN,
            "projects",
            "add-iam-policy-binding",
            proj,
            f"--member=serviceAccount:service-{pnum}@gcp-sa-bigqueryconnection.iam.gserviceaccount.com",
            "--role=roles/spanner.databaseReader",
            "--quiet",
        ],
        capture_output=True,
    )

    # 3. 90-day issuer authorization baselines table (fictitious banks)
    sql_baselines = f"""
    CREATE OR REPLACE TABLE `{proj}.{ds}.issuer_baselines_90d` AS
    SELECT '4532' AS issuer_bin, 'Albion Bank UK' AS issuer_bank, 'VISA' AS card_scheme, 'GB' AS country,
           0.942 AS baseline_90d_pan_auth_rate, 0.965 AS baseline_90d_network_token_auth_rate,
           2250000.0 AS daily_gmv_gbp, 0.0185 AS false_decline_baseline_rate,
           'HIGH_NETWORK_TOKEN_AFFINITY' AS issuer_behavior_profile
    UNION ALL
    SELECT '5412', 'Thames Commercial Bank', 'MASTERCARD', 'GB', 0.940, 0.968, 1840000.0, 0.0190, 'STANDARD_EMV_3DS2'
    UNION ALL
    SELECT '4929', 'Crown & Sterling Bank', 'VISA', 'GB', 0.937, 0.961, 1620000.0, 0.0210, 'TRA_EXEMPTION_PREFERRED'
    UNION ALL
    SELECT '4024', 'Banque Lumiere FR', 'CARTES_BANCAIRES', 'FR', 0.948, 0.972, 2100000.0, 0.0150, 'LOCAL_RAIL_CARTES_BANCAIRES'
    UNION ALL
    SELECT '5200', 'Rheinland Bank DE', 'MASTERCARD', 'DE', 0.944, 0.969, 1490000.0, 0.0175, 'STRICT_SCA_ENFORCEMENT';
    """
    run_bq_sql(token, sql_baselines, "issuer_baselines_90d")

    # 4. Zero-ETL BigQuery External Table over Cloud Bigtable
    ext_table_body = {
        "tableReference": {
            "projectId": proj,
            "datasetId": ds,
            "tableId": "acquired_payments_bigtable_ext",
        },
        "description": (
            f"Zero-ETL BigQuery External Table over Cloud Bigtable ({config.BT_INSTANCE} / acquired_payments_live)"
        ),
        "externalDataConfiguration": {
            "sourceFormat": "BIGTABLE",
            "sourceUris": [
                f"https://googleapis.com/bigtable/projects/{proj}/instances/{config.BT_INSTANCE}/tables/acquired_payments_live"
            ],
            "bigtableOptions": {
                "readRowkeyAsString": True,
                "columnFamilies": [
                    {
                        "familyId": "tx",
                        "onlyReadLatest": True,
                        "columns": [
                            {"qualifierString": c, "fieldName": c, "type": "STRING"}
                            for c in (
                                "merchant_id", "merchant_name", "country", "currency",
                                "amount", "auth_status", "decline_code", "decline_reason",
                                "credential_type", "three_ds_mode", "event_timestamp",
                            )
                        ],
                    },
                    {
                        "familyId": "issuer",
                        "onlyReadLatest": True,
                        "columns": [
                            {"qualifierString": c, "fieldName": c, "type": "STRING"}
                            for c in ("issuer_bin", "issuer_bank", "card_scheme")
                        ],
                    },
                    {
                        "familyId": "routing",
                        "onlyReadLatest": True,
                        "columns": [
                            {"qualifierString": c, "fieldName": c, "type": "STRING"}
                            for c in ("gateway_region", "p99_latency_ms", "intelligent_retry_eligible")
                        ],
                    },
                ],
            },
        },
    }
    config.api_request("DELETE", f"{bq_base}/datasets/{ds}/tables/acquired_payments_bigtable_ext", token)
    st_et, resp_et = config.api_request("POST", f"{bq_base}/datasets/{ds}/tables", token, body=ext_table_body)
    print(
        f"  -> External Table acquired_payments_bigtable_ext ready (HTTP {st_et})."
        if st_et in (200, 409)
        else f"  -> External Table error: {resp_et}"
    )

    # 5. Demo 1 Federated View (Bigtable External Table + 90-day BigQuery Baselines)
    sql_bt_view = f"""
    CREATE OR REPLACE VIEW `{proj}.{ds}.v_intelligent_acceptance_live_vs_baseline` AS
    WITH live_bt AS (
      SELECT
        issuer.issuer_bin.cell.value AS issuer_bin,
        issuer.issuer_bank.cell.value AS issuer_bank,
        issuer.card_scheme.cell.value AS card_scheme,
        tx.merchant_id.cell.value AS merchant_id,
        tx.merchant_name.cell.value AS merchant_name,
        tx.credential_type.cell.value AS credential_type,
        COUNT(*) AS live_tx_count,
        ROUND(AVG(CASE WHEN tx.auth_status.cell.value = 'APPROVED' THEN 1.0 ELSE 0.0 END), 4) AS live_auth_rate,
        SUM(CASE WHEN tx.decline_code.cell.value = '05' THEN 1 ELSE 0 END) AS soft_decline_05_count,
        ROUND(AVG(CAST(routing.p99_latency_ms.cell.value AS FLOAT64)), 2) AS avg_bt_latency_ms
      FROM `{proj}.{ds}.acquired_payments_bigtable_ext`
      GROUP BY 1, 2, 3, 4, 5, 6
    )
    SELECT
      l.merchant_id,
      l.merchant_name,
      l.issuer_bin,
      l.issuer_bank,
      l.card_scheme,
      l.credential_type,
      l.live_tx_count,
      l.live_auth_rate,
      CASE
        WHEN l.credential_type = 'RAW_PAN' THEN b.baseline_90d_pan_auth_rate
        ELSE b.baseline_90d_network_token_auth_rate
      END AS historical_90d_auth_rate,
      ROUND((l.live_auth_rate - CASE WHEN l.credential_type = 'RAW_PAN' THEN b.baseline_90d_pan_auth_rate ELSE b.baseline_90d_network_token_auth_rate END) * 10000, 0) AS auth_rate_delta_bps,
      l.soft_decline_05_count,
      l.avg_bt_latency_ms,
      b.daily_gmv_gbp,
      ROUND(
        CASE
          WHEN l.credential_type = 'RAW_PAN' AND l.live_auth_rate < b.baseline_90d_pan_auth_rate
          THEN b.daily_gmv_gbp * (b.baseline_90d_network_token_auth_rate - l.live_auth_rate)
          ELSE 0.0
        END, 0
      ) AS daily_false_decline_gmv_at_risk_gbp,
      CASE
        WHEN l.issuer_bin = '4532' AND l.credential_type = 'RAW_PAN'
        THEN 'FORCE_NETWORK_TOKEN_AND_TRA_EXEMPTION (Expected +1,890 bps uplift)'
        ELSE 'KEEP_CURRENT_NETWORK_TOKEN_ROUTING'
      END AS recommended_intelligent_acceptance_action
    FROM live_bt l
    JOIN `{proj}.{ds}.issuer_baselines_90d` b
      ON l.issuer_bin = b.issuer_bin;
    """
    run_bq_sql(token, sql_bt_view, "v_intelligent_acceptance_live_vs_baseline")

    # 6. Historical Fraud & KYC Dossiers table for Demo 2
    sql_fraud_history = f"""
    CREATE OR REPLACE TABLE `{proj}.{ds}.historical_fraud_and_kyc_dossiers` AS
    SELECT
      'subm_apex_uk' AS merchant_id,
      'Apex Digital Ltd (UK)' AS merchant_name,
      'AE47033120000099887766' AS linked_ubo_iban,
      'Zentra Holdings FZE' AS beneficial_owner_entity,
      'Q3_SYNTHETIC_TRIANGULATION_RING' AS matched_historical_fraud_pattern,
      0.987 AS pattern_similarity_confidence,
      480000.0 AS total_cluster_t0_exposure_eur,
      'Sub-merchant onboarded Aug 2026 under standard tier; shares 6 headless browser device fingerprints (AS9009 proxy pool) and routes T+0 Cymbal Acceleration settlement to the same Dubai UBO IBAN as Nova Goods SARL and Veloce Trade GmbH.' AS kyp_agent_dossier_summary
    UNION ALL
    SELECT
      'subm_nova_fr',
      'Nova Goods SARL (FR)',
      'AE47033120000099887766',
      'Zentra Holdings FZE',
      'Q3_SYNTHETIC_TRIANGULATION_RING',
      0.987,
      480000.0,
      'Sub-merchant onboarded 5 days after Apex Digital; 24 Cyprus-issued prepaid cards cycle between Apex Digital, Nova Goods, and Veloce Trade to stay under tabular velocity thresholds.'
    UNION ALL
    SELECT
      'subm_veloce_de',
      'Veloce Trade GmbH (DE)',
      'AE47033120000099887766',
      'Zentra Holdings FZE',
      'Q3_SYNTHETIC_TRIANGULATION_RING',
      0.987,
      480000.0,
      'Third node in synthetic triangulation ring; simultaneous weekend €157K T+0 Cymbal Acceleration payout request triggered within 14 minutes of Apex and Nova.'
    UNION ALL
    SELECT
      'subm_cymbal_uk',
      'Cymbal Retail UK',
      'GB29NWBK60161331926819',
      'Cymbal Retail Group PLC',
      'NONE_CLEAN_ENTERPRISE',
      0.010,
      0.0,
      'Verified Tier-1 Enterprise merchant since Jan 2023; isolated consumer device graph and dedicated UK corporate settlement account.';
    """
    run_bq_sql(token, sql_fraud_history, "historical_fraud_and_kyc_dossiers")

    # 7. Demo 2 Federated View (Spanner Data Boost EXTERNAL_QUERY + 12-Month Chargeback Dossiers)
    conn_fqn = f"{proj}.{config.REGION}.{config.BQ_SPANNER_CONN}"
    sql_spanner_view = f"""
    CREATE OR REPLACE VIEW `{proj}.{ds}.v_live_spanner_t0_fraud_ring_exposure` AS
    WITH sp_merchants AS (
      SELECT * FROM EXTERNAL_QUERY('{conn_fqn}', 'SELECT merchant_id, merchant_name, jurisdiction, risk_status FROM SubMerchants')
    ),
    sp_reqs AS (
      SELECT * FROM EXTERNAL_QUERY('{conn_fqn}', 'SELECT payout_req_id, merchant_id, payout_account_id, requested_amount_eur, settlement_rail, payout_status FROM AccelerationPayoutRequests')
    ),
    sp_accounts AS (
      SELECT * FROM EXTERNAL_QUERY('{conn_fqn}', 'SELECT payout_account_id, iban_or_wallet, beneficial_owner_name, ubo_risk_flag FROM PayoutAccounts')
    ),
    sp_payments AS (
      SELECT * FROM EXTERNAL_QUERY('{conn_fqn}', 'SELECT payment_id, card_token, merchant_id, device_fingerprint, row_fraud_score FROM CardPayments')
    )
    SELECT
      m.merchant_id,
      m.merchant_name,
      m.jurisdiction,
      r.requested_amount_eur,
      r.requested_amount_eur AS requested_t0_payout_eur,
      r.settlement_rail,
      r.payout_status,
      p.iban_or_wallet,
      p.iban_or_wallet AS shared_ubo_iban,
      p.beneficial_owner_name,
      COUNT(DISTINCT cp.card_token) AS cycled_cards,
      COUNT(DISTINCT cp.card_token) AS cycled_prepaid_cards,
      COUNT(DISTINCT cp.device_fingerprint) AS shared_devices,
      COUNT(DISTINCT cp.device_fingerprint) AS shared_headless_devices,
      ROUND(AVG(cp.row_fraud_score), 2) AS avg_row_score,
      ROUND(AVG(cp.row_fraud_score), 2) AS tabular_fraud_score,
      h.matched_historical_fraud_pattern,
      ROUND(h.pattern_similarity_confidence * 100, 1) AS historical_ring_match_confidence,
      CASE
        WHEN m.merchant_id = 'subm_apex_uk' THEN 135000.0
        WHEN m.merchant_id = 'subm_nova_fr' THEN 125000.0
        ELSE 115000.0
      END AS prior_chargeback_loss_eur,
      'IMMEDIATE_T0_QUARANTINE_AND_FREEZE' AS recommended_ledger_action,
      h.kyp_agent_dossier_summary
    FROM sp_merchants m
    JOIN sp_reqs r ON m.merchant_id = r.merchant_id
    JOIN sp_accounts p ON r.payout_account_id = p.payout_account_id
    JOIN sp_payments cp ON m.merchant_id = cp.merchant_id
    LEFT JOIN `{proj}.{ds}.historical_fraud_and_kyc_dossiers` h
      ON m.merchant_id = h.merchant_id
    WHERE p.ubo_risk_flag = 'HIGH_VELOCITY_SHARED_UBO'
    GROUP BY
      m.merchant_id, m.merchant_name, m.jurisdiction,
      r.requested_amount_eur, r.settlement_rail, r.payout_status,
      p.iban_or_wallet, p.beneficial_owner_name,
      h.matched_historical_fraud_pattern, h.pattern_similarity_confidence,
      h.kyp_agent_dossier_summary
    ORDER BY r.requested_amount_eur DESC;
    """
    run_bq_sql(token, sql_spanner_view, "v_live_spanner_t0_fraud_ring_exposure")
    print("Done! Open BigQuery Studio and run queries from data/sql/bigquery_federated_queries.sql.")


if __name__ == "__main__":
    main()
