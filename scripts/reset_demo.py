#!/usr/bin/env python3
"""One-command pre-demo reset for BOTH Demo 1 (Bigtable) and Demo 2 (Spanner Graph).

- Bigtable (`cymbal-payments-prod`):
  * Sets `intelligent_acceptance_rules` row `cymbal_retail_uk#4532` back to `force_network_token = false` (`RAW_PAN`)
  * Deletes any live checkout rows (`#tx_live_`) written during previous demo runs
- Spanner (`cymbal-payments-graph / settlement_and_fraud_db`):
  * Sets `SubMerchants` (`subm_apex_uk`, `subm_nova_fr`, `subm_veloce_de`) back to `UNDER_GRAPH_REVIEW`
  * Sets `AccelerationPayoutRequests` (`t0_req_901..903`) back to `PENDING_GRAPH_GATE`

Usage:
  python3 scripts/reset_demo.py                 # Reset both Bigtable & Spanner
  python3 scripts/reset_demo.py --bigtable-only # Reset Demo 1 only
  python3 scripts/reset_demo.py --spanner-only  # Reset Demo 2 only
"""

from __future__ import annotations

import argparse
import base64
import datetime
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import config  # noqa: E402


def b64e(text: str) -> str:
    return base64.b64encode(text.encode("utf-8")).decode("ascii")


def b64d(text: str) -> str:
    return base64.b64decode(text).decode("utf-8", errors="replace")


def reset_bigtable(token: str) -> None:
    print(f"=== Resetting Cloud Bigtable ({config.BT_INSTANCE}) ===")
    bt_base = (
        f"https://bigtable.googleapis.com/v2/projects/{config.PROJECT_ID}"
        f"/instances/{config.BT_INSTANCE}/tables"
    )
    now_iso = datetime.datetime.now(datetime.timezone.utc).isoformat()

    # 1. Flip routing rule back to RAW_PAN (force_network_token = false)
    rule_cells = [
        ("rule", "force_network_token", "false"),
        ("rule", "adaptive_iso8583_messaging", "STANDARD"),
        ("rule", "auto_retry_soft_decline_05", "false"),
        ("audit", "updated_by", "cymbal-demo-reset"),
        ("audit", "last_updated", now_iso),
    ]
    st_r, _ = config.api_request(
        "POST",
        f"{bt_base}/intelligent_acceptance_rules:mutateRow",
        token,
        body={
            "rowKey": b64e("cymbal_retail_uk#4532"),
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
        },
    )
    print(f"  -> Rule cymbal_retail_uk#4532 reset to RAW_PAN (HTTP {st_r}).")

    # 2. Delete any live checkout rows (`#tx_live_`) written during previous demos
    st_read, rows = config.api_request(
        "POST",
        f"{bt_base}/acquired_payments_live:readRows",
        token,
        body={
            "rows": {
                "rowRanges": [
                    {
                        "startKeyClosed": b64e("cymbal_retail_uk#4532#"),
                        "endKeyOpen": b64e("cymbal_retail_uk#4532$"),
                    }
                ]
            },
            "rowsLimit": 500,
        },
    )
    live_keys: list[str] = []
    if st_read == 200 and isinstance(rows, list):
        for item in rows:
            cur_rk = None
            for ch in item.get("chunks", []):
                if "rowKey" in ch:
                    cur_rk = b64d(ch["rowKey"])
                if ch.get("commitRow") and cur_rk and "#tx_live_" in cur_rk:
                    live_keys.append(cur_rk)

    if live_keys:
        del_entries = [
            {"rowKey": b64e(rk), "mutations": [{"deleteFromRow": {}}]} for rk in live_keys
        ]
        st_del, _ = config.api_request(
            "POST",
            f"{bt_base}/acquired_payments_live:mutateRows",
            token,
            body={"entries": del_entries},
        )
        print(f"  -> Deleted {len(live_keys)} live checkout row(s) from acquired_payments_live (HTTP {st_del}).")
    else:
        print("  -> No live #tx_live_ rows found to delete.")


def reset_spanner(token: str) -> None:
    print(f"=== Resetting Cloud Spanner ({config.SPANNER_INSTANCE} / {config.SPANNER_DB}) ===")
    db_uri = (
        f"https://spanner.googleapis.com/v1/projects/{config.PROJECT_ID}"
        f"/instances/{config.SPANNER_INSTANCE}/databases/{config.SPANNER_DB}"
    )
    st_s, s_resp = config.api_request("POST", f"{db_uri}/sessions", token, body={})
    if st_s != 200 or not isinstance(s_resp, dict):
        print(f"  -> Failed to open Spanner session (HTTP {st_s}): {s_resp}")
        return
    session = s_resp["name"]
    try:
        st_c, resp_c = config.api_request(
            "POST",
            f"https://spanner.googleapis.com/v1/{session}:commit",
            token,
            body={
                "singleUseTransaction": {"readWrite": {}},
                "mutations": [
                    {
                        "update": {
                            "table": "SubMerchants",
                            "columns": ["merchant_id", "risk_status", "acceleration_t0_enabled"],
                            "values": [
                                ["subm_apex_uk", "UNDER_GRAPH_REVIEW", True],
                                ["subm_nova_fr", "UNDER_GRAPH_REVIEW", True],
                                ["subm_veloce_de", "UNDER_GRAPH_REVIEW", True],
                            ],
                        }
                    },
                    {
                        "update": {
                            "table": "AccelerationPayoutRequests",
                            "columns": ["payout_req_id", "payout_status"],
                            "values": [
                                ["t0_req_901", "PENDING_GRAPH_GATE"],
                                ["t0_req_902", "PENDING_GRAPH_GATE"],
                                ["t0_req_903", "PENDING_GRAPH_GATE"],
                            ],
                        }
                    },
                ],
            },
        )
        print(f"  -> Spanner ring rows reset to PENDING_GRAPH_GATE (HTTP {st_c}, ts={resp_c.get('commitTimestamp')}).")
    finally:
        config.api_request("DELETE", f"https://spanner.googleapis.com/v1/{session}", token)


def main() -> None:
    parser = argparse.ArgumentParser(description="Reset Cymbal Payments demo state.")
    parser.add_argument("--bigtable-only", action="store_true", help="Reset Demo 1 (Bigtable) only.")
    parser.add_argument("--spanner-only", action="store_true", help="Reset Demo 2 (Spanner) only.")
    args = parser.parse_args()

    token = config.get_access_token()
    if not args.spanner_only:
        reset_bigtable(token)
    if not args.bigtable_only:
        reset_spanner(token)
    print("All requested demo states reset and ready!")


if __name__ == "__main__":
    main()
