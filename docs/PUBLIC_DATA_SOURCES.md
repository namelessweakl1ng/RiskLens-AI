# Public source collection

Use only public, licensed or owner-authorized documents. Current ingestion
sources and provenance rules are documented in [DATASET.md](DATASET.md).

- CFPB Credit Card Agreement Database for actual credit-card terms.
- IRDAI/public insurer policy wordings for insurance restrictions and benefits.
- SEC EDGAR exhibits for investment, financing and material contractual terms.
- CUAD for contract-language candidates with semantic mapping review.

Redact personal data before annotation. The original source guide's independent
training/data contract was retired; the single pipeline requires complete
source-document metadata and grouped splits. No historical two-field
text/label record alone qualifies as reviewed ground truth.
