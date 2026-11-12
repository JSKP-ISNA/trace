"""
TRACE — Attack simulation helpers.

Each function takes a known-good input and returns a tampered copy,
together with a description of what changed.  Used by the Streamlit UI
so the professor can select a scenario and watch the pipeline react.
"""

import copy
import hashlib
import json
import numpy as np
from core.hashing import compute_hash
from core.metadata import ProductMetadata
from core.provenance import ProvenanceRecord
from core.signatures import sign_data


# ── Attack definitions ───────────────────────────────────────────────────────

ATTACKS = {
    "none": {
        "label": "✅ No attack — original, untampered product",
        "description": "The file, metadata and provenance are exactly as produced. "
                       "All verification checks should pass.",
    },
    "pixel_flip": {
        "label": "🖼️ Pixel modification — change image content",
        "description": "A small number of pixel values are altered.  This simulates "
                       "post-processing manipulation of the raster data.  The hash "
                       "must change and integrity verification should fail.",
    },
    "metadata_tamper": {
        "label": "📝 Metadata alteration — change product identity",
        "description": "Key metadata fields (product ID, sensing time) are rewritten.  "
                       "The image data is untouched, so the hash still matches, but "
                       "the metadata consistency check should detect the discrepancy.",
    },
    "substitute": {
        "label": "🔄 File substitution — swap in a different image",
        "description": "The entire file is replaced with a different one.  Both the "
                       "hash and the metadata will be wrong.  This tests whether the "
                       "system can distinguish the replacement from the original.",
    },
    "signature_invalid": {
        "label": "🔑 Invalid signature — sign with a wrong key",
        "description": "The file is signed with a key that does not match the trusted "
                       "public key.  The hash may still match, but authenticity "
                       "verification should fail.",
    },
    "provenance_missing": {
        "label": "📋 Missing provenance — remove processing history",
        "description": "The provenance record is stripped of all activities and agents.  "
                       "Integrity may pass, but the provenance completeness check "
                       "should flag the record as incomplete.",
    },
    "hash_and_checksum_replaced": {
        "label": "⚠️ Image + checksum replaced (advanced)",
        "description": "Both the image AND its reference hash are replaced together.  "
                       "A naive hash comparison will incorrectly report a match.  "
                       "This demonstrates why a trusted reference source (or digital "
                       "signature) is essential.",
    },
}


# ── Tamper functions ─────────────────────────────────────────────────────────

def apply_pixel_flip(data: bytes, num_flips: int = 20) -> tuple[bytes, str]:
    """Flip *num_flips* bytes at evenly-spaced positions."""
    arr = bytearray(data)
    positions = np.linspace(100, max(len(arr) - 100, 200), num_flips, dtype=int)
    for pos in positions:
        if pos < len(arr):
            arr[pos] = (arr[pos] + 42) % 256
    return bytes(arr), f"Flipped {num_flips} pixel bytes."


def apply_metadata_tamper(meta: ProductMetadata) -> tuple[ProductMetadata, str]:
    """Return a copy with product_id and sensing_time altered."""
    tampered = copy.deepcopy(meta)
    tampered.product_id = "FAKE_PRODUCT_ID_20240101T000000"
    tampered.sensing_time = "1999-01-01T00:00:00.000Z"
    tampered.spacecraft = "Unknown-Satellite"
    return tampered, "Changed product_id, sensing_time and spacecraft."


def apply_substitute(original_data: bytes) -> tuple[bytes, str]:
    """Return random bytes of the same length — a completely different file."""
    rng = np.random.default_rng(seed=42)
    fake = rng.integers(0, 256, size=len(original_data), dtype=np.uint8).tobytes()
    return fake, "Replaced entire file content with random data."


def strip_provenance(prov: ProvenanceRecord) -> tuple[ProvenanceRecord, str]:
    """Return a provenance record with agents and activities removed."""
    stripped = copy.deepcopy(prov)
    stripped.agents = []
    stripped.activities = []
    return stripped, "Removed all agents and activities from provenance record."


def apply_hash_and_checksum_replaced(
    original_data: bytes,
    algorithm: str = "sha256",
) -> tuple[bytes, str, str]:
    """Replace the file AND compute a new 'matching' hash for it.

    Returns (fake_data, fake_hash, description).
    """
    fake_data, _ = apply_substitute(original_data)
    fake_hash = compute_hash(fake_data, algorithm)
    return (
        fake_data,
        fake_hash,
        "Replaced both the file and its reference checksum.  "
        "A simple hash comparison will see a 'match'.",
    )

