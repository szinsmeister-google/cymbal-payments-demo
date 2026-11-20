# Cymbal Payments — Connected Accounts & Express Checkout Web App

A realistic consumer banking and express checkout demo app that reads live routing rules from **Cloud Bigtable** (`intelligent_acceptance_rules`) and writes real payment rows (`DECLINED` / `APPROVED`) into `acquired_payments_live` with sub-5ms latency.

## Features
- **Live Bigtable Read/Write Loop**: Clicking **Pay £248.00** executes a live `POST /api/checkout` against the Cloud Run bridge, which reads `cymbal_retail_uk#4532` in Cloud Bigtable and writes a real row (`cymbal_retail_uk#4532#<MODE>#<rev_ts>#tx_live_<id>`) into `acquired_payments_live`.
- **Telemetry & Demo Drawer**: Click **Telemetry & Demo** in the top navigation bar to inspect the live Bigtable row key, write latency (`ms`), issuer approval comparison, and copy a ready-to-paste BTQL verification query for Bigtable Studio.
- **Hidden Presenter Reset & Token Toggle**: Click the **Alex Mercer (`AM`)** profile pill in the top-right corner to reveal:
  - **Reset Demo (Delete Write)**: Resets `cymbal_retail_uk#4532` to `RAW_PAN` and deletes `#tx_live_` demo writes from Bigtable.
  - **Enable Network Token**: Flips `force_network_token = true` in Bigtable live so the next checkout approves immediately (`APPROVED`, Code `00`).

## Quickstart

### 1. Point the app at your Cloud Run backend
Either copy `config.example.js` to `config.js`:
```bash
cp apps/checkout-web/config.example.js apps/checkout-web/config.js
# Edit API_BASE with your Cloud Run URL from apps/cloud-run-bridge-mcp/deploy.sh
```
Or pass the backend URL directly via query string:
```text
http://localhost:8090/?api=https://YOUR-CLOUD-RUN-SERVICE.run.app
```

### 2. Run locally
```bash
python3 apps/checkout-web/serve_local.py
```
Open `http://localhost:8090` in Chrome.

### 3. Optional: Host statically on Firebase Hosting or Cloud Storage
Because the app is a single self-contained `index.html` + optional `config.js`, you can drop it straight onto Firebase Hosting, Cloud Storage, or any static host with zero build step.
