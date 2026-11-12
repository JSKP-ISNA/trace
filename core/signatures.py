"""
TRACE — Digital-signature generation and verification (demonstration).

Uses Ed25519 for the default demo key pair.  RSA and ECDSA helpers are
included so you can compare algorithms in your experiments.
"""

from cryptography.hazmat.primitives.asymmetric import ed25519, ec, rsa, padding, utils
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.exceptions import InvalidSignature
from dataclasses import dataclass
import os

from config import KEYS_DIR


@dataclass
class KeyPair:
    """Holds a serialised key pair for demonstration purposes."""
    algorithm: str
    private_pem: bytes
    public_pem: bytes


# ── Key generation helpers ───────────────────────────────────────────────────

def generate_ed25519() -> KeyPair:
    priv = ed25519.Ed25519PrivateKey.generate()
    priv_pem = priv.private_bytes(
        serialization.Encoding.PEM,
        serialization.PrivateFormat.PKCS8,
        serialization.NoEncryption(),
    )
    pub_pem = priv.public_key().public_bytes(
        serialization.Encoding.PEM,
        serialization.PublicFormat.SubjectPublicKeyInfo,
    )
    return KeyPair("Ed25519", priv_pem, pub_pem)


def generate_ecdsa() -> KeyPair:
    priv = ec.generate_private_key(ec.SECP256R1())
    priv_pem = priv.private_bytes(
        serialization.Encoding.PEM,
        serialization.PrivateFormat.PKCS8,
        serialization.NoEncryption(),
    )
    pub_pem = priv.public_key().public_bytes(
        serialization.Encoding.PEM,
        serialization.PublicFormat.SubjectPublicKeyInfo,
    )
    return KeyPair("ECDSA-P256", priv_pem, pub_pem)


def generate_rsa(key_size: int = 2048) -> KeyPair:
    priv = rsa.generate_private_key(public_exponent=65537, key_size=key_size)
    priv_pem = priv.private_bytes(
        serialization.Encoding.PEM,
        serialization.PrivateFormat.PKCS8,
        serialization.NoEncryption(),
    )
    pub_pem = priv.public_key().public_bytes(
        serialization.Encoding.PEM,
        serialization.PublicFormat.SubjectPublicKeyInfo,
    )
    return KeyPair(f"RSA-{key_size}", priv_pem, pub_pem)


# ── Signing / verification ──────────────────────────────────────────────────

def sign_data(data: bytes, private_pem: bytes, algorithm: str = "Ed25519") -> bytes:
    """Sign *data* and return the raw signature bytes."""
    priv = serialization.load_pem_private_key(private_pem, password=None)
    if algorithm == "Ed25519":
        return priv.sign(data)
    elif algorithm.startswith("ECDSA"):
        return priv.sign(data, ec.ECDSA(hashes.SHA256()))
    elif algorithm.startswith("RSA"):
        return priv.sign(data, padding.PSS(
            mgf=padding.MGF1(hashes.SHA256()),
            salt_length=padding.PSS.MAX_LENGTH,
        ), hashes.SHA256())
    raise ValueError(f"Unsupported algorithm: {algorithm}")


def verify_signature(
    data: bytes,
    signature: bytes,
    public_pem: bytes,
    algorithm: str = "Ed25519",
) -> bool:
    """Return True if the signature is valid for *data*."""
    pub = serialization.load_pem_public_key(public_pem)
    try:
        if algorithm == "Ed25519":
            pub.verify(signature, data)
        elif algorithm.startswith("ECDSA"):
            pub.verify(signature, data, ec.ECDSA(hashes.SHA256()))
        elif algorithm.startswith("RSA"):
            pub.verify(signature, data, padding.PSS(
                mgf=padding.MGF1(hashes.SHA256()),
                salt_length=padding.PSS.MAX_LENGTH,
            ), hashes.SHA256())
        else:
            raise ValueError(f"Unsupported algorithm: {algorithm}")
        return True
    except (InvalidSignature, TypeError, ValueError, AttributeError):
        return False


# ── Persistence helpers ──────────────────────────────────────────────────────

def save_key_pair(kp: KeyPair, label: str = "demo") -> None:
    """Write PEM files into the keys/ directory."""
    priv_path = os.path.join(KEYS_DIR, f"{label}_{kp.algorithm}_private.pem")
    pub_path = os.path.join(KEYS_DIR, f"{label}_{kp.algorithm}_public.pem")
    with open(priv_path, "wb") as f:
        f.write(kp.private_pem)
    with open(pub_path, "wb") as f:
        f.write(kp.public_pem)


def load_public_key(label: str, algorithm: str = "Ed25519") -> bytes:
    pub_path = os.path.join(KEYS_DIR, f"{label}_{algorithm}_public.pem")
    with open(pub_path, "rb") as f:
        return f.read()


def load_private_key(label: str, algorithm: str = "Ed25519") -> bytes:
    priv_path = os.path.join(KEYS_DIR, f"{label}_{algorithm}_private.pem")
    with open(priv_path, "rb") as f:
        return f.read()
