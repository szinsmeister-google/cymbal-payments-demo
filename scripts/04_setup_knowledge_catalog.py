#!/usr/bin/env python3
"""Step 4: Provision Knowledge Catalog Glossary, Entry Links & Policy Artifacts.

Creates in `<PROJECT_ID>` (`REGION`):
- Business Glossary `cymbal-payments-glossary` with 5 governed terms:
  1. False Decline Rate (Intelligent Acceptance)
  2. Soft Decline Code 05 (Do Not Honor)
  3. Network Token Authorization Uplift
  4. Cymbal Acceleration (T+0 Instant Settlement)
  5. Synthetic Triangulation Ring (3-Hop Graph)
- Dataplex Entry Links connecting glossary terms to BigQuery, Bigtable, and Spanner assets
- GCS bucket `gs://cymbal-payments-kc-policies-<PROJECT_NUMBER>/cymbal-payments/`
  containing the SOP markdown & Python pipeline constants for Knowledge Catalog Enrichment Agent.
"""

from __future__ import annotations

import sys
import time
import urllib.parse
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import config  # noqa: E402

DP = "https://dataplex.googleapis.com/v1"
SYS_PROJECT = "655216118709"  # Google-managed Dataplex system aspect/link types project


def wait_op(token: str, op: dict | str) -> None:
    if isinstance(op, dict) and "/operations/" in op.get("name", ""):
        op_name = op["name"]
        for _ in range(30):
            _, res = config.api_request("GET", f"{DP}/{op_name}", token)
            if isinstance(res, dict) and res.get("done"):
                return
            time.sleep(1.5)


def set_overview(token: str, entry_name: str, md: str) -> int:
    body = {
        "name": entry_name,
        "aspects": {
            f"{SYS_PROJECT}.global.overview": {
                "aspectType": f"projects/{SYS_PROJECT}/locations/global/aspectTypes/overview",
                "data": {"content": md, "contentType": "MARKDOWN"},
            }
        },
    }
    st, _ = config.api_request(
        "PATCH",
        f"{DP}/{entry_name}",
        token,
        body=body,
        params={"updateMask": "aspects", "aspectKeys": f"{SYS_PROJECT}.global.overview"},
    )
    return st


def main() -> None:
    token = config.get_access_token()
    proj = config.PROJECT_ID
    pnum = config.get_project_number()
    loc = config.REGION
    gid = config.GLOSSARY_ID

    print(f"=== Step 4: Knowledge Catalog ({proj} / {loc} / {gid}) ===")

    # 1. Create Business Glossary in REGION
    st_g, resp_g = config.api_request(
        "POST",
        f"{DP}/projects/{proj}/locations/{loc}/glossaries",
        token,
        params={"glossaryId": gid},
        body={
            "displayName": "Cymbal Payments Global Risk & Acceptance Glossary",
            "description": (
                f"Governed enterprise payment definitions for Cymbal Payments across Cloud Bigtable "
                f"({config.BT_INSTANCE}), Cloud Spanner Graph ({config.SPANNER_INSTANCE}), and "
                f"BigQuery ({config.BQ_DATASET})."
            ),
        },
    )
    if st_g == 200:
        wait_op(token, resp_g)
        print(f"  -> Created glossary {gid} in {loc}.")
    elif st_g == 409:
        print(f"  -> Glossary {gid} already exists in {loc}.")
    else:
        print(f"  -> Glossary warning (HTTP {st_g}): {resp_g}")

    # 2. Create/Update the 5 governed glossary terms
    terms = [
        (
            "false-decline-rate",
            "False Decline Rate (Intelligent Acceptance)",
            "Share of legitimate customer transactions declined by an issuing bank due to stale or untokenized credential formatting (RAW_PAN) rather than fraud or insufficient funds. Target < 1.5%.",
            "### False Decline Rate (Intelligent Acceptance)\n\n"
            "- **Policy Threshold:** >`1.5%` false decline rate or >`-500 bps` approval drop vs. 90-day baseline in `issuer_baselines_90d` triggers `FORCE_NETWORK_TOKEN`.\n"
            f"- **Operational Source (Bigtable):** `{config.BT_INSTANCE}.acquired_payments_live` & `cmv_bin_acceptance_rollup`.\n"
            f"- **Federated Analytics (BigQuery):** `{config.BQ_DATASET}.acquired_payments_bigtable_ext` & `v_intelligent_acceptance_live_vs_baseline`.",
        ),
        (
            "soft-decline-code-05",
            "Soft Decline Code 05 (Do Not Honor)",
            "ISO 8583 issuer rejection code 05 triggered on un-tokenised 16-digit Raw PAN retries on Albion Bank UK (BIN 4532), dropping live approval to 77.8% (-1,642 bps) and exposing £421,200/day GMV.",
            "### Soft Decline Code 05 (Do Not Honor)\n\n"
            "- **Root Cause:** Issuer velocity filter rejecting `RAW_PAN` while approving `NETWORK_TOKEN` at `96.7%`.\n"
            "- **Remediation:** Update row `cymbal_retail_uk#4532` in `intelligent_acceptance_rules` to `force_network_token = true`.",
        ),
        (
            "network-token-uplift",
            "Network Token Authorization Uplift",
            "Authorization rate gain (+1,890 bps, from 77.8% RAW_PAN to 96.7% NETWORK_TOKEN on Albion Bank UK BIN 4532) achieved when routing credentials as EMVCo Network Tokens.",
            "### Network Token Authorization Uplift\n\n"
            "- **Calculation:** `v_intelligent_acceptance_live_vs_baseline` joining `acquired_payments_bigtable_ext` and `issuer_baselines_90d`.\n"
            "- **Control Plane:** `intelligent_acceptance_rules` (`rule:force_network_token`, `rule:expected_uplift_bps`).",
        ),
        (
            "cymbal-acceleration-t0",
            "Cymbal Acceleration (T+0 Instant Settlement)",
            "24/7 instant sub-merchant payout facility in Cloud Spanner (AccelerationPayoutRequests) requiring both row-level fraud score < 0.25 and zero shared-entity collusion rings in Spanner Graph.",
            "### Cymbal Acceleration (T+0 Instant Settlement)\n\n"
            f"- **Policy Gate:** Tabular `row_fraud_score < 0.25` AND zero shared UBO/device rings in `{config.SPANNER_GRAPH}`.\n"
            "- **Linked Assets:** `AccelerationPayoutRequests`, `SubMerchants`, `PayoutAccounts`, `v_live_spanner_t0_fraud_ring_exposure`.",
        ),
        (
            "synthetic-triangulation-ring",
            "Synthetic Triangulation Ring (3-Hop Graph)",
            "Coordinated multi-merchant bust-out ring where sub-merchants pass row-level checks (0.12 score) while sharing 6 headless devices, 24 prepaid cards, and 1 Dubai UBO IBAN requesting €480,000 in T+0 payouts.",
            "### Synthetic Triangulation Ring (3-Hop Graph)\n\n"
            "- **Detection Pattern:** >=3 sub-merchants cycling >=5 prepaid cards & >=2 headless devices into 1 shared UBO IBAN.\n"
            f"- **Linked Assets:** `{config.SPANNER_GRAPH}`, `v_live_spanner_t0_fraud_ring_exposure`, `historical_fraud_and_kyc_dossiers`.",
        ),
    ]

    dx_eg = f"projects/{pnum}/locations/{loc}/entryGroups/@dataplex"
    for tid, title, desc, md in terms:
        st_t, resp_t = config.api_request(
            "POST",
            f"{DP}/projects/{proj}/locations/{loc}/glossaries/{gid}/terms",
            token,
            params={"termId": tid},
            body={
                "displayName": title,
                "description": desc,
                "parent": f"projects/{proj}/locations/{loc}/glossaries/{gid}",
            },
        )
        if st_t == 409:
            config.api_request(
                "PATCH",
                f"{DP}/projects/{proj}/locations/{loc}/glossaries/{gid}/terms/{tid}",
                token,
                params={"updateMask": "displayName,description"},
                body={"displayName": title, "description": desc},
            )
        term_entry = f"{dx_eg}/entries/projects/{pnum}/locations/{loc}/glossaries/{gid}/terms/{tid}"
        set_overview(token, term_entry, md)
        print(f"  -> Term {tid} ready (HTTP {st_t}).")

    # 3. Link Glossary Terms to BigQuery & Spanner Entries via Dataplex Entry Links
    bq_eg = f"projects/{pnum}/locations/{loc}/entryGroups/@bigquery"
    sp_eg = f"projects/{pnum}/locations/{loc}/entryGroups/@spanner"
    def_type = f"projects/{SYS_PROJECT}/locations/global/entryLinkTypes/definition"

    def bq_entry(tbl: str) -> str:
        return f"{bq_eg}/entries/bigquery.googleapis.com/projects/{proj}/datasets/{config.BQ_DATASET}/tables/{tbl}"

    def sp_entry(tbl: str) -> str:
        return (
            f"{sp_eg}/entries/spanner.googleapis.com/projects/{proj}"
            f"/instances/{config.SPANNER_INSTANCE}/databases/{config.SPANNER_DB}/tables/{tbl}"
        )

    links = [
        ("lnk-fdr-ext", "false-decline-rate", bq_entry("acquired_payments_bigtable_ext")),
        ("lnk-fdr-view", "false-decline-rate", bq_entry("v_intelligent_acceptance_live_vs_baseline")),
        ("lnk-fdr-base", "false-decline-rate", bq_entry("issuer_baselines_90d")),
        ("lnk-sd05-view", "soft-decline-code-05", bq_entry("v_intelligent_acceptance_live_vs_baseline")),
        ("lnk-ntu-view", "network-token-uplift", bq_entry("v_intelligent_acceptance_live_vs_baseline")),
        ("lnk-t0-req", "cymbal-acceleration-t0", sp_entry("AccelerationPayoutRequests")),
        ("lnk-t0-view", "cymbal-acceleration-t0", bq_entry("v_live_spanner_t0_fraud_ring_exposure")),
        ("lnk-ring-subm", "synthetic-triangulation-ring", sp_entry("SubMerchants")),
        ("lnk-ring-view", "synthetic-triangulation-ring", bq_entry("v_live_spanner_t0_fraud_ring_exposure")),
        ("lnk-ring-hist", "synthetic-triangulation-ring", bq_entry("historical_fraud_and_kyc_dossiers")),
    ]

    linked_ok = 0
    for link_id, tid, target_entry in links:
        term_entry = f"{dx_eg}/entries/projects/{pnum}/locations/{loc}/glossaries/{gid}/terms/{tid}"
        st_l, _ = config.api_request(
            "POST",
            f"{DP}/{dx_eg}/entryLinks",
            token,
            params={"entryLinkId": link_id},
            body={
                "entryLinkType": def_type,
                "entryReferences": [
                    {"name": target_entry, "type": "SOURCE"},
                    {"name": term_entry, "type": "TARGET"},
                ],
            },
        )
        if st_l in (200, 409):
            linked_ok += 1
    print(f"  -> Linked {linked_ok}/{len(links)} glossary-to-table definitions in Knowledge Catalog.")

    # 4. Upload unstructured SOP & pipeline constants to GCS for Enrichment Agent
    bucket_name = f"cymbal-payments-kc-policies-{pnum}"
    st_b, _ = config.api_request(
        "POST",
        f"https://storage.googleapis.com/storage/v1/b?project={proj}",
        token,
        body={
            "name": bucket_name,
            "location": loc,
            "iamConfiguration": {"uniformBucketLevelAccess": {"enabled": True}},
        },
    )
    print(f"  -> GCS Policy Bucket gs://{bucket_name} ready (HTTP {st_b}).")

    gov_dir = config.REPO_ROOT / "data" / "governance"
    for fname, ctype in [
        ("ALBION-BANK-4532-ISSUER-ADVISORY-AND-ROUTING-SOP.md", "text/markdown"),
        ("intelligent_acceptance_token_routing_pipeline.py", "text/x-python"),
    ]:
        obj_name = urllib.parse.quote(f"cymbal-payments/{fname}", safe="")
        st_u, _ = config.api_request(
            "POST",
            f"https://storage.googleapis.com/upload/storage/v1/b/{bucket_name}/o?uploadType=media&name={obj_name}",
            token,
            body=(gov_dir / fname).read_text(encoding="utf-8"),
            content_type=ctype,
        )
        print(f"  -> Uploaded gs://{bucket_name}/cymbal-payments/{fname} (HTTP {st_u}).")

    print("Done! Open Dataplex Knowledge Catalog Studio in Google Cloud Console to inspect the Context Graph.")


if __name__ == "__main__":
    main()
