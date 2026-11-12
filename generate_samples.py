"""
TRACE — Sample data generator.

Creates a small synthetic GeoTIFF (or plain TIFF) so the project can be
demonstrated without requiring a real Sentinel-2 download.  If rasterio
is installed a proper GeoTIFF with CRS is produced; otherwise a regular
TIFF via Pillow is created.
"""

import json
import os
import numpy as np
from PIL import Image

from config import SAMPLE_DIR
from core.hashing import compute_hash
from core.metadata import ProductMetadata, create_demo_metadata
from core.provenance import create_demo_provenance
from core.signatures import generate_ed25519, sign_data, save_key_pair


SAMPLE_IMAGE = os.path.join(SAMPLE_DIR, "sample_sentinel2.tif")
SAMPLE_META_JSON = os.path.join(SAMPLE_DIR, "sample_metadata.json")
SAMPLE_PROV_JSON = os.path.join(SAMPLE_DIR, "sample_provenance.json")
SAMPLE_HASH_JSON = os.path.join(SAMPLE_DIR, "sample_trusted_hashes.json")
SAMPLE_SIG = os.path.join(SAMPLE_DIR, "sample_signature.bin")


def _generate_synthetic_image(path: str, width: int = 256, height: int = 256) -> None:
    """Create a small 3-band image that vaguely resembles a satellite tile."""
    rng = np.random.default_rng(seed=2024)

    # Create a synthetic landscape pattern
    x = np.linspace(0, 4 * np.pi, width)
    y = np.linspace(0, 4 * np.pi, height)
    xx, yy = np.meshgrid(x, y)

    # Band simulation (NIR-like, Red, Green)
    b1 = (np.sin(xx) * np.cos(yy) * 0.3 + 0.5) * 200 + rng.normal(0, 5, (height, width))
    b2 = (np.cos(xx * 0.7) * 0.3 + 0.4) * 160 + rng.normal(0, 5, (height, width))
    b3 = (np.sin(yy * 0.5) * 0.2 + 0.35) * 140 + rng.normal(0, 5, (height, width))

    bands = np.stack([
        np.clip(b1, 0, 255).astype(np.uint8),
        np.clip(b2, 0, 255).astype(np.uint8),
        np.clip(b3, 0, 255).astype(np.uint8),
    ], axis=-1)

    # Try GeoTIFF with rasterio first
    try:
        import rasterio
        from rasterio.transform import from_bounds
        from rasterio.crs import CRS

        transform = from_bounds(11.0, 47.0, 12.0, 48.0, width, height)
        with rasterio.open(
            path,
            "w",
            driver="GTiff",
            height=height,
            width=width,
            count=3,
            dtype="uint8",
            crs=CRS.from_epsg(32632),
            transform=transform,
        ) as dst:
            for i in range(3):
                dst.write(bands[:, :, i], i + 1)
        return
    except ImportError:
        pass

    # Fallback: plain TIFF via Pillow
    img = Image.fromarray(bands, mode="RGB")
    img.save(path, format="TIFF")


def generate_samples(force: bool = False) -> dict[str, str]:
    """Create all sample files and return a dict of paths.

    Skips generation if files already exist unless *force* is True.
    """
    paths: dict[str, str] = {}

    # 1. Image
    if force or not os.path.exists(SAMPLE_IMAGE):
        _generate_synthetic_image(SAMPLE_IMAGE)
    paths["image"] = SAMPLE_IMAGE

    # Read image bytes for hashing / signing
    with open(SAMPLE_IMAGE, "rb") as f:
        image_bytes = f.read()

    # 2. Hashes (trusted reference)
    hashes = {
        "sha256": compute_hash(image_bytes, "sha256"),
        "sha3_256": compute_hash(image_bytes, "sha3_256"),
        "blake2b": compute_hash(image_bytes, "blake2b"),
    }
    with open(SAMPLE_HASH_JSON, "w") as f:
        json.dump(hashes, f, indent=2)
    paths["hashes"] = SAMPLE_HASH_JSON

    # 3. Metadata
    meta = create_demo_metadata()
    with open(SAMPLE_META_JSON, "w") as f:
        f.write(meta.to_json())
    paths["metadata"] = SAMPLE_META_JSON

    # 4. Provenance
    prov = create_demo_provenance(
        product_id=meta.product_id,
        file_hash=hashes["sha256"],
        hash_algorithm="sha256",
    )
    with open(SAMPLE_PROV_JSON, "w") as f:
        f.write(prov.to_json())
    paths["provenance"] = SAMPLE_PROV_JSON

    # 5. Digital signature (Ed25519)
    kp = generate_ed25519()
    save_key_pair(kp, label="demo")
    sig = sign_data(image_bytes, kp.private_pem, "Ed25519")
    with open(SAMPLE_SIG, "wb") as f:
        f.write(sig)
    paths["signature"] = SAMPLE_SIG

    return paths

