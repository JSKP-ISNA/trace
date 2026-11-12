"""TRACE - evidence-based verification for remote-sensing products."""

import io
import json
import os
import sys
import zipfile

import streamlit as st

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from config import HASH_ALGORITHMS, VERDICT_FAIL, VERDICT_PASS
from core.metadata import (
    ProductMetadata,
    parse_sentinel2_manifest_bytes,
    read_geotiff_metadata_bytes,
)
from core.provenance import ProvenanceRecord
from core.verification import run_verification


st.set_page_config(page_title="TRACE - Remote Sensing Verification", page_icon="Satellite", layout="wide")
st.title("TRACE - Remote-Sensing Data Verification")
st.caption("Evidence-based verification. TRACE never creates trusted evidence for an uploaded product.")

with st.sidebar:
    st.header("Verification settings")
    hash_choice = st.selectbox("Checksum algorithm", list(HASH_ALGORITHMS))
    hash_algorithm = HASH_ALGORITHMS[hash_choice]
    if hash_algorithm == "md5":
        st.warning("MD5 is accepted only to compare a source-published legacy checksum; it is not suitable as a modern security hash.")
    signature_algorithm = st.selectbox("Detached signature algorithm", ["Ed25519", "ECDSA-P256", "RSA-2048"])
    st.divider()
    st.caption("Any unavailable check keeps the verdict UNVERIFIED. No attack simulation is run in this mode.")

uploaded = st.file_uploader(
    "Product to verify",
    type=["tif", "tiff", "jp2", "png", "jpg", "zip", "xml"],
    help="Upload the exact file covered by the official checksum or detached signature.",
)
if uploaded is None:
    st.info("Upload a Sentinel product, SAFE ZIP, manifest, or raster to start.")
    st.stop()

file_data = uploaded.getvalue()
file_name = uploaded.name
suffix = os.path.splitext(file_name)[1].lower()
st.success(f"Uploaded {file_name} ({len(file_data):,} bytes)")

st.header("Independent trusted evidence")
st.warning(
    "Obtain evidence independently from the uploaded data, for example from the Copernicus download record, "
    "a signed catalogue, or a controlled archive. A checksum you calculate locally is not a trusted reference."
)

reference_hash = st.text_input(
    "Official checksum for this exact file",
    help="Paste the source-published checksum. Select its algorithm in the sidebar.",
).strip().lower()
checksum_file = st.file_uploader("Or upload an official checksum file", type=["sha256", "sha3", "txt", "checksum"])
if checksum_file is not None:
    checksum_tokens = checksum_file.getvalue().decode("utf-8", errors="replace").split()
    if checksum_tokens:
        reference_hash = checksum_tokens[0].lower()

reference_manifest_file = st.file_uploader(
    "Trusted Sentinel-2 manifest (MTD_MSIL*.xml, optional)",
    type=["xml"],
    help="A manifest from an independently trusted reference product.",
)
signature_file = st.file_uploader("Detached signature (optional)", type=["sig", "bin"])
public_key_file = st.file_uploader("Trusted signer public key PEM (optional)", type=["pem", "pub"])
provenance_file = st.file_uploader("Provenance record JSON (optional)", type=["json"])


def extract_uploaded_metadata(data: bytes, extension: str) -> tuple[ProductMetadata | None, str]:
    """Read metadata physically contained in the uploaded product."""
    try:
        if extension in {".tif", ".tiff"}:
            return read_geotiff_metadata_bytes(data), "Extracted GeoTIFF CRS, dimensions, and embedded tags."
        if extension == ".xml":
            return parse_sentinel2_manifest_bytes(data), "Extracted the uploaded Sentinel-2 manifest."
        if extension == ".zip":
            with zipfile.ZipFile(io.BytesIO(data)) as archive:
                manifests = [
                    name for name in archive.namelist()
                    if os.path.basename(name).upper().startswith("MTD_MSIL") and name.lower().endswith(".xml")
                ]
                if manifests:
                    return parse_sentinel2_manifest_bytes(archive.read(manifests[0])), f"Extracted {manifests[0]}."
                return None, "ZIP has no MTD_MSIL*.xml Sentinel-2 manifest."
        return None, "No metadata parser is available for this file type."
    except Exception as exc:
        return None, f"Metadata extraction failed: {exc}"


observed_metadata, metadata_note = extract_uploaded_metadata(file_data, suffix)
expected_metadata: ProductMetadata | None = None
if reference_manifest_file is not None:
    try:
        expected_metadata = parse_sentinel2_manifest_bytes(reference_manifest_file.getvalue())
    except Exception as exc:
        st.error(f"Trusted manifest could not be parsed: {exc}")

provenance: ProvenanceRecord | None = None
if provenance_file is not None:
    try:
        provenance = ProvenanceRecord.from_dict(json.loads(provenance_file.getvalue()))
    except (json.JSONDecodeError, TypeError, ValueError) as exc:
        st.error(f"Provenance JSON is invalid: {exc}")

st.info(metadata_note)
with st.expander("Observed product metadata"):
    st.json(observed_metadata.to_dict() if observed_metadata else {})
with st.expander("Trusted reference metadata"):
    st.json(expected_metadata.to_dict() if expected_metadata else {})

st.header("Verification results")
report = run_verification(
    file_data=file_data,
    expected_hash=reference_hash,
    hash_algorithm=hash_algorithm,
    expected_metadata=expected_metadata,
    observed_metadata=observed_metadata,
    signature=signature_file.getvalue() if signature_file else None,
    public_key_pem=public_key_file.getvalue() if public_key_file else None,
    sig_algorithm=signature_algorithm,
    provenance=provenance,
)

if report.overall_verdict == VERDICT_PASS:
    st.success("VERDICT: PASS - every check passed and no evidence category is missing.")
elif report.overall_verdict == VERDICT_FAIL:
    st.error("VERDICT: FAIL - supplied evidence does not validate this product.")
else:
    st.warning("VERDICT: UNVERIFIED - independently trusted evidence is missing or could not be evaluated.")

for check in report.checks:
    status = "PASS" if check.passed is True else "FAIL" if check.passed is False else "NOT VERIFIED"
    with st.expander(f"{status}: {check.name}", expanded=True):
        st.write(check.detail)
        if check.expected:
            st.caption(f"Expected: {check.expected}")
        if check.observed:
            st.caption(f"Observed: {check.observed}")

for warning in report.warnings:
    st.warning(warning)

st.header("Decision summary")
st.table(report.summary_table())
st.metric("Total verification time", f"{report.total_elapsed_ms:.1f} ms")
st.download_button(
    "Download verification report",
    data=report.to_json(),
    file_name=f"trace_report_{file_name}.json",
    mime="application/json",
)
