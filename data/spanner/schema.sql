-- ==============================================================================
-- Cymbal Payments — Cloud Spanner Relational Schema & Native Property Graph
-- Database: settlement_and_fraud_db
-- Property Graph: cymbal_fraud_and_settlement_graph (Zero-ETL over live tables)
-- ==============================================================================

CREATE TABLE SubMerchants (
  merchant_id STRING(64) NOT NULL,
  merchant_name STRING(128) NOT NULL,
  jurisdiction STRING(16) NOT NULL,
  mcc_code STRING(16) NOT NULL,
  kyc_tier STRING(32) NOT NULL,
  onboarding_date DATE NOT NULL,
  acceleration_t0_enabled BOOL NOT NULL,
  risk_status STRING(32) NOT NULL,
  pending_t0_payout_eur FLOAT64 NOT NULL,
) PRIMARY KEY (merchant_id);

CREATE TABLE PaymentCards (
  card_token STRING(64) NOT NULL,
  issuer_bin STRING(16) NOT NULL,
  card_scheme STRING(32) NOT NULL,
  issuing_country STRING(16) NOT NULL,
  is_prepaid BOOL NOT NULL,
) PRIMARY KEY (card_token);

CREATE TABLE Devices (
  device_fingerprint STRING(64) NOT NULL,
  ip_asn STRING(64) NOT NULL,
  user_agent_family STRING(64) NOT NULL,
  emulator_detected BOOL NOT NULL,
  shared_merchant_count INT64 NOT NULL,
) PRIMARY KEY (device_fingerprint);

CREATE TABLE PayoutAccounts (
  payout_account_id STRING(64) NOT NULL,
  iban_or_wallet STRING(64) NOT NULL,
  beneficial_owner_name STRING(128) NOT NULL,
  bank_country STRING(16) NOT NULL,
  ubo_risk_flag STRING(32) NOT NULL,
) PRIMARY KEY (payout_account_id);

CREATE TABLE CardPayments (
  payment_id STRING(64) NOT NULL,
  card_token STRING(64) NOT NULL,
  merchant_id STRING(64) NOT NULL,
  device_fingerprint STRING(64) NOT NULL,
  amount_eur FLOAT64 NOT NULL,
  row_fraud_score FLOAT64 NOT NULL,
  tx_status STRING(32) NOT NULL,
  tx_timestamp TIMESTAMP NOT NULL,
) PRIMARY KEY (payment_id);

CREATE TABLE DeviceUsages (
  card_token STRING(64) NOT NULL,
  device_fingerprint STRING(64) NOT NULL,
  session_count INT64 NOT NULL,
  first_seen_ts TIMESTAMP NOT NULL,
) PRIMARY KEY (card_token, device_fingerprint);

CREATE TABLE AccelerationPayoutRequests (
  payout_req_id STRING(64) NOT NULL,
  merchant_id STRING(64) NOT NULL,
  payout_account_id STRING(64) NOT NULL,
  requested_amount_eur FLOAT64 NOT NULL,
  settlement_rail STRING(32) NOT NULL,
  payout_status STRING(32) NOT NULL,
  requested_ts TIMESTAMP NOT NULL,
) PRIMARY KEY (payout_req_id);

CREATE PROPERTY GRAPH cymbal_fraud_and_settlement_graph
  NODE TABLES (
    SubMerchants
      KEY (merchant_id)
      LABEL SubMerchant
      PROPERTIES (merchant_id, merchant_name, jurisdiction, mcc_code, kyc_tier, acceleration_t0_enabled, risk_status, pending_t0_payout_eur),
    PaymentCards
      KEY (card_token)
      LABEL PaymentCard
      PROPERTIES (card_token, issuer_bin, card_scheme, issuing_country, is_prepaid),
    Devices
      KEY (device_fingerprint)
      LABEL Device
      PROPERTIES (device_fingerprint, ip_asn, user_agent_family, emulator_detected, shared_merchant_count),
    PayoutAccounts
      KEY (payout_account_id)
      LABEL PayoutAccount
      PROPERTIES (payout_account_id, iban_or_wallet, beneficial_owner_name, bank_country, ubo_risk_flag)
  )
  EDGE TABLES (
    CardPayments
      KEY (payment_id)
      SOURCE KEY (card_token) REFERENCES PaymentCards (card_token)
      DESTINATION KEY (merchant_id) REFERENCES SubMerchants (merchant_id)
      LABEL PAID_MERCHANT
      PROPERTIES (payment_id, amount_eur, row_fraud_score, device_fingerprint, tx_status, tx_timestamp),
    DeviceUsages
      KEY (card_token, device_fingerprint)
      SOURCE KEY (card_token) REFERENCES PaymentCards (card_token)
      DESTINATION KEY (device_fingerprint) REFERENCES Devices (device_fingerprint)
      LABEL USED_DEVICE
      PROPERTIES (session_count, first_seen_ts),
    AccelerationPayoutRequests
      KEY (payout_req_id)
      SOURCE KEY (merchant_id) REFERENCES SubMerchants (merchant_id)
      DESTINATION KEY (payout_account_id) REFERENCES PayoutAccounts (payout_account_id)
      LABEL REQUESTS_T0_PAYOUT_TO
      PROPERTIES (payout_req_id, requested_amount_eur, settlement_rail, payout_status, requested_ts)
  );
