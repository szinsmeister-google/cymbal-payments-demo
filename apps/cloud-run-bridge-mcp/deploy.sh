#!/usr/bin/env bash
# Deploy the Cymbal Payments Cloud Run Bridge & Dual MCP Server
# Usage:
#   source .env  # or export PROJECT_ID=...
#   ./apps/cloud-run-bridge-mcp/deploy.sh

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "${SCRIPT_DIR}/../.." && pwd)"

if [[ -f "${REPO_ROOT}/.env" ]]; then
  set -a
  # shellcheck disable=SC1091
  source "${REPO_ROOT}/.env"
  set +a
fi

PROJECT_ID="${PROJECT_ID:-$(gcloud config get-value project 2>/dev/null || true)}"
REGION="${REGION:-us-central1}"
SERVICE_NAME="${CLOUD_RUN_SERVICE:-cymbal-payments-bt-bridge}"
BT_INSTANCE="${BT_INSTANCE:-cymbal-payments-prod}"
SPANNER_INSTANCE="${SPANNER_INSTANCE:-cymbal-payments-graph}"
SPANNER_DB="${SPANNER_DB:-settlement_and_fraud_db}"
BQ_DATASET="${BQ_DATASET:-cymbal_payments_warehouse}"

if [[ -z "${PROJECT_ID}" || "${PROJECT_ID}" == "your-gcp-project-id" ]]; then
  echo "ERROR: Set PROJECT_ID in .env or run 'gcloud config set project <PROJECT_ID>'." >&2
  exit 1
fi

PROJECT_NUM="$(gcloud projects describe "${PROJECT_ID}" --format='value(projectNumber)')"
COMPUTE_SA="${PROJECT_NUM}-compute@developer.gserviceaccount.com"

echo "=== Enabling required APIs on ${PROJECT_ID} ==="
gcloud services enable \
  run.googleapis.com \
  cloudbuild.googleapis.com \
  bigtable.googleapis.com \
  spanner.googleapis.com \
  --project="${PROJECT_ID}" --quiet

echo "=== Granting Bigtable & Spanner permissions to ${COMPUTE_SA} ==="
gcloud projects add-iam-policy-binding "${PROJECT_ID}" \
  --member="serviceAccount:${COMPUTE_SA}" \
  --role="roles/bigtable.user" --quiet >/dev/null

gcloud projects add-iam-policy-binding "${PROJECT_ID}" \
  --member="serviceAccount:${COMPUTE_SA}" \
  --role="roles/spanner.databaseUser" --quiet >/dev/null

echo "=== Deploying Cloud Run service ${SERVICE_NAME} in ${REGION} ==="
gcloud run deploy "${SERVICE_NAME}" \
  --source="${SCRIPT_DIR}" \
  --project="${PROJECT_ID}" \
  --region="${REGION}" \
  --allow-unauthenticated \
  --min-instances=1 \
  --max-instances=5 \
  --set-env-vars="PROJECT_ID=${PROJECT_ID},PROJECT_NUM=${PROJECT_NUM},BT_INSTANCE=${BT_INSTANCE},SPANNER_INSTANCE=${SPANNER_INSTANCE},SPANNER_DB=${SPANNER_DB},BQ_DATASET=${BQ_DATASET}"

SERVICE_URL="$(gcloud run services describe "${SERVICE_NAME}" --project="${PROJECT_ID}" --region="${REGION}" --format='value(status.url)')"
echo ""
echo "Deployed successfully!"
echo "  Base URL (for apps/checkout-web/config.js): ${SERVICE_URL}"
echo "  Bigtable MCP Endpoint:                      ${SERVICE_URL}/api/checkout"
echo "  Spanner Graph MCP Endpoint:                 ${SERVICE_URL}/mcp"
