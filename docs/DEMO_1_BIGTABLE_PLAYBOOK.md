# Demo 1 Playbook: Cloud Bigtable Intelligent Acceptance & Conversational Analytics

**Target Runtime:** ~3–4 minutes · **Persona:** Head of Payment Acceptance & Risk at Cymbal Payments

---

## 1. Pre-Flight Checklist (2 Minutes Before Demo)

1. Reset Bigtable to the starting `RAW_PAN` state (and delete any prior live checkout rows):
   ```bash
   python3 scripts/reset_demo.py --bigtable-only
   ```
   *(Or click **Alex Mercer (`AM`) -> Reset Demo (Delete Write)** in the Checkout App.)*
2. Open these browser tabs in order:
   - **Tab 1 — Checkout Web App:** `http://localhost:8090` (or your hosted URL pointing to Cloud Run)
   - **Tab 2 — Bigtable Studio & Conversational Analytics:** `https://console.cloud.google.com/bigtable/instances/cymbal-payments-prod/agents?project=<YOUR_PROJECT_ID>`
   - **Tab 3 — Knowledge Catalog Studio:** `https://console.cloud.google.com/dataplex/studio?project=<YOUR_PROJECT_ID>`
   - **Tab 4 — BigQuery Studio:** `https://console.cloud.google.com/bigquery?project=<YOUR_PROJECT_ID>`
   - **Tab 5 — Gemini Enterprise Agent** *(optional, if wired via `--with-gemini-enterprise`)*

---

## 2. Prompt & Query Cheat Sheet

### Tab 2 — Bigtable Conversational Analytics Prompts (`cymbal-payments-bt-agent`)
- **Prompt 1 (Triage UK Issuing Banks):**
  > `Which UK issuing banks are declining Cymbal Retail checkouts right now, and how do raw 16-digit cards compare against Network Tokens?`
- **Prompt 2 (Root Cause & Soft Decline Code 05):**
  > `Break down Albion Bank UK declines by decline code over the last 10 minutes and tell me if switching to Network Tokens fixes it.`

### Tab 3 — Knowledge Catalog Explore Prompt
- **Prompt 3 (Context & Governance Lineage):**
  > `Which operational Bigtable tables and analytical BigQuery views are linked to our False Decline Rate and Soft Decline Code 05 glossary terms, and how is Network Token Authorization Uplift calculated?`

### Tab 4 — BigQuery Studio Federated Query (from `data/sql/bigquery_federated_queries.sql`)
```sql
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
FROM `<YOUR_PROJECT_ID>.cymbal_payments_warehouse.v_intelligent_acceptance_live_vs_baseline`
WHERE issuer_bin = '4532'
ORDER BY credential_type DESC;
```

---

## 3. Say | Do | See Talk Track

| Beat | Say (Key Narrative Points) | Do (Presenter Action) | See (On-Screen Proof) |
| :--- | :--- | :--- | :--- |
| **1.1 Live False Decline** | Start with a real customer experience: Alex Mercer has £24,850 in connected cash, a 792 credit score, and £8,420 available in Albion Bank UK. He tries to buy £248 running shoes — and gets hit with a false decline. Every millisecond of a false decline costs the merchant real revenue. | In **Tab 1 (Checkout App)**, click **Pay £248.00**. Open the **Telemetry & Demo** drawer and click **Copy Verification Query for Bigtable Studio**. | Red banner: *Payment declined by Albion Bank UK (Soft Decline Code 05)*. Drawer shows live row key written to `acquired_payments_live` in ~3ms. |
| **1.2 Live Bigtable Verification & CA** | Flip straight into **Cloud Bigtable**. That decline isn't mocked — it's live in `acquired_payments_live`. Instead of writing hand-coded scans, we ask **Bigtable Conversational Analytics** in plain English what is happening across UK banks — isolated by **Bigtable Data Boost** with zero impact on live card swipes. | In **Tab 2**, paste the copied BTQL query into Bigtable Studio (shows the `DECLINED` `RAW_PAN` row), then ask **Prompt 1** & **Prompt 2** in Bigtable CA. | `Albion Bank UK (BIN 4532)` dropped to **77.8%** on `RAW_PAN` due to **Soft Decline Code 05**, while `NETWORK_TOKEN` approves at **96.7%** (`+1,890 bps`). |
| **1.3 Knowledge Catalog Governance** | Before any AI agent quantifies dollar impact or changes routing, we need governed business definitions. Inside **Knowledge Catalog**, our glossary maps live Bigtable tables directly to 90-day BigQuery baselines on one lineage canvas. | Switch to **Tab 3 (Knowledge Catalog)** and submit **Prompt 3**. Trace the Context Graph from `cymbal-payments-glossary` across Bigtable & BigQuery. | Context Graph linking `False Decline Rate`, `Soft Decline Code 05`, `acquired_payments_bigtable_ext`, `issuer_baselines_90d`, and `v_intelligent_acceptance_live_vs_baseline`. |
| **1.4 Zero-ETL BigQuery Federation** | Bigtable knows the last 10 minutes; BigQuery holds 90-day issuer baselines and merchant GMV. With a **Zero-ETL BigQuery External Table** over Bigtable, one SQL query quantifies the exact business impact: **-1,642 bps** drop and **£421,200/day** in false-decline GMV at risk. | Switch to **Tab 4 (BigQuery Studio)** and run the federated query against `v_intelligent_acceptance_live_vs_baseline`. | 2-row comparison for `Albion Bank UK (4532)`: `RAW_PAN` (`77.8%` vs `94.2%`, `£421,200/day` at risk) vs `NETWORK_TOKEN` (`96.7%` vs `96.5%`, `£0` at risk). |
| **1.5 System of Action (Live Recovery)** | Insight without action is just trivia. Flip `cymbal_retail_uk#4532` in Bigtable `intelligent_acceptance_rules` to `force_network_token = true` — either via the Gemini Enterprise agent or the profile menu — and watch Alex's checkout succeed live. | Enable Network Token (via Gemini Agent or **Alex Mercer (`AM`) -> Enable Network Token**), then return to **Tab 1** and click **Pay £248.00**. | Card flips to **EMVCo Network Token**, green confirmation banner (`Payment confirmed · £248.00`), balance updates to `£8,172.00`, and an `APPROVED` (`00`) row writes live to Bigtable! |
