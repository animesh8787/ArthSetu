# ============================================================
# FILE: backend/app/services/connectors.py
# Read-only pull connectors. A source system may publish a CSV / JSON export
# at an https URL; the scheduled sync fetches it and feeds the normal
# ingestion paths (records -> matching, events -> status). Nothing is ever
# written back to the department.
# ============================================================

from __future__ import annotations

import csv
import io
import ipaddress
import json
import socket
import urllib.error
import urllib.request
from datetime import datetime, timezone
from typing import Any
from urllib.parse import urlparse

from sqlalchemy.orm import Session

from backend.app.db.models.source_system import SourceSystem
from backend.app.services import events_ingestion, ingestion

MAX_PULL_BYTES = 8 * 1024 * 1024
PULL_TIMEOUT_SECONDS = 20
KINDS = ("records", "events")


def validate_pull_url(url: str) -> str:
    """https only, and never a private / loopback / link-local address.

    shortcut: the host is resolved here and again by urllib, so a hostile DNS
    server could rebind in between; put the sync behind an egress proxy if the
    connector URLs stop being admin-curated.
    """
    parsed = urlparse((url or "").strip())
    if parsed.scheme != "https" or not parsed.hostname:
        raise ValueError("Connector URL must be an https:// address")
    try:
        infos = socket.getaddrinfo(parsed.hostname, parsed.port or 443, proto=socket.IPPROTO_TCP)
    except socket.gaierror:
        raise ValueError(f"Cannot resolve host '{parsed.hostname}'")
    for info in infos:
        addr = ipaddress.ip_address(info[4][0])
        if not addr.is_global:
            raise ValueError("Connector URL must point to a public address")
    return parsed.geturl()


class _NoRedirect(urllib.request.HTTPRedirectHandler):
    # A redirect could hop to an internal address after validation passed.
    def redirect_request(self, *args, **kwargs):  # noqa: D401
        return None


def _fetch(url: str) -> bytes:
    opener = urllib.request.build_opener(_NoRedirect)
    request = urllib.request.Request(url, headers={"User-Agent": "ArthSetu-connector/1.0"})
    try:
        with opener.open(request, timeout=PULL_TIMEOUT_SECONDS) as response:
            raw = response.read(MAX_PULL_BYTES + 1)
    except urllib.error.HTTPError as exc:
        raise ValueError(f"Source answered HTTP {exc.code}")
    except (urllib.error.URLError, TimeoutError, OSError) as exc:
        raise ValueError(f"Could not reach the source: {exc}")
    if len(raw) > MAX_PULL_BYTES:
        raise ValueError("Export is larger than 8 MB")
    return raw


def _json_rows(raw: bytes, key: str) -> list[dict[str, Any]]:
    try:
        data = json.loads(raw.decode("utf-8-sig"))
    except ValueError:
        raise ValueError("Export is not valid JSON")
    if isinstance(data, dict):
        data = data.get(key) or data.get("items") or data.get("data") or []
    if not isinstance(data, list) or not all(isinstance(r, dict) for r in data):
        raise ValueError(f"JSON export must be a list of objects (or {{\"{key}\": [...]}})")
    return data


def _load_rows(raw: bytes, kind: str):
    """CSV or JSON, decided by content, mapped onto our canonical columns."""
    if raw.lstrip()[:1] in (b"[", b"{"):
        dicts = _json_rows(raw, kind)
        names = sorted({k for d in dicts for k in d})
    else:
        reader = csv.DictReader(io.StringIO(raw.decode("utf-8-sig", errors="replace")))
        names = reader.fieldnames or []
        dicts = list(reader)
    if kind == "events":
        return events_ingestion.event_rows_from_dicts(names, dicts)
    return ingestion.rows_from_dicts(names, dicts)


def sync_system(db: Session, system: SourceSystem) -> dict[str, Any]:
    """Pull one system's export. Never raises: the outcome is recorded on the system."""
    summary: dict[str, Any] = {"code": system.code, "kind": system.pull_kind}
    try:
        url = validate_pull_url(system.pull_url or "")
        kind = system.pull_kind if system.pull_kind in KINDS else "records"
        rows = _load_rows(_fetch(url), kind)

        if kind == "events":
            report = events_ingestion.ingest_events(db, rows, system.code)
            summary.update(report.as_dict())
            status = f"{report.created} events added, {report.skipped_duplicates} already known"
        else:
            report = ingestion.ingest_rows(db, system.code, rows, process=False)
            tally = ingestion.run_matching_for_ids(db, report.new_record_ids)
            summary.update(report.as_dict())
            summary["matching"] = {
                "auto_link": tally.auto_link,
                "review": tally.review,
                "new_entity": tally.new_entity,
                "failed": tally.failed,
            }
            status = f"{report.created} records added, {report.skipped_duplicates} already known"
        summary["ok"] = True
    except Exception as exc:  # noqa: BLE001 - one broken feed must not stop the others
        db.rollback()
        summary.update(ok=False, error=str(exc))
        status = f"Failed: {exc}"

    system = db.merge(system)
    system.last_pull_at = datetime.now(timezone.utc)
    system.last_pull_status = status[:500]
    db.commit()
    return summary


def sync_all(db: Session, code: str | None = None) -> list[dict[str, Any]]:
    query = db.query(SourceSystem).filter(SourceSystem.pull_url.isnot(None))
    if code:
        query = query.filter(SourceSystem.code == code.upper())
    return [sync_system(db, system) for system in query.order_by(SourceSystem.code).all()]
