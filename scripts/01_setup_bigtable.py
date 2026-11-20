#!/usr/bin/env python3
"""Step 1: Provision & seed Cloud Bigtable for Demo 1 (Intelligent Acceptance).

Creates:
- Cloud Bigtable instance `cymbal-payments-prod` (1-node SSD cluster)
- Table `acquired_payments_live` (460 deterministic synthetic payment rows)
- Table `intelligent_acceptance_rules` (5 live issuer BIN routing rules)
- Logical View `v_acquired_payments_btql`
- Continuous Materialized View `cmv_bin_acceptance_rollup`
"""

from __future__ import annotations

import base64
import datetime
import random
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import config  # noqa: E402


def b64e(text: str) -> str:
    return base64.b64encode(text.encode("utf-8")).decode("ascii")


def main() -> None:
    token = config.get_access_token()
    bt_proj = f"https://bigtableadmin.googleapis.com/v2/projects/{config.PROJECT_ID}"
    base_admin = f"{bt_proj}/instances/{config.BT_INSTANCE}"
    base_data = (
        f"https://bigtable.googleapis.com/v2/projects/{config.PROJECT_ID}"
        f"/instances/{config.BT_INSTANCE}/tables"
    )

    print(f"=== Step 1: Cloud Bigtable ({config.PROJECT_ID} / {config.BT_INSTANCE}) ===")

    # 1. Create Bigtable instance
    st, resp = config.api_request(
        "POST",
        f"{bt_proj}/instances",
        token,
        body={
            "parent": f"projects/{config.PROJECT_ID}",
            "instanceId": config.BT_INSTANCE,
            "instance": {
                "displayName": "Cymbal Payments Acquiring",
                "type": "PRODUCTION",
                "labels": {"app": "cymbal-payments", "tier": "acquiring-prod"},
            },
            "clusters": {
                config.BT_CLUSTER: {
                    "location": f"projects/{config.PROJECT_ID}/locations/{config.ZONE}",
                    "serveNodes": 1,
                    "defaultStorageType": "SSD",
                }
            },
        },
    )
    if st in (200, 409):
        print(f"  -> Instance {config.BT_INSTANCE} ready (HTTP {st}).")
        if st == 200:
            time.sleep(5)
    else:
        print(f"  -> Instance creation warning (HTTP {st}): {resp}")

    # 2. Create tables
    for table_id, families in [
        ("acquired_payments_live", {"tx": {}, "issuer": {}, "routing": {}}),
        ("intelligent_acceptance_rules", {"rule": {}, "audit": {}}),
    ]:
        st_t, resp_t = config.api_request(
            "POST",
            f"{base_admin}/tables",
            token,
            params={"tableId": table_id},
            body={"tableId": table_id, "table": {"columnFamilies": families}},
        )
        status_note = "ready" if st_t in (200, 409) else f"error: {resp_t}"
        print(f"  -> Table {table_id} (HTTP {st_t}): {status_note}")

    # 3. Seed 460 synthetic rows into acquired_payments_live using fictitious banks
    bins = [
        # Hero BIN 4532: Albion Bank UK drops to ~77.8% on RAW_PAN due to Soft Decline Code 05,
        # while EMVCo NETWORK_TOKEN clears at ~96.7% (+1,890 bps uplift).
        {
            "bin": "4532",
            "bank": "Albion Bank UK",
            "scheme": "VISA",
            "country": "GB",
            "pan_auth_rate": 0.778,
            "nt_auth_rate": 0.967,
        },
        {
            "bin": "5412",
            "bank": "Thames Commercial Bank",
            "scheme": "MASTERCARD",
            "country": "GB",
            "pan_auth_rate": 0.942,
            "nt_auth_rate": 0.960,
        },
        {
            "bin": "4929",
            "bank": "Crown & Sterling Bank",
            "scheme": "VISA",
            "country": "GB",
            "pan_auth_rate": 0.938,
            "nt_auth_rate": 0.961,
        },
        {
            "bin": "4024",
            "bank": "Banque Lumiere FR",
            "scheme": "CARTES_BANCAIRES",
            "country": "FR",
            "pan_auth_rate": 0.949,
            "nt_auth_rate": 0.972,
        },
        {
            "bin": "5200",
            "bank": "Rheinland Bank DE",
            "scheme": "MASTERCARD",
            "country": "DE",
            "pan_auth_rate": 0.945,
            "nt_auth_rate": 0.969,
        },
    ]

    now_ts = int(time.time())
    random.seed(42)
    entries = []
    tx_counter = 10000

    for b in bins:
        count_per_mode = 90 if b["bin"] == "4532" else 35
        for cred_type in ("RAW_PAN", "NETWORK_TOKEN"):
            target_rate = b["pan_auth_rate"] if cred_type == "RAW_PAN" else b["nt_auth_rate"]
            approved_target = int(round(count_per_mode * target_rate))
            for i in range(count_per_mode):
                tx_counter += 1
                is_approved = i < approved_target
                auth_status = "APPROVED" if is_approved else "DECLINED"
                if is_approved:
                    decline_code = "00"
                    decline_reason = "Approved"
                elif b["bin"] == "4532" and cred_type == "RAW_PAN":
                    if (i - approved_target) < int((count_per_mode - approved_target) * 0.85):
                        decline_code = "05"
                        decline_reason = "Do Not Honor (Issuer Soft Decline)"
                    else:
                        decline_code = "51"
                        decline_reason = "Insufficient Funds"
                else:
                    decline_code = random.choice(["51", "05", "65"])
                    decline_reason = {
                        "51": "Insufficient Funds",
                        "05": "Do Not Honor (Issuer Soft Decline)",
                        "65": "Soft Decline - 3DS Authentication Required",
                    }[decline_code]

                offset_sec = random.randint(1, 600)
                ev_ts = now_ts - offset_sec
                rev_ts = 9999999999 - ev_ts
                merchant_id = "cymbal_retail_uk" if b["country"] == "GB" else "cymbal_eu_marketplace"
                merchant_name = (
                    "Cymbal Retail UK" if b["country"] == "GB" else "Cymbal Europe Marketplace"
                )
                amount = round(random.uniform(45.0, 320.0), 2)
                latency_ms = round(random.uniform(3.4, 4.8), 1)

                row_key = f"{merchant_id}#{b['bin']}#{cred_type}#{rev_ts}#tx_{tx_counter}"
                cells = [
                    ("tx", "merchant_id", merchant_id),
                    ("tx", "merchant_name", merchant_name),
                    ("tx", "country", b["country"]),
                    ("tx", "currency", "GBP" if b["country"] == "GB" else "EUR"),
                    ("tx", "amount", f"{amount:.2f}"),
                    ("tx", "auth_status", auth_status),
                    ("tx", "decline_code", decline_code),
                    ("tx", "decline_reason", decline_reason),
                    ("tx", "credential_type", cred_type),
                    (
                        "tx",
                        "three_ds_mode",
                        "TRA_EXEMPT" if cred_type == "NETWORK_TOKEN" else "FRICTIONLESS_3DS2",
                    ),
                    (
                        "tx",
                        "event_timestamp",
                        datetime.datetime.fromtimestamp(ev_ts, tz=datetime.timezone.utc).isoformat(),
                    ),
                    ("issuer", "issuer_bin", b["bin"]),
                    ("issuer", "issuer_bank", b["bank"]),
                    ("issuer", "card_scheme", b["scheme"]),
                    ("routing", "gateway_region", "europe-west2-london"),
                    ("routing", "p99_latency_ms", str(latency_ms)),
                    (
                        "routing",
                        "intelligent_retry_eligible",
                        "true" if decline_code in ("05", "65") else "false",
                    ),
                ]
                mutations = [
                    {
                        "setCell": {
                            "familyName": fam,
                            "columnQualifier": b64e(qual),
                            "timestampMicros": "-1",
                            "value": b64e(val),
                        }
                    }
                    for fam, qual, val in cells
                ]
                entries.append({"rowKey": b64e(row_key), "mutations": mutations})

    for idx in range(0, len(entries), 100):
        st_m, resp_m = config.api_request(
            "POST",
            f"{base_data}/acquired_payments_live:mutateRows",
            token,
            body={"entries": entries[idx : idx + 100]},
        )
        if st_m != 200:
            print(f"  -> Batch {idx} warning (HTTP {st_m}): {resp_m}")
    print(f"  -> Seeded {len(entries)} payment telemetry rows into acquired_payments_live.")

    # 4. Seed Intelligent Acceptance routing rules
    rule_entries = []
    now_iso = datetime.datetime.now(datetime.timezone.utc).isoformat()
    for b in bins:
        rk = f"cymbal_retail_uk#{b['bin']}"
        is_hero = b["bin"] == "4532"
        rule_cells = [
            ("rule", "merchant_id", "cymbal_retail_uk"),
            ("rule", "issuer_bin", b["bin"]),
            ("rule", "issuer_bank", b["bank"]),
            ("rule", "force_network_token", "false" if is_hero else "true"),
            ("rule", "adaptive_iso8583_messaging", "STANDARD" if is_hero else "ISSUER_OPTIMIZED"),
            ("rule", "auto_retry_soft_decline_05", "false" if is_hero else "true"),
            ("rule", "expected_uplift_bps", "+1890" if is_hero else "+240"),
            ("audit", "updated_by", "cymbal-payments-default-policy"),
            ("audit", "last_updated", now_iso),
        ]
        rule_entries.append(
            {
                "rowKey": b64e(rk),
                "mutations": [
                    {
                        "setCell": {
                            "familyName": fam,
                            "columnQualifier": b64e(qual),
                            "timestampMicros": "-1",
                            "value": b64e(val),
                        }
                    }
                    for fam, qual, val in rule_cells
                ],
            }
        )
    st_r, _ = config.api_request(
        "POST",
        f"{base_data}/intelligent_acceptance_rules:mutateRows",
        token,
        body={"entries": rule_entries},
    )
    print(f"  -> Seeded {len(rule_entries)} routing rules into intelligent_acceptance_rules (HTTP {st_r}).")

    # 5. Create Bigtable Logical View & Continuous Materialized View
    lv_query = """SELECT
  CAST(_key AS STRING) AS row_key,
  CAST(tx['merchant_id'] AS STRING) AS merchant_id,
  CAST(tx['merchant_name'] AS STRING) AS merchant_name,
  CAST(issuer['issuer_bin'] AS STRING) AS issuer_bin,
  CAST(issuer['issuer_bank'] AS STRING) AS issuer_bank,
  CAST(issuer['card_scheme'] AS STRING) AS card_scheme,
  CAST(tx['credential_type'] AS STRING) AS credential_type,
  CAST(tx['auth_status'] AS STRING) AS auth_status,
  CAST(tx['decline_code'] AS STRING) AS decline_code,
  CAST(tx['decline_reason'] AS STRING) AS decline_reason,
  CAST(tx['amount'] AS STRING) AS amount_gbp,
  CAST(routing['p99_latency_ms'] AS STRING) AS p99_latency_ms,
  CAST(tx['event_timestamp'] AS STRING) AS event_timestamp
FROM acquired_payments_live"""
    st_lv, _ = config.api_request(
        "POST",
        f"{base_admin}/logicalViews",
        token,
        params={"logicalViewId": "v_acquired_payments_btql"},
        body={"query": lv_query},
    )
    print(f"  -> Logical View v_acquired_payments_btql (HTTP {st_lv}).")

    cmv_query = """SELECT
  CAST(issuer['issuer_bin'] AS STRING) AS issuer_bin,
  CAST(issuer['issuer_bank'] AS STRING) AS issuer_bank,
  CAST(tx['credential_type'] AS STRING) AS credential_type,
  CAST(tx['auth_status'] AS STRING) AS auth_status,
  CAST(tx['decline_code'] AS STRING) AS decline_code,
  COUNT(*) AS tx_count
FROM acquired_payments_live
GROUP BY 1, 2, 3, 4, 5"""
    st_cmv, _ = config.api_request(
        "POST",
        f"{base_admin}/materializedViews",
        token,
        params={"materializedViewId": "cmv_bin_acceptance_rollup"},
        body={"query": cmv_query},
    )
    print(f"  -> Continuous Materialized View cmv_bin_acceptance_rollup (HTTP {st_cmv}).")
    print("Done! Open Bigtable Studio in Google Cloud Console to verify.")


if __name__ == "__main__":
    main()
