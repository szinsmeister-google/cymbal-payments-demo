# Demo 2 Playbook: Zero-ETL Fraud Rings & T+0 Settlement on Spanner Graph

**Target Runtime:** ~3m 35s · **Persona:** Payment Risk & Settlement Lead at Cymbal Payments

---

## 1. Pre-Flight Checklist (2 Minutes Before Demo)

1. Reset Cloud Spanner so all 3 ring sub-merchants are back in `PENDING_GRAPH_GATE`:
   ```bash
   python3 scripts/reset_demo.py --spanner-only
   ```
2. Open these browser tabs in order:
   - **Tab 1 — Spanner Relational Tables:** `https://console.cloud.google.com/spanner/instances/cymbal-payments-graph/databases/settlement_and_fraud_db/details/tables?project=<YOUR_PROJECT_ID>`
   - **Tab 2 — Spanner Graph Studio:** `https://console.cloud.google.com/spanner/instances/cymbal-payments-graph/databases/settlement_and_fraud_db/details/query?project=<YOUR_PROJECT_ID>`
   - **Tab 3 — Knowledge Catalog Studio:** `https://console.cloud.google.com/dataplex/studio?project=<YOUR_PROJECT_ID>`
   - **Tab 4 — BigQuery Studio:** `https://console.cloud.google.com/bigquery?project=<YOUR_PROJECT_ID>`
   - **Tab 5 — Gemini Enterprise Agent** *(with 1P Spanner Connector + Spanner Graph MCP App + Knowledge Catalog)*

---

## 2. Query & Prompt Cheat Sheet

### Tab 2 — Query 1.3 (Visual 3-Hop Force-Directed Property Graph in Spanner Graph Studio)
```sql
GRAPH cymbal_fraud_and_settlement_graph
MATCH
  p1 = (u:PayoutAccount {ubo_risk_flag: 'HIGH_VELOCITY_SHARED_UBO'})<-[req:REQUESTS_T0_PAYOUT_TO]-(m:SubMerchant),
  p2 = (m)<-[pay:PAID_MERCHANT]-(c:PaymentCard)-[du:USED_DEVICE]->(d:Device)
RETURN
  TO_JSON(p1) AS payout_path,
  TO_JSON(p2) AS device_ring_path
LIMIT 60;
```

### Tab 2 — Query 1.4 (3-Hop ISO GQL Collusion Rollup — `€480,000` Exposure)
```sql
GRAPH cymbal_fraud_and_settlement_graph
MATCH
  (u:PayoutAccount {ubo_risk_flag: 'HIGH_VELOCITY_SHARED_UBO'})<-[req:REQUESTS_T0_PAYOUT_TO]-(m:SubMerchant)
  <-[pay:PAID_MERCHANT]-(c:PaymentCard)-[du:USED_DEVICE]->(d:Device)
RETURN
  m.merchant_name,
  m.jurisdiction,
  req.requested_amount_eur,
  req.payout_status,
  u.iban_or_wallet AS shared_ubo_iban,
  u.beneficial_owner_name,
  COUNT(DISTINCT c.card_token) AS cycled_cards,
  COUNT(DISTINCT d.device_fingerprint) AS shared_devices,
  ROUND(AVG(pay.row_fraud_score), 2) AS avg_row_score
GROUP BY
  m.merchant_name, m.jurisdiction, req.requested_amount_eur,
  req.payout_status, u.iban_or_wallet, u.beneficial_owner_name
ORDER BY req.requested_amount_eur DESC;
```

### Tab 3 — Prompt 2.1 (Knowledge Catalog Explore Chat)
> `Which live Spanner Graph tables and historical BigQuery dispute tables are linked to our Cymbal Acceleration T+0 and Synthetic Triangulation Ring glossary terms?`

### Tab 4 — Query 2.2 (BigQuery + Spanner Data Boost Federated View)
```sql
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
FROM `<YOUR_PROJECT_ID>.cymbal_payments_warehouse.v_live_spanner_t0_fraud_ring_exposure`
ORDER BY requested_t0_payout_eur DESC;
```

### Tab 5 — Gemini Enterprise Agent Prompts
- **Prompt 3.1 (Investigation):**
  > `We have €480K in pending European T+0 payouts—are any of these merchants secretly sharing cards, devices, or a single bank account?`
- **Prompt 3.2 (Atomic TrueTime Action):**
  > `Execute an atomic Spanner transaction to freeze the €480,000 collusive T+0 payout ring across all 3 sub-merchants`

---

## 3. Say | Do | See Talk Track

| Beat | Say (Key Narrative Points) | Do (Presenter Action) | See (On-Screen Proof) |
| :--- | :--- | :--- | :--- |
| **1.1–1.2 The Tabular Blind Spot** | Scaling instant `T+0` payouts creates a Friday-night test: when three European sub-merchants (**Apex Digital UK**, **Nova Goods FR**, **Veloce Trade DE**) request **€480,000** in instant settlement, waiting 2 hours for ETL into a separate graph database means the money is gone. Every single transaction passed row-level ML checks with a clean **0.12** fraud score because fraudsters don't attack in rows — they attack in networks. | Show **Tab 1 (`SubMerchants`, `CardPayments`, `AccelerationPayoutRequests`)** highlighting `row_fraud_score = 0.12` and `PENDING_GRAPH_GATE` balances (`€165K`, `€158K`, `€157K`). | Flat relational tables showing three seemingly clean merchants with `0.12` scores. |
| **1.3–1.4 Zero-ETL 3-Hop Spanner Graph** | Switch to **Spanner Graph Studio** and run a 3-hop **ISO GQL** query directly over those live tables — zero ETL, zero database sprawl. In milliseconds, the entire synthetic triangulation ring lights up: **24 Cyprus prepaid cards** cycled across **6 headless proxy devices**, funneling all **€480,000** into **1 Dubai UBO account**. | In **Tab 2**, run **Query 1.3** and drag the central Dubai `PayoutAccount` node (`AE47033120000099887766`) so the 3 merchant clusters fan out. Then run **Query 1.4** for the 3-row rollup. | Force-directed graph revealing the 3-hop ring, followed by the 3-row ISO GQL rollup (`€165K + €158K + €157K = €480K`). |
| **2.1–2.2 Context Engineering, Tokenomics & Data Boost** | **Knowledge Catalog** governs the exact definitions of `Cymbal Acceleration T+0` and `Synthetic Triangulation Ring` across Spanner and BigQuery. In **BigQuery Studio**, pushing the 3-hop aggregation down into Spanner condenses **180,000+ raw edge tokens -> <1,000 tokens** (**99.4% token reduction**), while **Spanner Data Boost** runs the federated join against 12 months of chargeback dossiers (**€375,000** prior syndicate losses) with **0% OLTP CPU impact**. | Run **Prompt 2.1** in **Tab 3 (Knowledge Catalog)**, then run **Query 2.2** in **Tab 4 (BigQuery Studio)**. | Governed Context Graph + 3-row BigQuery Data Boost result confirming `€375,000` prior syndicate losses (`€135K + €125K + €115K`) and `IMMEDIATE_T0_QUARANTINE_AND_FREEZE`. |
| **3.1–3.2 Direct Spanner Connector & Atomic TrueTime Freeze** | Inside **Gemini Enterprise**, open the Connectors menu to show the native **Spanner** connector and **Knowledge Catalog**. Ask the investigation question in plain English — Gemini renders the interactive Luminous 3-hop chart and recommends a freeze. With one command, execute an atomic **Spanner TrueTime** read-write transaction freezing all three merchants simultaneously so automated scripts can't drain the others. | In **Tab 5**, show the `🧩` Connectors menu, run **Prompt 3.1**, explore the **Graph Topology** tab, then run **Prompt 3.2**. Flip back to **Tab 2** and re-run **Query 1.4**. | Returned **TrueTime Commit Timestamp**; live Spanner Studio query flips all 3 rows from `PENDING_GRAPH_GATE` to `FROZEN_BY_SPANNER_GRAPH` simultaneously. |
