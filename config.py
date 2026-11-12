"""
TRACE — Configuration constants.
"""

import os

# ── Directories ──────────────────────────────────────────────────────────────
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
SAMPLE_DIR = os.path.join(BASE_DIR, "samples")
REPORT_DIR = os.path.join(BASE_DIR, "reports")
QUARANTINE_DIR = os.path.join(BASE_DIR, "quarantine")
KEYS_DIR = os.path.join(BASE_DIR, "keys")

# Create directories on import
for _d in (SAMPLE_DIR, REPORT_DIR, QUARANTINE_DIR, KEYS_DIR):
    os.makedirs(_d, exist_ok=True)

# ── Hash algorithms available for demonstration ──────────────────────────────
HASH_ALGORITHMS = {
    "SHA-256": "sha256",
    "SHA3-256": "sha3_256",
    "BLAKE2b": "blake2b",
    "MD5 (legacy provider checksum)": "md5",
}

DEFAULT_HASH = "SHA-256"

# ── Verification verdicts ────────────────────────────────────────────────────
VERDICT_PASS = "PASS"
VERDICT_FAIL = "FAIL"
VERDICT_UNVERIFIED = "UNVERIFIED"

# ── Colour palette (for Streamlit UI) ────────────────────────────────────────
COLOUR_PASS = "#28a745"
COLOUR_FAIL = "#dc3545"
COLOUR_WARN = "#ffc107"

