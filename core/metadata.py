"""
TRACE — Metadata inspection and consistency checks.

Works with:
  • Sentinel-2 XML manifests (MTD_MSIL*.xml)
  • GeoTIFF tags read via rasterio
  • A generic JSON/dict metadata model for the demo
"""

import json
import xml.etree.ElementTree as ET
from dataclasses import dataclass, field, asdict
from datetime import datetime
from typing import Any


@dataclass
class ProductMetadata:
    """Normalised metadata extracted from a satellite product."""
    product_id: str = ""
    product_type: str = ""
    sensing_time: str = ""
    processing_level: str = ""
    processing_baseline: str = ""
    spacecraft: str = ""
    orbit_number: str = ""
    tile_id: str = ""
    crs: str = ""
    cloud_cover: str = ""
    extra: dict = field(default_factory=dict)

    def to_dict(self) -> dict:
        return asdict(self)

    def to_json(self, indent: int = 2) -> str:
        return json.dumps(self.to_dict(), indent=indent)


# ── Sentinel-2 manifest parser ──────────────────────────────────────────────

_S2_NS = {
    "n1": "https://psd-14.sentinel2.eo.esa.int/PSD/User_Product_Level-1C.xsd",
    "safe": "http://www.esa.int/safe/sentinel/1.0",
}


def _metadata_from_manifest_root(root: ET.Element) -> ProductMetadata:
    """Extract normalised fields from a parsed Sentinel-2 manifest root."""

    def _find_text(xpath: str) -> str:
        for ns_prefix, ns_uri in _S2_NS.items():
            full = xpath.replace(f"{ns_prefix}:", f"{{{ns_uri}}}")
            el = root.find(full)
            if el is not None and el.text:
                return el.text.strip()
        # Fallback: try without namespace
        el = root.find(xpath.split("}")[-1] if "}" in xpath else xpath)
        if el is not None and el.text:
            return el.text.strip()
        return ""

    # Walk all elements and build a simple tag→text map for fallback
    tag_map: dict[str, str] = {}
    for el in root.iter():
        tag = el.tag.split("}")[-1] if "}" in el.tag else el.tag
        if el.text and el.text.strip():
            tag_map.setdefault(tag, el.text.strip())

    return ProductMetadata(
        product_id=tag_map.get("PRODUCT_URI", tag_map.get("PRODUCT_ID", "")),
        product_type=tag_map.get("PRODUCT_TYPE", ""),
        sensing_time=tag_map.get("PRODUCT_START_TIME", tag_map.get("DATATAKE_SENSING_START", "")),
        processing_level=tag_map.get("PROCESSING_LEVEL", ""),
        processing_baseline=tag_map.get("PROCESSING_BASELINE", ""),
        spacecraft=tag_map.get("SPACECRAFT_NAME", ""),
        orbit_number=tag_map.get("SENSING_ORBIT_NUMBER", ""),
        tile_id=tag_map.get("TILE_ID", ""),
        crs=tag_map.get("HORIZONTAL_CS_CODE", tag_map.get("HORIZONTAL_CS_NAME", "")),
        cloud_cover=tag_map.get("Cloud_Coverage_Assessment", ""),
    )


def parse_sentinel2_manifest(xml_path: str) -> ProductMetadata:
    """Best-effort extraction from an on-disk MTD_MSIL*.xml file."""
    return _metadata_from_manifest_root(ET.parse(xml_path).getroot())


def parse_sentinel2_manifest_bytes(xml_data: bytes) -> ProductMetadata:
    """Best-effort extraction from uploaded Sentinel-2 manifest bytes."""
    return _metadata_from_manifest_root(ET.fromstring(xml_data))


# ── GeoTIFF metadata via rasterio ────────────────────────────────────────────

def read_geotiff_metadata(tiff_path: str) -> ProductMetadata:
    """Extract CRS, size and tags from a GeoTIFF."""
    try:
        import rasterio
    except ImportError:
        return ProductMetadata(extra={"error": "rasterio not installed"})

    with rasterio.open(tiff_path) as src:
        tags = src.tags()
        return ProductMetadata(
            crs=str(src.crs) if src.crs else "",
            extra={
                "width": src.width,
                "height": src.height,
                "count": src.count,
                "dtype": str(src.dtypes[0]) if src.dtypes else "",
                "bounds": list(src.bounds),
                "transform": list(src.transform)[:6],
                "tags": tags,
            },
        )


def read_geotiff_metadata_bytes(tiff_data: bytes) -> ProductMetadata:
    """Extract GeoTIFF metadata from uploaded bytes without persisting a file."""
    try:
        from rasterio.io import MemoryFile
    except ImportError:
        return ProductMetadata(extra={"error": "rasterio not installed"})

    with MemoryFile(tiff_data) as memory_file:
        with memory_file.open() as src:
            tags = src.tags()
            return ProductMetadata(
                crs=str(src.crs) if src.crs else "",
                extra={
                    "width": src.width,
                    "height": src.height,
                    "count": src.count,
                    "dtype": str(src.dtypes[0]) if src.dtypes else "",
                    "bounds": list(src.bounds),
                    "transform": list(src.transform)[:6],
                    "tags": tags,
                },
            )


# ── Demo / synthetic metadata ───────────────────────────────────────────────

def create_demo_metadata(
    product_id: str = "S2B_MSIL1C_20240315T103021_N0510_R108_T32TQM_20240315T123456",
    sensing_time: str = "2024-03-15T10:30:21.024Z",
) -> ProductMetadata:
    """Return a plausible Sentinel-2 metadata record for demonstration."""
    return ProductMetadata(
        product_id=product_id,
        product_type="S2MSI1C",
        sensing_time=sensing_time,
        processing_level="Level-1C",
        processing_baseline="05.10",
        spacecraft="Sentinel-2B",
        orbit_number="12345",
        tile_id="T32TQM",
        crs="EPSG:32632",
        cloud_cover="12.34",
    )


# ── Metadata consistency checks ─────────────────────────────────────────────

@dataclass
class MetadataCheckResult:
    field: str
    expected: str
    observed: str
    match: bool
    detail: str = ""


def check_metadata_consistency(
    expected: ProductMetadata,
    observed: ProductMetadata,
    fields: list[str] | None = None,
) -> list[MetadataCheckResult]:
    """Compare two metadata records field by field.

    If *fields* is ``None`` all non-empty expected fields are checked.
    """
    if fields is None:
        fields = [
            "product_id",
            "product_type",
            "sensing_time",
            "processing_level",
            "processing_baseline",
            "spacecraft",
            "crs",
        ]

    results = []
    exp_dict = expected.to_dict()
    obs_dict = observed.to_dict()

    for f in fields:
        e = str(exp_dict.get(f, ""))
        o = str(obs_dict.get(f, ""))
        if not e:
            continue  # nothing to compare against
        match = e == o
        results.append(MetadataCheckResult(
            field=f,
            expected=e,
            observed=o,
            match=match,
            detail="" if match else f"Expected '{e}', got '{o}'",
        ))

    return results

