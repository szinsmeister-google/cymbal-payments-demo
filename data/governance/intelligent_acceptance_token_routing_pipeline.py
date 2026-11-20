"""Cymbal Payments Intelligent Acceptance & T+0 Risk Pipeline Constants.

Reference pipeline artifact uploaded to GCS for Knowledge Catalog Enrichment Agent
discrepancy detection (legacy -2,500 bps script threshold vs. governed -500 bps SOP).
"""

# Governed Intelligent Acceptance thresholds (Cymbal Payments Global Risk & Acceptance Glossary)
FALSE_DECLINE_MAX_RATE_PCT: float = 0.015
GOVERNED_DROP_BPS_THRESHOLD: int = -500

# DISCREPANCY NOTICE (Flagged for Steward Review):
# Legacy gateway alert script used LEGACY_DROP_BPS_THRESHOLD = -2500 bps, which failed to
# trigger on Albion Bank UK (BIN 4532) at -1642 bps (77.8% live vs 94.2% baseline, £421,200/day GMV at risk).
LEGACY_DROP_BPS_THRESHOLD: int = -2500

# T+0 Cymbal Acceleration Instant Settlement gates
TABULAR_FRAUD_SCORE_CEILING: float = 0.25
MAX_SHARED_UBO_MERCHANTS_T0: int = 1
