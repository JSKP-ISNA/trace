# TRACE — Tamper-Resistant Audit Chain for Earth-observation data

A Python/Streamlit prototype that demonstrates end-to-end security
verification of remote-sensing satellite imagery.

## What it does

TRACE takes a satellite data product (image + metadata + provenance) and runs
a four-stage verification pipeline:

| Stage | Check | Algorithm / Method |
|-------|-------|--------------------|
| 1 | **Integrity** | SHA-256 / SHA3-256 / BLAKE2b hash comparison |
| 2 | **Metadata consistency** | Field-by-field comparison against trusted reference |
| 3 | **Authenticity** | Digital signature verification (Ed25519 / ECDSA / RSA) |
| 4 | **Provenance** | Processing-history completeness (W3C PROV-inspired) |

It then classifies the product as **PASS**, **FAIL** or **UNVERIFIED** and
recommends whether to accept, quarantine or investigate.

## Attack scenarios

The sidebar lets you simulate seven attack types and watch the pipeline
respond:

- ✅ No attack (all checks pass)
- 🖼️ Pixel modification (hash mismatch)
- 📝 Metadata alteration (consistency failure)
- 🔄 File substitution (hash + metadata failure)
- 🔑 Invalid signature (authenticity failure)
- 📋 Missing provenance (incomplete record)
- ⚠️ Image + checksum replaced (demonstrates why signatures matter)

## Quick start

```bash
# 1. Install dependencies
pip install -r requirements.txt

# 2. Run the app
streamlit run app.py
```

The app generates a built-in synthetic satellite tile on first run — no
external downloads required.

To test with real data, upload a Sentinel-2 GeoTIFF or product file via the
web interface.

## Project structure

```
trace/
├── app.py                  # Streamlit web application
├── config.py               # Configuration constants
├── requirements.txt        # Python dependencies
├── generate_samples.py     # Synthetic data generator
├── core/
│   ├── __init__.py
│   ├── hashing.py          # SHA-256, SHA3-256, BLAKE2b
│   ├── signatures.py       # Ed25519, ECDSA, RSA sign/verify
│   ├── metadata.py         # Sentinel-2 manifest parser + checks
│   ├── provenance.py       # W3C PROV-inspired lineage model
│   ├── verification.py     # Pipeline orchestrator + report
│   └── attacks.py          # Tamper simulation helpers
├── samples/                # Generated sample data (auto-created)
├── keys/                   # Demo key pairs (auto-created)
├── reports/                # Downloaded verification reports
└── quarantine/             # Rejected files
```

## Technology stack

- **Python 3.10+**
- **Streamlit** — web interface
- **hashlib** — cryptographic hashing
- **cryptography** — digital signatures
- **rasterio** (optional) — GeoTIFF with CRS; falls back to Pillow
- **NumPy** — synthetic data generation
- **Pillow** — image handling fallback

## Research context

This prototype supports the research topic *Security and Trust in Remote
Sensing Data and Geospatial Systems*.  It demonstrates:

- How integrity, authenticity and provenance checks work individually
- How they interact to cover each other's blind spots
- What happens when each check fails
- Why a hash alone is insufficient without a trusted reference
- How digital signatures add verifiable attribution
