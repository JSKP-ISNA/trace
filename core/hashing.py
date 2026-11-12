"""
TRACE — Cryptographic hash computation.

Supports SHA-256, SHA3-256 and BLAKE2b.
Reads files in 64 KiB chunks so large rasters stay memory-friendly.
"""

import hashlib
from typing import BinaryIO

CHUNK_SIZE = 65_536  # 64 KiB


def compute_hash(data: bytes | BinaryIO, algorithm: str = "sha256") -> str:
    """Return the hex digest of *data* using the specified algorithm.

    Parameters
    ----------
    data : bytes or file-like
        Raw bytes, or a readable binary stream.
    algorithm : str
        Any name accepted by ``hashlib.new()`` — e.g. ``"sha256"``,
        ``"sha3_256"``, ``"blake2b"``.

    Returns
    -------
    str
        Lower-case hex digest.
    """
    h = hashlib.new(algorithm)

    if isinstance(data, bytes):
        h.update(data)
    else:
        # file-like → read in chunks
        while True:
            chunk = data.read(CHUNK_SIZE)
            if not chunk:
                break
            h.update(chunk)

    return h.hexdigest()


def compute_file_hash(path: str, algorithm: str = "sha256") -> str:
    """Convenience wrapper: hash a file given its path."""
    with open(path, "rb") as fh:
        return compute_hash(fh, algorithm)


def verify_hash(
    data: bytes | BinaryIO,
    expected: str,
    algorithm: str = "sha256",
) -> tuple[bool, str]:
    """Compare a computed hash with an expected reference value.

    Returns
    -------
    (match, computed_hex)
    """
    computed = compute_hash(data, algorithm)
    return computed == expected.lower(), computed

