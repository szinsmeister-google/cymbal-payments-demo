# Cymbal Payments — Cloud Run Bridge & Dual MCP Server

A zero-dependency Python 3.12 Cloud Run service that powers both:
1. **Checkout Web App Live REST API**: Reads/mutates real rows in **Cloud Bigtable** (`cymbal-payments-prod`) with millisecond latency.
2. **Dual Streamable HTTP MCP Server + Luminous MCP Apps**: Exposes interactive HTML chart cards (`text/html;profile=mcp-app`) and live database tools for **Gemini Enterprise** agents across both **Cloud Bigtable** and **Cloud Spanner Graph**.

## Endpoints

| Path | Method | Purpose |
| :--- | :--- | :--- |
| `/` | `GET` | Health check returning active Bigtable instance and MCP endpoint info |
| `/api/state` | `GET` | Reads live `cymbal_retail_uk#4532` rule and lists any `#tx_live_` demo rows in Bigtable |
| `/api/checkout` | `POST` *(JSON)* | Executes a live checkout write (`DECLINED` or `APPROVED`) to Bigtable `acquired_payments_live` |
| `/api/checkout` | `POST` *(JSON-RPC 2.0)* | **Bigtable MCP Server** (`query_bigtable_uk_acceptance`, `enable_bigtable_network_token_rule`, `ui://cymbal-bigtable-mcp/acceptance-chart`) |
| `/api/rule/enable-token` | `POST` | Sets `force_network_token = true` on `cymbal_retail_uk#4532` in Bigtable |
| `/api/reset` | `POST` | Resets `cymbal_retail_uk#4532` to `RAW_PAN` and deletes `#tx_live_` rows in Bigtable |
| `/mcp` | `POST` *(JSON-RPC 2.0)* | **Spanner Graph MCP Server** (`query_spanner_fraud_ring_gql`, `get_spanner_t0_payout_exposure`, `freeze_spanner_t0_collusion_ring`, `ui://cymbal-spanner-mcp/fraud-ring-graph`) |

## Deploy to Your Google Cloud Project

```bash
chmod +x apps/cloud-run-bridge-mcp/deploy.sh
./apps/cloud-run-bridge-mcp/deploy.sh
```

## Run Locally (for Development)

```bash
export PROJECT_ID="your-gcp-project-id"
export PROJECT_NUM="$(gcloud projects describe "$PROJECT_ID" --format='value(projectNumber)')"
export LOCAL_ACCESS_TOKEN="$(gcloud auth print-access-token)"
python3 apps/cloud-run-bridge-mcp/main.py
```
