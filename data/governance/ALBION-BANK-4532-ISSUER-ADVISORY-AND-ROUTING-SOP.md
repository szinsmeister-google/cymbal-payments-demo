# Cymbal Payments · Intelligent Acceptance & T+0 Settlement Risk SOP (POL-PAY-2026-UK05)

- **Owner:** Payment Operations & Acquiring Risk Engineering
- **Governed False Decline Threshold (`False Decline Rate`):** **`1.5%` maximum** or **`-500 bps`** drop below the 90-day issuer authorization baseline in `issuer_baselines_90d`.
- **Albion Bank UK (`BIN 4532`) Soft Decline Code 05 Advisory (`IAB-4532-05`):**
  - **Root Cause:** Albion Bank UK updated its domestic card-not-present velocity filter to reject un-tokenised 16-digit PAN retries (`RAW_PAN`) with ISO 8583 **Soft Decline Code 05 (`Do Not Honor`)**, dropping live approval rate in `acquired_payments_live` and `acquired_payments_bigtable_ext` to **`77.8%`** (`-1,642 bps` vs. the `94.2%` 90-day baseline in `issuer_baselines_90d`) and exposing **`£421,200/day`** in UK merchant GMV.
  - **Network Token Authorization Uplift (`+1,890 bps`):** Cryptographic EMVCo Network Tokens (`NETWORK_TOKEN`) on Albion Bank UK `BIN 4532` approve at **`96.7%`** (`+17 bps` above baseline, `£0` false-decline risk).
  - **Discrepancy Resolution (HITL Steward Review):** Legacy gateway routing scripts waited for a `-2,500 bps` drop (`LEGACY_DROP_BPS_THRESHOLD = -2500`) before enabling Network Token substitution, missing the Albion Bank UK `-1,642 bps` drop. Always enforce the governed **`-500 bps`** threshold (`GOVERNED_DROP_BPS_THRESHOLD = -500`) and set `rule:force_network_token = true` on `cymbal_retail_uk#4532` in `intelligent_acceptance_rules`.
- **Cymbal Acceleration (T+0 Instant Settlement) & Synthetic Triangulation Ring Gate (`SRP-T0-09`):**
  - Any T+0 payout request in `AccelerationPayoutRequests` must pass both row-level tabular fraud score `< 0.25` AND a 3-hop Spanner Graph check (`cymbal_fraud_and_settlement_graph`) verifying zero shared headless devices (`Devices`) or shared beneficial owner IBANs (`PayoutAccounts`).
  - **Flagged Ring (`AE47033120000099887766`):** `Apex Digital Ltd` (`€165,000`), `Nova Goods SARL` (`€158,000`), and `Veloce Trade GmbH` (`€157,000`) share 24 prepaid cards, 6 headless devices, and Dubai UBO IBAN `AE47033120000099887766` (`€480,000` total exposure; `€375,000` prior syndicate chargeback loss in `historical_fraud_and_kyc_dossiers`).
- **Golden Schema Join Keys:**
  - `acquired_payments_bigtable_ext` joins `issuer_baselines_90d` on `issuer_bin` and `credential_type` inside `v_intelligent_acceptance_live_vs_baseline`
  - `v_live_spanner_t0_fraud_ring_exposure` joins `historical_fraud_and_kyc_dossiers` on `merchant_id`
