"""
TRACE — Verification pipeline.

Orchestrates integrity, metadata, authenticity and provenance checks,
produces a structured VerificationReport.
"""

import json
import os
import time
from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone
from typing import Any

from core.hashing import compute_hash, verify_hash
from core.metadata import (
    ProductMetadata,
    MetadataCheckResult,
    check_metadata_consistency,
)
from core.provenance import ProvenanceRecord
from core.signatures import verify_signature
from config import VERDICT_PASS, VERDICT_FAIL, VERDICT_UNVERIFIED


@dataclass
class CheckResult:
    """One check inside a verification report."""
    name: str
    passed: bool | None  # None → could not be evaluated
    detail: str = ""
    expected: str = ""
    observed: str = ""
    elapsed_ms: float = 0.0


@dataclass
class VerificationReport:
    """Aggregated result of the full pipeline."""
    product_id: str = ""
    timestamp: str = field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )
    overall_verdict: str = VERDICT_UNVERIFIED
    checks: list[CheckResult] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    total_elapsed_ms: float = 0.0

    def add(self, check: CheckResult) -> None:
        self.checks.append(check)

    def finalise(self) -> None:
        """Set overall verdict from individual checks."""
        evaluated = [c for c in self.checks if c.passed is not None]
        if any(c.passed is False for c in self.checks):
            self.overall_verdict = VERDICT_FAIL
        elif not evaluated or any(c.passed is None for c in self.checks):
            self.overall_verdict = VERDICT_UNVERIFIED
        else:
            self.overall_verdict = VERDICT_PASS

    def to_dict(self) -> dict:
        return asdict(self)

    def to_json(self, indent: int = 2) -> str:
        return json.dumps(self.to_dict(), indent=indent, default=str)

    def summary_table(self) -> list[dict[str, str]]:
        """Return a list of dicts suitable for ``st.table``."""
        rows = []
        for c in self.checks:
            status = "✅ Pass" if c.passed else ("❌ Fail" if c.passed is False else "⚠️ N/A")
            rows.append({
                "Check": c.name,
                "Status": status,
                "Detail": c.detail[:120],
            })
        return rows


# ── Pipeline runner ──────────────────────────────────────────────────────────

def run_verification(
    file_data: bytes,
    *,
    expected_hash: str = "",
    hash_algorithm: str = "sha256",
    expected_metadata: ProductMetadata | None = None,
    observed_metadata: ProductMetadata | None = None,
    signature: bytes | None = None,
    public_key_pem: bytes | None = None,
    sig_algorithm: str = "Ed25519",
    provenance: ProvenanceRecord | None = None,
) -> VerificationReport:
    """Execute the full TRACE verification pipeline."""
    report = VerificationReport()
    t0 = time.perf_counter()

    # ── Step 1  Integrity (hash) ─────────────────────────────────────────
    if expected_hash:
        t1 = time.perf_counter()
        match, computed = verify_hash(file_data, expected_hash, hash_algorithm)
        elapsed = (time.perf_counter() - t1) * 1000
        report.add(CheckResult(
            name="Integrity — hash comparison",
            passed=match,
            detail=f"{hash_algorithm.upper()} {'matches' if match else 'MISMATCH'}",
            expected=expected_hash[:24] + "…",
            observed=computed[:24] + "…",
            elapsed_ms=round(elapsed, 2),
        ))
    else:
        computed = compute_hash(file_data, hash_algorithm)
        report.add(CheckResult(
            name="Integrity — hash comparison",
            passed=None,
            detail="No trusted reference hash provided — cannot verify integrity.",
            observed=computed[:24] + "…",
        ))
        report.warnings.append(
            "No trusted reference hash was available. The computed hash is "
            "informational only and does NOT prove the file is genuine."
        )

    # ── Step 2  Metadata consistency ─────────────────────────────────────
    if expected_metadata and observed_metadata:
        t1 = time.perf_counter()
        meta_results = check_metadata_consistency(expected_metadata, observed_metadata)
        elapsed = (time.perf_counter() - t1) * 1000
        all_ok = all(r.match for r in meta_results)
        mismatches = [r for r in meta_results if not r.match]
        detail_parts = []
        if mismatches:
            for m in mismatches:
                detail_parts.append(f"{m.field}: expected '{m.expected}', got '{m.observed}'")
        else:
            detail_parts.append(f"All {len(meta_results)} checked fields match.")

        report.add(CheckResult(
            name="Metadata consistency",
            passed=all_ok,
            detail="; ".join(detail_parts),
            elapsed_ms=round(elapsed, 2),
        ))
    else:
        report.add(CheckResult(
            name="Metadata consistency",
            passed=None,
            detail="Metadata comparison not configured for this run.",
        ))

    # ── Step 3  Authenticity (digital signature) ─────────────────────────
    if signature is not None and public_key_pem is not None:
        t1 = time.perf_counter()
        sig_ok = verify_signature(file_data, signature, public_key_pem, sig_algorithm)
        elapsed = (time.perf_counter() - t1) * 1000
        report.add(CheckResult(
            name="Authenticity — digital signature",
            passed=sig_ok,
            detail=f"{sig_algorithm} signature {'valid' if sig_ok else 'INVALID'}",
            elapsed_ms=round(elapsed, 2),
        ))
    else:
        report.add(CheckResult(
            name="Authenticity — digital signature",
            passed=None,
            detail="No signature or public key supplied — cannot verify authenticity.",
        ))

    # ── Step 4  Provenance completeness ──────────────────────────────────
    if provenance is not None:
        t1 = time.perf_counter()
        issues = provenance.check_completeness()
        elapsed = (time.perf_counter() - t1) * 1000
        warnings_or_errors = [i for i in issues if i["severity"] in ("warning", "error")]
        if warnings_or_errors:
            detail = "; ".join(i["message"] for i in warnings_or_errors)
            report.add(CheckResult(
                name="Provenance completeness",
                passed=False,
                detail=detail,
                elapsed_ms=round(elapsed, 2),
            ))
        else:
            info_notes = [i for i in issues if i["severity"] == "info"]
            detail = "Provenance record is complete."
            if info_notes:
                detail += " Notes: " + "; ".join(i["message"] for i in info_notes)
            report.add(CheckResult(
                name="Provenance completeness",
                passed=True,
                detail=detail,
                elapsed_ms=round(elapsed, 2),
            ))
    else:
        report.add(CheckResult(
            name="Provenance completeness",
            passed=None,
            detail="No provenance record supplied.",
        ))

    # ── Finalise ─────────────────────────────────────────────────────────
    report.total_elapsed_ms = round((time.perf_counter() - t0) * 1000, 2)
    report.finalise()
    return report
