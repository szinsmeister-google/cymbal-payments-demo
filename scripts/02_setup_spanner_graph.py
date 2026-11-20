#!/usr/bin/env python3
"""Step 2: Provision & seed Cloud Spanner Graph for Demo 2 (Zero-ETL Fraud Rings).

Creates:
- Cloud Spanner instance `cymbal-payments-graph` (100 Processing Units, Standard Edition)
- Database `settlement_and_fraud_db` with relational tables + Property Graph
  `cymbal_fraud_and_settlement_graph` (from `data/spanner/schema.sql`)
- Deterministic seed data:
  * 3 collusive European sub-merchants (Apex Digital UK, Nova Goods FR, Veloce Trade DE)
    requesting €480,000 in T+0 payouts into 1 shared Dubai UBO IBAN (Zentra Holdings FZE),
    cycling 24 Cyprus prepaid cards across 6 headless proxy devices with 0.12 row fraud score.
  * 4 clean Tier-1 enterprise merchants for realistic contrast.
"""

from __future__ import annotations

import datetime
import subprocess
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import config  # noqa: E402

SCHEMA_PATH = config.REPO_ROOT / "data" / "spanner" / "schema.sql"


def main() -> None:
    token = config.get_access_token()
    print(
        f"=== Step 2: Cloud Spanner Graph ({config.PROJECT_ID} / "
        f"{config.SPANNER_INSTANCE} / {config.SPANNER_DB}) ==="
    )

    # 1. Create Spanner instance (100 PU regional config)
    inst_cmd = [
        config.GCLOUD_BIN,
        "spanner",
        "instances",
        "create",
        config.SPANNER_INSTANCE,
        f"--project={config.PROJECT_ID}",
        f"--config=regional-{config.REGION}",
        "--description=Cymbal Payments T+0 Settlement & Spanner Graph",
        "--processing-units=100",
        "--edition=STANDARD",
    ]
    res_inst = subprocess.run(inst_cmd, capture_output=True, text=True)
    if res_inst.returncode == 0:
        print(f"  -> Created Spanner instance {config.SPANNER_INSTANCE}.")
    elif "ALREADY_EXISTS" in res_inst.stderr or "already exists" in res_inst.stderr.lower():
        print(f"  -> Spanner instance {config.SPANNER_INSTANCE} already exists.")
    else:
        print("  -> Spanner instance output:", res_inst.stderr.strip()[:400])

    # 2. Create database + relational schema + Property Graph
    db_cmd = [
        config.GCLOUD_BIN,
        "spanner",
        "databases",
        "create",
        config.SPANNER_DB,
        f"--instance={config.SPANNER_INSTANCE}",
        f"--project={config.PROJECT_ID}",
        f"--ddl-file={SCHEMA_PATH}",
    ]
    res_db = subprocess.run(db_cmd, capture_output=True, text=True)
    if res_db.returncode == 0:
        print(f"  -> Created database {config.SPANNER_DB} with Property Graph {config.SPANNER_GRAPH}.")
    elif "ALREADY_EXISTS" in res_db.stderr or "already exists" in res_db.stderr.lower():
        print(f"  -> Database {config.SPANNER_DB} already exists.")
    else:
        print("  -> Database create output:", res_db.stderr.strip()[:400])

    # 3. Seed relational nodes and edges via Spanner REST Session + commit
    db_uri = (
        f"https://spanner.googleapis.com/v1/projects/{config.PROJECT_ID}"
        f"/instances/{config.SPANNER_INSTANCE}/databases/{config.SPANNER_DB}"
    )
    st_s, s_resp = config.api_request("POST", f"{db_uri}/sessions", token, body={})
    if st_s != 200 or not isinstance(s_resp, dict):
        raise RuntimeError(f"Failed to create Spanner session (HTTP {st_s}): {s_resp}")
    session_name = s_resp["name"]

    try:
        now_iso = datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

        submerchants = [
            # Collusive Fraud Ring (€480,000 combined T+0 exposure)
            ["subm_apex_uk", "Apex Digital Ltd (UK)", "GB", "5815", "TIER_2_STANDARD", "2026-08-14", True, "UNDER_GRAPH_REVIEW", 165000.0],
            ["subm_nova_fr", "Nova Goods SARL (FR)", "FR", "5999", "TIER_2_STANDARD", "2026-08-19", True, "UNDER_GRAPH_REVIEW", 158000.0],
            ["subm_veloce_de", "Veloce Trade GmbH (DE)", "DE", "5732", "TIER_2_STANDARD", "2026-08-22", True, "UNDER_GRAPH_REVIEW", 157000.0],
            # Clean Tier-1 Enterprise Merchants
            ["subm_cymbal_uk", "Cymbal Retail UK", "GB", "5651", "TIER_1_ENTERPRISE", "2023-01-10", True, "CLEAN_VERIFIED", 420000.0],
            ["subm_lumiere_fr", "Lumiere Luxe Paris", "FR", "5621", "TIER_1_ENTERPRISE", "2024-03-15", True, "CLEAN_VERIFIED", 290000.0],
            ["subm_nordic_se", "Nordic Outdoor AB", "SE", "5941", "TIER_1_ENTERPRISE", "2024-06-01", True, "CLEAN_VERIFIED", 185000.0],
            ["subm_iberian_es", "Iberian Travel Group", "ES", "4722", "TIER_1_ENTERPRISE", "2023-11-20", True, "CLEAN_VERIFIED", 310000.0],
        ]

        payout_accounts = [
            ["payout_ubo_mule_99", "AE47033120000099887766", "Zentra Holdings FZE (Shared UBO)", "AE", "HIGH_VELOCITY_SHARED_UBO"],
            ["payout_cymbal_01", "GB29NWBK60161331926819", "Cymbal Retail Group PLC", "GB", "VERIFIED_CORPORATE"],
            ["payout_lumiere_01", "FR7630006000011234567890189", "Lumiere Luxe SA", "FR", "VERIFIED_CORPORATE"],
            ["payout_nordic_01", "SE4550000000058398257466", "Nordic Outdoor AB", "SE", "VERIFIED_CORPORATE"],
            ["payout_iberian_01", "ES9121000418450200051332", "Iberian Travel SL", "ES", "VERIFIED_CORPORATE"],
        ]

        devices = [
            [f"dev_fp_ring_88a{i}", "AS9009_M247_PROXY_POOL", "HeadlessChrome/129.0", True, 3]
            for i in range(1, 7)
        ] + [
            [f"dev_fp_clean_10{i}", "AS2856_RESIDENTIAL_UK", "MobileSafari/18.0", False, 1]
            for i in range(1, 9)
        ]

        cards = []
        card_payments = []
        device_usages = []
        ring_merchants = ["subm_apex_uk", "subm_nova_fr", "subm_veloce_de"]
        pay_idx = 5000

        # 24 synthetic Cyprus prepaid cards cycled across the 6 headless devices & 3 ring merchants
        for c_i in range(1, 25):
            c_tok = f"card_tok_ring_{c_i:03d}"
            cards.append([c_tok, "453299", "VISA", "CY", True])
            dev_fp = f"dev_fp_ring_88a{((c_i - 1) % 6) + 1}"
            device_usages.append([c_tok, dev_fp, 4, now_iso])
            for m_offset in range(2):
                pay_idx += 1
                m_id = ring_merchants[(c_i + m_offset) % 3]
                card_payments.append([
                    f"pay_ring_{pay_idx}",
                    c_tok,
                    m_id,
                    dev_fp,
                    120.0 + (c_i % 5),
                    0.12,  # Low isolated tabular fraud score
                    "CAPTURED",
                    now_iso,
                ])

        # 16 clean customer cards for legitimate merchants
        clean_merchants = ["subm_cymbal_uk", "subm_lumiere_fr", "subm_nordic_se", "subm_iberian_es"]
        for c_i in range(1, 17):
            c_tok = f"card_tok_clean_{c_i:03d}"
            cards.append([c_tok, "453201", "VISA", "GB", False])
            dev_fp = f"dev_fp_clean_10{((c_i - 1) % 8) + 1}"
            device_usages.append([c_tok, dev_fp, 1, now_iso])
            pay_idx += 1
            m_id = clean_merchants[(c_i - 1) % 4]
            card_payments.append([
                f"pay_clean_{pay_idx}",
                c_tok,
                m_id,
                dev_fp,
                89.50,
                0.03,
                "CAPTURED",
                now_iso,
            ])

        payout_requests = [
            ["t0_req_901", "subm_apex_uk", "payout_ubo_mule_99", 165000.0, "ACCELERATION_T0_USDC", "PENDING_GRAPH_GATE", now_iso],
            ["t0_req_902", "subm_nova_fr", "payout_ubo_mule_99", 158000.0, "ACCELERATION_T0_SEPA_INST", "PENDING_GRAPH_GATE", now_iso],
            ["t0_req_903", "subm_veloce_de", "payout_ubo_mule_99", 157000.0, "ACCELERATION_T0_SEPA_INST", "PENDING_GRAPH_GATE", now_iso],
            ["t0_req_801", "subm_cymbal_uk", "payout_cymbal_01", 420000.0, "ACCELERATION_T0_FPS", "SETTLED_T0", now_iso],
            ["t0_req_802", "subm_lumiere_fr", "payout_lumiere_01", 290000.0, "ACCELERATION_T0_SEPA_INST", "SETTLED_T0", now_iso],
        ]

        mutations = [
            {
                "insertOrUpdate": {
                    "table": "SubMerchants",
                    "columns": [
                        "merchant_id", "merchant_name", "jurisdiction", "mcc_code",
                        "kyc_tier", "onboarding_date", "acceleration_t0_enabled",
                        "risk_status", "pending_t0_payout_eur",
                    ],
                    "values": [[x if isinstance(x, (bool, float)) else str(x) for x in r] for r in submerchants],
                }
            },
            {
                "insertOrUpdate": {
                    "table": "PayoutAccounts",
                    "columns": ["payout_account_id", "iban_or_wallet", "beneficial_owner_name", "bank_country", "ubo_risk_flag"],
                    "values": payout_accounts,
                }
            },
            {
                "insertOrUpdate": {
                    "table": "Devices",
                    "columns": ["device_fingerprint", "ip_asn", "user_agent_family", "emulator_detected", "shared_merchant_count"],
                    "values": [[x if isinstance(x, bool) else str(x) for x in r] for r in devices],
                }
            },
            {
                "insertOrUpdate": {
                    "table": "PaymentCards",
                    "columns": ["card_token", "issuer_bin", "card_scheme", "issuing_country", "is_prepaid"],
                    "values": [[x if isinstance(x, bool) else str(x) for x in r] for r in cards],
                }
            },
            {
                "insertOrUpdate": {
                    "table": "DeviceUsages",
                    "columns": ["card_token", "device_fingerprint", "session_count", "first_seen_ts"],
                    "values": [[str(x) for x in r] for r in device_usages],
                }
            },
            {
                "insertOrUpdate": {
                    "table": "CardPayments",
                    "columns": [
                        "payment_id", "card_token", "merchant_id", "device_fingerprint",
                        "amount_eur", "row_fraud_score", "tx_status", "tx_timestamp",
                    ],
                    "values": [[x if isinstance(x, float) else str(x) for x in r] for r in card_payments],
                }
            },
            {
                "insertOrUpdate": {
                    "table": "AccelerationPayoutRequests",
                    "columns": [
                        "payout_req_id", "merchant_id", "payout_account_id",
                        "requested_amount_eur", "settlement_rail", "payout_status", "requested_ts",
                    ],
                    "values": [[x if isinstance(x, float) else str(x) for x in r] for r in payout_requests],
                }
            },
        ]

        st_c, resp_c = config.api_request(
            "POST",
            f"https://spanner.googleapis.com/v1/{session_name}:commit",
            token,
            body={"singleUseTransaction": {"readWrite": {}}, "mutations": mutations},
        )
        if st_c == 200:
            print(f"  -> Seeded Spanner Graph nodes & edges! Commit timestamp: {resp_c.get('commitTimestamp')}")
        else:
            print(f"  -> Error committing Spanner seed data (HTTP {st_c}): {resp_c}")
    finally:
        config.api_request("DELETE", f"https://spanner.googleapis.com/v1/{session_name}", token)

    print("Done! Open Spanner Graph Studio and run Query 1.3 from data/sql/spanner_gql_queries.sql.")


if __name__ == "__main__":
    main()
