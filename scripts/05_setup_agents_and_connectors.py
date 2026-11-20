#!/usr/bin/env python3
"""Step 5: Provision Conversational Analytics Data Agents & Optional Gemini Enterprise Connectors.

Default behavior (works in any standard GCP project):
- Creates `cymbal-payments-bt-agent` (Bigtable Conversational Analytics Data Agent)
- Creates `cymbal-payments-kyp-agent` (Unified BigQuery + Bigtable + Spanner Data Agent)

Optional (`--with-gemini-enterprise`):
- Registers the official 1P Google Cloud Spanner (`v2.0`) Data Connector
- Registers the custom Dual MCP Connectors (`cymbal-bigtable-mcp` & `cymbal-spanner-mcp`)
  pointing at your deployed `MCP_BASE_URL` (Cloud Run or API Gateway URL).
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import config  # noqa: E402


def create_ca_agents(token: str) -> None:
    proj = config.PROJECT_ID
    ds = config.BQ_DATASET
    ca_base = f"https://geminidataanalytics.googleapis.com/v1beta/projects/{proj}/locations/global/dataAgents"

    agents = [
        (
            "cymbal-payments-bt-agent",
            "Cymbal Payments — Bigtable Intelligent Acceptance Agent",
            (
                f"Conversational Analytics Data Agent for Cymbal Payments over live Cloud Bigtable "
                f"({config.BT_INSTANCE}) payment telemetry and 90-day BigQuery baselines."
            ),
            (
                "You are the Cymbal Payments Intelligent Acceptance Data Agent. "
                "Translate natural business phrases ('regular card numbers' -> RAW_PAN, "
                "'network tokens' -> NETWORK_TOKEN, 'Albion Bank' -> issuer_bin = '4532', "
                "'Thames Commercial Bank' -> issuer_bin = '5412', 'Crown & Sterling Bank' -> issuer_bin = '4929'). "
                f"Query `{proj}.{ds}.v_intelligent_acceptance_live_vs_baseline` and `{proj}.{ds}.issuer_baselines_90d`. "
                "Always highlight the live approval rate vs 90-day baseline, Soft Decline Code 05 count, "
                "daily revenue at risk (£421,200/day on Albion Bank UK BIN 4532 RAW_PAN), and Network Token uplift (+1,890 bps)."
            ),
            [
                {"project_id": proj, "dataset_id": ds, "table_id": "v_intelligent_acceptance_live_vs_baseline"},
                {"project_id": proj, "dataset_id": ds, "table_id": "issuer_baselines_90d"},
            ],
        ),
        (
            "cymbal-payments-kyp-agent",
            "Cymbal Payments — Unified KYP & Spanner Graph Risk Agent",
            (
                f"Unified Data Agent connecting BigQuery ({ds}), Cloud Bigtable ({config.BT_INSTANCE}), "
                f"and Cloud Spanner Graph ({config.SPANNER_INSTANCE})."
            ),
            (
                "You are the Cymbal Payments Unified Risk & Settlement Data Agent. "
                f"For UK false declines, query `{proj}.{ds}.v_intelligent_acceptance_live_vs_baseline`. "
                f"For European T+0 instant payout fraud rings, query `{proj}.{ds}.v_live_spanner_t0_fraud_ring_exposure` "
                f"and `{proj}.{ds}.historical_fraud_and_kyc_dossiers`. "
                "Highlight the €480,000 synthetic triangulation ring (Apex Digital UK €165K, Nova Goods FR €158K, "
                "Veloce Trade DE €157K) sharing 24 prepaid cards, 6 headless devices, and Dubai UBO IBAN AE47033120000099887766 "
                "with €375,000 in prior syndicate chargeback losses."
            ),
            [
                {"project_id": proj, "dataset_id": ds, "table_id": "v_intelligent_acceptance_live_vs_baseline"},
                {"project_id": proj, "dataset_id": ds, "table_id": "v_live_spanner_t0_fraud_ring_exposure"},
                {"project_id": proj, "dataset_id": ds, "table_id": "issuer_baselines_90d"},
                {"project_id": proj, "dataset_id": ds, "table_id": "historical_fraud_and_kyc_dossiers"},
            ],
        ),
    ]

    for agent_id, display_name, desc, instruction, tables in agents:
        st, resp = config.api_request(
            "POST",
            ca_base,
            token,
            params={"data_agent_id": agent_id},
            body={
                "display_name": display_name,
                "description": desc,
                "data_analytics_agent": {
                    "published_context": {
                        "system_instruction": instruction,
                        "datasource_references": {"bq": {"table_references": tables}},
                    }
                },
            },
        )
        print(
            f"  -> Conversational Analytics Agent `{agent_id}` ready (HTTP {st})."
            if st in (200, 409)
            else f"  -> Agent `{agent_id}` warning (HTTP {st}): {resp}"
        )


def setup_gemini_enterprise_connectors(token: str) -> None:
    pnum = config.get_project_number()
    proj = config.PROJECT_ID
    de_base = f"https://discoveryengine.googleapis.com/v1alpha/projects/{pnum}/locations/global"

    print("\n=== Registering 1P Spanner (v2.0) Connector in Gemini Enterprise ===")
    st_sp, resp_sp = config.api_request(
        "POST",
        f"{de_base}:setUpDataConnectorV2",
        token,
        params={
            "collectionId": "cymbal-spanner-connector",
            "collectionDisplayName": f"Spanner ({config.SPANNER_INSTANCE})",
        },
        body={
            "dataSource": "spanner",
            "dataSourceVersion": 2,
            "connectorModes": ["ACTIONS"],
            "bapConfig": {"supportedConnectorModes": ["ACTIONS"]},
            "actionConfig": {
                "isActionConfigured": True,
                "actionParams": {
                    "project_id": proj,
                    "instance_id": config.SPANNER_INSTANCE,
                    "database_id": config.SPANNER_DB,
                },
            },
        },
    )
    print(f"  -> 1P Spanner v2.0 Connector (`cymbal-spanner-connector`) HTTP {st_sp}")
    if st_sp not in (200, 409):
        print("     Details:", str(resp_sp)[:300])

    if not config.MCP_BASE_URL:
        print(
            "  -> Skipping custom MCP connector registration because MCP_BASE_URL is empty in .env.\n"
            "     Deploy apps/cloud-run-bridge-mcp first, set MCP_BASE_URL, and re-run with --with-gemini-enterprise."
        )
        return

    for cid, cname, path in [
        ("cymbal-bigtable-mcp", f"Cloud Bigtable MCP ({config.BT_INSTANCE})", "/api/checkout"),
        ("cymbal-spanner-mcp", f"Cloud Spanner MCP ({config.SPANNER_INSTANCE})", "/mcp"),
    ]:
        st_m, resp_m = config.api_request(
            "POST",
            f"{de_base}:setUpDataConnectorV2",
            token,
            params={"collectionId": cid, "collectionDisplayName": cname},
            body={
                "dataSource": "custom_mcp",
                "connectorModes": ["ACTIONS"],
                "params": {"oauth_access_token": "no_auth"},
                "actionConfig": {
                    "isActionConfigured": True,
                    "actionParams": {
                        "mcp_server_url": f"{config.MCP_BASE_URL}{path}",
                        "auth_type": "NO_AUTH",
                    },
                },
            },
        )
        print(f"  -> Custom MCP Connector `{cid}` -> {config.MCP_BASE_URL}{path} (HTTP {st_m})")
        if st_m not in (200, 409):
            print("     Details:", str(resp_m)[:300])


def main() -> None:
    parser = argparse.ArgumentParser(description="Provision Cymbal Payments Data Agents & Connectors.")
    parser.add_argument(
        "--with-gemini-enterprise",
        action="store_true",
        help="Also register 1P Spanner (v2.0) and custom Dual MCP connectors in Gemini Enterprise.",
    )
    args = parser.parse_args()

    token = config.get_access_token()
    print(f"=== Step 5: Conversational Analytics Agents ({config.PROJECT_ID}) ===")
    create_ca_agents(token)
    if args.with_gemini_enterprise:
        setup_gemini_enterprise_connectors(token)
    print("Done!")


if __name__ == "__main__":
    main()
