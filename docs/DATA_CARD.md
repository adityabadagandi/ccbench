# Data Card

## Dataset Overview

CCBench is a benchmark for enterprise context compilation across multiple document formats and jurisdictions.

## Composition

- **Total cases:** 200+ (target)
- **Dev split:** 100
- **Test split:** 100+
- **Buckets:** lookup, multi-hop, temporal, cross-lingual, compliance

## Collection Process

- Synthetic invoice data with realistic GSTIN/HSN/IRN structure
- E-way bills linked by consignment reference
- ERP purchase-order records seeded from BPI Challenge 2019 event-log structure
- Controllable noise injection (OCR typos, currency format variance, date variance)
- Adversarial cases designed to break naive matching

## Provenance

| Component | Source | License |
|-----------|--------|---------|
| Invoice structure | Synthetic (GST-format) | CC-BY-SA 4.0 |
| ERP event-log | BPI Challenge 2019 | Refer to BPI Challenge terms |
| Regulation text | EUR-Lex GDPR / DPDP | Public domain / government |
| Identifiers | Synthetic only | N/A |

## PII Statement

All identifiers (GSTIN, PAN, IRN, vendor names) are **synthetic**. No real
personal or business data is included in this benchmark.

## Limitations

- Focused on Indian logistics / GST context
- Limited to 2 jurisdictions (IN, EU)
- Synthetic data may not capture all real-world edge cases
- WhatsApp threads are simulated, not real

## Licensing

- **Data:** CC-BY-SA 4.0
- **Code:** MIT
