"""
TRACE — Provenance record model (W3C PROV-inspired).

Tracks the lineage of a data product: who created it, which activities
transformed it, which entities were derived from which.

This is a simplified, JSON-serialisable model suitable for demonstration.
A production system would use a proper PROV-O / PROV-JSON library.
"""

import json
import uuid
from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone
from typing import Any


@dataclass
class Agent:
    """An actor (person, software, organisation)."""
    id: str
    name: str
    type: str = "Software"  # Software | Person | Organisation


@dataclass
class Activity:
    """A processing step."""
    id: str
    label: str
    started: str = ""
    ended: str = ""
    agent_id: str = ""
    parameters: dict = field(default_factory=dict)


@dataclass
class Entity:
    """A data artefact (file, product, etc.)."""
    id: str
    label: str
    generated_by: str = ""          # activity id
    derived_from: str = ""          # entity id
    hash_value: str = ""
    hash_algorithm: str = ""
    attributes: dict = field(default_factory=dict)


@dataclass
class ProvenanceRecord:
    """Complete provenance document for one product."""
    document_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    created: str = field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )
    agents: list[Agent] = field(default_factory=list)
    activities: list[Activity] = field(default_factory=list)
    entities: list[Entity] = field(default_factory=list)

    # ── helpers ──────────────────────────────────────────────────────────
    def add_agent(self, **kw) -> Agent:
        a = Agent(**kw)
        self.agents.append(a)
        return a

    def add_activity(self, **kw) -> Activity:
        a = Activity(**kw)
        self.activities.append(a)
        return a

    def add_entity(self, **kw) -> Entity:
        e = Entity(**kw)
        self.entities.append(e)
        return e

    def to_dict(self) -> dict:
        return asdict(self)

    def to_json(self, indent: int = 2) -> str:
        return json.dumps(self.to_dict(), indent=indent)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "ProvenanceRecord":
        """Load a TRACE/W3C-PROV-inspired JSON record supplied by a user."""
        return cls(
            document_id=str(data.get("document_id", "")) or str(uuid.uuid4()),
            created=str(data.get("created", "")),
            agents=[Agent(**item) for item in data.get("agents", [])],
            activities=[Activity(**item) for item in data.get("activities", [])],
            entities=[Entity(**item) for item in data.get("entities", [])],
        )

    # ── completeness check ───────────────────────────────────────────────
    def check_completeness(self) -> list[dict[str, Any]]:
        """Return a list of issues found in the provenance record."""
        issues: list[dict[str, Any]] = []

        if not self.agents:
            issues.append({
                "severity": "warning",
                "message": "No agents recorded — cannot attribute processing.",
            })

        if not self.activities:
            issues.append({
                "severity": "warning",
                "message": "No activities recorded — processing history unknown.",
            })

        for ent in self.entities:
            if not ent.hash_value:
                issues.append({
                    "severity": "info",
                    "message": f"Entity '{ent.label}' has no recorded hash.",
                })
            if not ent.generated_by:
                issues.append({
                    "severity": "info",
                    "message": f"Entity '{ent.label}' is not linked to a generating activity.",
                })

        return issues


# ── Demo provenance factory ──────────────────────────────────────────────────

def create_demo_provenance(
    product_id: str = "S2B_MSIL1C_20240315T103021_N0510_R108_T32TQM_20240315T123456",
    file_hash: str = "",
    hash_algorithm: str = "sha256",
) -> ProvenanceRecord:
    """Build a realistic-looking provenance chain for the demonstration."""
    prov = ProvenanceRecord()

    # Agents
    esa = prov.add_agent(id="agent:esa", name="European Space Agency", type="Organisation")
    s2_processor = prov.add_agent(id="agent:s2-pdgs", name="Sentinel-2 PDGS", type="Software")
    trace = prov.add_agent(id="agent:trace", name="TRACE Verification System", type="Software")

    # Activities
    acquire = prov.add_activity(
        id="activity:acquisition",
        label="Satellite image acquisition",
        started="2024-03-15T10:30:21Z",
        ended="2024-03-15T10:30:21Z",
        agent_id=esa.id,
    )
    l1c = prov.add_activity(
        id="activity:l1c-processing",
        label="Level-1C processing",
        started="2024-03-15T12:00:00Z",
        ended="2024-03-15T12:34:56Z",
        agent_id=s2_processor.id,
        parameters={"baseline": "05.10"},
    )
    verify = prov.add_activity(
        id="activity:verification",
        label="TRACE integrity verification",
        started=datetime.now(timezone.utc).isoformat(),
        agent_id=trace.id,
    )

    # Entities
    raw = prov.add_entity(
        id="entity:raw-data",
        label="Raw instrument data",
        generated_by=acquire.id,
    )
    product = prov.add_entity(
        id=f"entity:{product_id}",
        label=product_id,
        generated_by=l1c.id,
        derived_from=raw.id,
        hash_value=file_hash,
        hash_algorithm=hash_algorithm,
    )

    return prov

