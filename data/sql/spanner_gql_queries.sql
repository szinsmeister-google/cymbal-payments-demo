-- ==============================================================================
-- Demo 2: Cloud Spanner Graph Studio (ISO GQL) Query Bank
-- Instance: cymbal-payments-graph | Database: settlement_and_fraud_db
-- Property Graph: cymbal_fraud_and_settlement_graph
-- ==============================================================================

-- Query 1.3: Visual 3-Hop Force-Directed Node-Link Graph in Spanner Graph Studio
-- Traverses live operational tables with Zero ETL:
-- PayoutAccount <- REQUESTS_T0_PAYOUT_TO - SubMerchant <- PAID_MERCHANT - PaymentCard - USED_DEVICE -> Device
GRAPH cymbal_fraud_and_settlement_graph
MATCH
  p1 = (u:PayoutAccount {ubo_risk_flag: 'HIGH_VELOCITY_SHARED_UBO'})<-[req:REQUESTS_T0_PAYOUT_TO]-(m:SubMerchant),
  p2 = (m)<-[pay:PAID_MERCHANT]-(c:PaymentCard)-[du:USED_DEVICE]->(d:Device)
RETURN
  TO_JSON(p1) AS payout_path,
  TO_JSON(p2) AS device_ring_path
LIMIT 60;

-- Query 1.4: 3-Hop ISO GQL Collusion Rollup (€480,000 Exposure Across 3 Sub-Merchants)
-- Condenses 180,000+ raw transaction/device edge tokens into 3 summary rows (~980 tokens, 99.4% token reduction).
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
  m.merchant_name,
  m.jurisdiction,
  req.requested_amount_eur,
  req.payout_status,
  u.iban_or_wallet,
  u.beneficial_owner_name
ORDER BY req.requested_amount_eur DESC;

-- Pre-Demo Reset DML (Run between live demos or video takes to restore PENDING_GRAPH_GATE)
UPDATE SubMerchants
SET risk_status = 'UNDER_GRAPH_REVIEW', acceleration_t0_enabled = TRUE
WHERE merchant_id IN ('subm_apex_uk', 'subm_nova_fr', 'subm_veloce_de');

UPDATE AccelerationPayoutRequests
SET payout_status = 'PENDING_GRAPH_GATE'
WHERE payout_req_id IN ('t0_req_901', 't0_req_902', 't0_req_903');
