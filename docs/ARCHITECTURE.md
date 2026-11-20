# Cymbal Payments — Technical Architecture Guide (CE & FDE Reference)

This document explains the architectural design patterns showcased across **Demo 1 (Cloud Bigtable)** and **Demo 2 (Cloud Spanner Graph)** so Customer Engineers (CEs) and Forward Deployed Engineers (FDEs) can handle deep technical Q&A during customer briefings.

---

## 1. Core Architectural Thesis: Eliminating the "Database Zoo"

Modern payment processors typically run into three failure modes when scaling real-time AI and fraud prevention:
1. **The ETL Blind Spot:** Copying live operational payment rows out of a NoSQL or OLTP database into a separate analytics warehouse or standalone graph database introduces 1–6 hours of lag. By the time a false-decline alert or collusion graph updates, either hundreds of thousands in GMV is lost or instant `T+0` funds have already left the building.
2. **OLTP Contention Fear:** Infrastructure teams hesitate to let analysts, BigQuery jobs, or AI agents query live acquiring or ledger clusters because heavy scans can cause P99 latency spikes on live card swipes.
3. **LLM Token Explosion & Governance Drift:** Feeding raw transaction logs or graph edges into an LLM burns hundreds of thousands of tokens per investigation and invites hallucinated risk definitions.

Google Cloud's **Agentic Data Cloud** resolves all three across both demos:

| Architectural Pattern | Demo 1 (Cloud Bigtable) | Demo 2 (Cloud Spanner Graph) |
| :--- | :--- | :--- |
| **Operational Engine** | `cymbal-payments-prod` (`acquired_payments_live`, `intelligent_acceptance_rules`) — sub-5ms P99 key-value & wide-column reads/writes | `cymbal-payments-graph` (`settlement_and_fraud_db`) — globally consistent SQL ledger + native **ISO GQL Property Graph** (`cymbal_fraud_and_settlement_graph`) |
| **Zero-ETL Federation** | BigQuery External Table (`acquired_payments_bigtable_ext`) reading live Bigtable rows in place and joining with 90-day baselines (`issuer_baselines_90d`) | BigQuery `EXTERNAL_QUERY` over `cymbal-spanner-conn` joining live Spanner state with 12-month chargeback dossiers (`historical_fraud_and_kyc_dossiers`) |
| **Compute Isolation** | **Bigtable Serverless Data Boost** + Continuous Materialized View (`cmv_bin_acceptance_rollup`) — **0% primary cluster CPU impact** | **Spanner Serverless Data Boost** (`useDataBoost=true`) — **0% primary OLTP CPU impact** |
| **Context Engineering** | **Knowledge Catalog** (`cymbal-payments-glossary`) defining `False Decline Rate`, `Soft Decline Code 05`, and `Network Token Authorization Uplift` | **Knowledge Catalog** (`cymbal-payments-glossary`) defining `Cymbal Acceleration (T+0)` and `Synthetic Triangulation Ring` |
| **Tokenomics Pushdown** | SQL/BTQL aggregation over Bigtable Logical Views & CMVs returns compact bank-level summaries instead of raw swipe rows | 3-hop ISO GQL pushdown condenses **180,000+ raw edge tokens -> 3 summary rows (~980 tokens)** — **99.4% LLM token reduction** |
| **System of Action** | Single-row sub-5ms Bigtable mutation (`cymbal_retail_uk#4532` -> `force_network_token = true`) immediately picked up by live Checkout App | Single **TrueTime** atomic read-write transaction locking all 3 collusive sub-merchants and freezing **€480,000** at the exact same commit timestamp |

---

## 2. How the Custom Checkout App & Dual MCP Server Work

The Cloud Run service (`apps/cloud-run-bridge-mcp/main.py`) runs as a single lightweight Python 3.12 container with zero external pip dependencies, authenticating via the Cloud Run metadata server (or `LOCAL_ACCESS_TOKEN` locally).

### A. Live Checkout REST Flow (`apps/checkout-web` -> Cloud Run -> Bigtable)
1. On page load, `index.html` calls `GET /api/state` to read live row `cymbal_retail_uk#4532` from Bigtable table `intelligent_acceptance_rules`.
2. When the presenter clicks **Pay £248.00**, `index.html` sends `POST /api/checkout`:
   - Cloud Run reads `rule:force_network_token` from `intelligent_acceptance_rules`.
   - If `false` (`RAW_PAN`), Cloud Run writes a real **DECLINED** row (`decline_code = 05`, `credential_type = RAW_PAN`) into `acquired_payments_live` using reverse-timestamp key `cymbal_retail_uk#4532#RAW_PAN#<rev_ts>#tx_live_<id>` and returns the exact write latency (`ms`) and a copyable BTQL verification query.
   - If `true` (`NETWORK_TOKEN`), Cloud Run writes a real **APPROVED** row (`decline_code = 00`, `credential_type = NETWORK_TOKEN`) into `acquired_payments_live` and the UI confirms Order `#CR-88412`.
3. Clicking **Alex Mercer (`AM`) -> Reset Demo (Delete Write)** calls `POST /api/reset`, which sets `force_network_token = false` and deletes all `#tx_live_` rows so the dataset stays clean across repeated demos.

### B. Dual Streamable HTTP MCP Server + Luminous MCP Apps
The same Cloud Run service exposes two JSON-RPC 2.0 MCP endpoints for **Gemini Enterprise**:
- **`POST /api/checkout` (Bigtable MCP):** Exposes `query_bigtable_uk_acceptance` and `enable_bigtable_network_token_rule`, plus MCP App resource `ui://cymbal-bigtable-mcp/acceptance-chart` (interactive Luminous bar/comparison card with verified badges).
- **`POST /mcp` (Spanner Graph MCP):** Exposes `query_spanner_fraud_ring_gql`, `get_spanner_t0_payout_exposure`, and `freeze_spanner_t0_collusion_ring`, plus MCP App resource `ui://cymbal-spanner-mcp/fraud-ring-graph` (animated 3-hop SVG graph topology + `€480K` exposure bar chart + `99.4%` tokenomics card).

---

## 3. Cost & Teardown Tips for CEs / FDEs

- **Bigtable (`cymbal-payments-prod`):** Provisioned with `1` SSD node in a single zone (`us-central1-a`).
- **Spanner (`cymbal-payments-graph`):** Provisioned with `100` Processing Units (`STANDARD` edition) in `regional-us-central1` — the lowest-cost Spanner footprint supporting full Spanner Graph (ISO GQL) and Data Boost.
- **Cloud Run (`cymbal-payments-bt-bridge`):** Change `--min-instances=1` to `--min-instances=0` in `apps/cloud-run-bridge-mcp/deploy.sh` if you want scale-to-zero between customer meetings.
