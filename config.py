"""Shared configuration and Google Cloud REST helpers for Cymbal Payments demos.

Loads settings from `.env` (if present) and environment variables, falling back
to the active `gcloud` CLI project when `PROJECT_ID` is unset.
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent


def _load_dotenv() -> None:
    env_path = REPO_ROOT / ".env"
    if not env_path.exists():
        return
    for raw_line in env_path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, val = line.split("=", 1)
        key = key.strip()
        val = val.strip().strip('"').strip("'")
        if key and key not in os.environ:
            os.environ[key] = val


_load_dotenv()


def find_gcloud() -> str:
    """Locate the `gcloud` CLI binary on PATH (or standard Cloudtop/SDK paths)."""
    found = shutil.which("gcloud")
    if found:
        return found
    for candidate in (
        "/google/data/ro/teams/cloud-sdk/gcloud",
        "/usr/bin/gcloud",
        "/usr/local/bin/gcloud",
    ):
        if os.path.exists(candidate):
            return candidate
    raise RuntimeError(
        "Could not find `gcloud` CLI. Install the Google Cloud SDK and run `gcloud auth login`."
    )


GCLOUD_BIN = find_gcloud()


def resolve_project_id() -> str:
    proj = os.environ.get("PROJECT_ID", "").strip()
    if proj and proj != "your-gcp-project-id":
        return proj
    try:
        out = subprocess.check_output(
            [GCLOUD_BIN, "config", "get-value", "project"],
            text=True,
            stderr=subprocess.DEVNULL,
        ).strip()
        if out and out != "(unset)":
            return out
    except subprocess.CalledProcessError:
        pass
    print(
        "ERROR: PROJECT_ID is not set. Copy .env.example to .env and set PROJECT_ID, "
        "or run `gcloud config set project <YOUR_PROJECT_ID>`.",
        file=sys.stderr,
    )
    sys.exit(1)


PROJECT_ID = resolve_project_id()
REGION = os.environ.get("REGION", "us-central1")
ZONE = os.environ.get("ZONE", "us-central1-a")

BT_INSTANCE = os.environ.get("BT_INSTANCE", "cymbal-payments-prod")
BT_CLUSTER = os.environ.get("BT_CLUSTER", "cymbal-payments-c1")

SPANNER_INSTANCE = os.environ.get("SPANNER_INSTANCE", "cymbal-payments-graph")
SPANNER_DB = os.environ.get("SPANNER_DB", "settlement_and_fraud_db")
SPANNER_GRAPH = os.environ.get("SPANNER_GRAPH", "cymbal_fraud_and_settlement_graph")

BQ_DATASET = os.environ.get("BQ_DATASET", "cymbal_payments_warehouse")
BQ_SPANNER_CONN = os.environ.get("BQ_SPANNER_CONN", "cymbal-spanner-conn")
GLOSSARY_ID = os.environ.get("GLOSSARY_ID", "cymbal-payments-glossary")

CLOUD_RUN_SERVICE = os.environ.get("CLOUD_RUN_SERVICE", "cymbal-payments-bt-bridge")
GE_ENGINE_ID = os.environ.get("GE_ENGINE_ID", "cymbal-payments-enterprise-hub")
MCP_BASE_URL = os.environ.get("MCP_BASE_URL", "").rstrip("/")


_PROJECT_NUMBER_CACHE: str | None = None


def get_project_number() -> str:
    global _PROJECT_NUMBER_CACHE
    if _PROJECT_NUMBER_CACHE:
        return _PROJECT_NUMBER_CACHE
    if os.environ.get("PROJECT_NUMBER"):
        _PROJECT_NUMBER_CACHE = os.environ["PROJECT_NUMBER"].strip()
        return _PROJECT_NUMBER_CACHE
    out = subprocess.check_output(
        [GCLOUD_BIN, "projects", "describe", PROJECT_ID, "--format=value(projectNumber)"],
        text=True,
    ).strip()
    _PROJECT_NUMBER_CACHE = out
    return out


def get_access_token() -> str:
    """Return an OAuth2 access token from `gcloud auth print-access-token`."""
    return subprocess.check_output(
        [GCLOUD_BIN, "auth", "print-access-token"], text=True
    ).strip()


def api_request(
    method: str,
    url: str,
    token: str,
    body: dict | str | bytes | None = None,
    params: dict | None = None,
    content_type: str = "application/json",
    timeout: int = 90,
) -> tuple[int, dict | list | str]:
    """Minimal dependency-free REST helper with automatic 429/503 retries."""
    if params:
        sep = "&" if "?" in url else "?"
        url = f"{url}{sep}{urllib.parse.urlencode(params)}"
    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": content_type,
        "X-Goog-User-Project": PROJECT_ID,
    }
    if body is None:
        payload = None
    elif isinstance(body, (bytes, bytearray)):
        payload = body
    elif isinstance(body, str):
        payload = body.encode("utf-8")
    else:
        payload = json.dumps(body).encode("utf-8")

    for attempt in range(4):
        req = urllib.request.Request(url, data=payload, headers=headers, method=method)
        try:
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                txt = resp.read().decode("utf-8")
                if not txt:
                    return resp.status, {}
                if content_type == "application/json":
                    try:
                        return resp.status, json.loads(txt)
                    except json.JSONDecodeError:
                        return resp.status, txt
                return resp.status, txt
        except urllib.error.HTTPError as exc:
            err_txt = exc.read().decode("utf-8", errors="replace")
            if exc.code in (429, 503) and attempt < 3:
                time.sleep(2 * (attempt + 1))
                continue
            try:
                return exc.code, json.loads(err_txt)
            except json.JSONDecodeError:
                return exc.code, err_txt
    return 500, "Max retries exceeded"
