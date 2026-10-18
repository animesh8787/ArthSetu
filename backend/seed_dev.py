"""
Self-contained development seeder for ArthSetu.

Builds a coherent synthetic ecosystem in the configured database
(SQLite by default), then runs the real status engine so every
business gets a genuine status snapshot + audit trail.

Run from the repo root:
    python -m backend.seed_dev            # seed if empty
    python -m backend.seed_dev --reset    # drop + recreate + seed

Refuses to run at all when APP_ENV=production (drops tables, installs
publicly-known demo passwords) unless --force-production-seed is passed.

Requires a Firebase Auth target to create the demo users against — either
the local emulator (FIREBASE_AUTH_EMULATOR_HOST, the normal dev case; run
`firebase emulators:start --only auth` first) or a real project via
FIREBASE_CREDENTIALS_JSON. The placeholder emails below (@arthsetu.local)
are fine for the emulator; edit DEMO_USERS if seeding a real project.
"""

from __future__ import annotations

import argparse
import os
import random
import string
import uuid
from datetime import datetime, timedelta, timezone

from backend.app.core.config import settings
from backend.app.db.base import Base
from backend.app.db.session import SessionLocal, engine
from backend.app.db import models  # noqa: F401  (register tables)
from backend.app.db.models.activity_event import ActivityEvent
from backend.app.db.models.business_entity import BusinessEntity
from backend.app.db.models.entity_record_link import EntityRecordLink
from backend.app.db.models.review_case import ReviewCase
from backend.app.db.models.source_record import SourceRecord
from backend.app.db.models.source_system import SourceSystem
from backend.app.db.models.user import User
from backend.app.db.enums import (
    EntityStatusEnum,
    EventTypeEnum,
    ReviewCaseStatusEnum,
    UserRole,
)
from backend.app.core import firebase
from backend.app.core.config import settings
from backend.app.services.matching_engine import process_source_record
from backend.app.services.scoring import normalize_address
from backend.app.services.status_engine import infer_business_status

# email, full name, role, password — edit the emails if seeding a real
# Firebase project rather than the local emulator.
DEMO_USERS = [
    ("admin@arthsetu.local", "System Administrator", UserRole.ADMIN, "arthsetu-admin"),
    ("reviewer@arthsetu.local", "Priya Menon", UserRole.REVIEWER, "arthsetu-review"),
    ("reviewer2@arthsetu.local", "Rohit Sharma", UserRole.REVIEWER, "arthsetu-review"),
    ("officer@arthsetu.local", "Anjali Rao", UserRole.VIEWER, "arthsetu-view"),
]

SEED = 42
random.seed(SEED)

DISTRICTS = [
    "Patiala", "Ludhiana", "Mohali", "Amritsar",
    "Bathinda", "Jalandhar", "Rajpura", "Mandi Gobindgarh",
]
SECTORS = [
    "Retail", "Manufacturing", "Restaurant", "Healthcare", "Education",
    "Fitness", "Automobile", "Warehouse", "Textile", "Agriculture",
]
PREFIXES = ["Sharma", "Gupta", "Singh", "Verma", "Aggarwal", "Punjab",
            "Royal", "Green", "Om", "Sai"]
SUFFIXES = ["Traders", "Industries", "Rice Mill", "Foods", "Medical Store",
            "Gym", "Auto Works", "Textiles", "Enterprises", "Steel Works"]

SYSTEMS = [
    ("LABOUR", "Shops Registration Portal", "Labour Department"),
    ("MUNICIPAL", "Trade License Registry", "Municipal Department"),
    ("POLLUTION", "Consent Monitoring System", "Pollution Control Board"),
    ("POWER", "Commercial Consumer Ledger", "Electricity Board"),
]

TOTAL_BUSINESSES = 140
NOW = datetime.now(timezone.utc)


def _pan() -> str:
    return (
        "".join(random.choices(string.ascii_uppercase, k=5))
        + "".join(random.choices(string.digits, k=4))
        + random.choice(string.ascii_uppercase)
    )


def _gstin(pan: str) -> str:
    return f"{random.choice(['03', '04', '06'])}{pan}{random.randint(1, 9)}Z" \
           f"{random.choice(string.ascii_uppercase + string.digits)}"


def _normalize(name: str) -> str:
    return " ".join(name.lower().split())


def _phone() -> str:
    return random.choice("6789") + "".join(random.choices(string.digits, k=9))


def _noisy_phone(phone: str) -> str:
    return random.choice([phone, f"+91 {phone[:5]} {phone[5:]}", f"0{phone}", f"{phone[:4]}-{phone[4:]}"])


def _email(name: str) -> str:
    slug = "".join(c for c in name.lower() if c.isalnum())[:18] or "unit"
    return f"accounts@{slug}.example"


def _noisy(name: str) -> str:
    return random.choice([
        name.upper(), name.lower(), f"M/S {name}",
        name.replace("Works", "Wrks"), name.replace("Industries", "Inds"),
        name,
    ])


AREAS = [
    "Industrial Area Phase", "Focal Point", "GT Road", "Model Town",
    "Civil Lines", "Grain Market", "Mall Road", "Adarsh Nagar",
    "Guru Nanak Colony", "Sabzi Mandi",
]
DISTRICT_PINS = {
    "Patiala": "147001", "Ludhiana": "141001", "Mohali": "160055",
    "Amritsar": "143001", "Bathinda": "151001", "Jalandhar": "144001",
    "Rajpura": "140401", "Mandi Gobindgarh": "147301",
}


def _address(district: str) -> str:
    return (
        f"Plot {random.randint(1, 480)}, {random.choice(AREAS)} "
        f"{random.randint(1, 8)}, {district}, Punjab"
    )


def _noisy_address(address: str) -> str:
    """A departmental transcription of the same address."""
    variants = [
        address,
        address.upper(),
        address.replace("Plot", "Shop").replace("Phase", "Ph"),
        address.split(",")[0] + ", " + address.split(",")[-2].strip(),  # drop area
        address.replace(", Punjab", ""),
    ]
    return random.choice(variants)


def _noisy_pin(pin: str) -> str:
    # occasionally a digit-transposed / partial PIN
    roll = random.random()
    if roll < 0.75:
        return pin
    if roll < 0.9 and len(pin) == 6:
        return pin[:5] + str((int(pin[5]) + 1) % 10)  # last-digit typo
    return ""  # missing on this record


ARCHETYPES = ["active"] * 62 + ["dormant"] * 25 + ["closed"] * 13


POSITIVE_EVENTS = [
    EventTypeEnum.GST_FILED, EventTypeEnum.LICENSE_RENEWED,
    EventTypeEnum.POWER_USAGE, EventTypeEnum.INSPECTION,
    EventTypeEnum.EMPLOYEE_FILING, EventTypeEnum.PAYMENT_RECEIVED,
]


def _spread_ages(n: int, oldest: int, newest: int = 1) -> list[int]:
    """n event ages (days) roughly uniform across a business's lifetime."""
    if n <= 0:
        return []
    step = (oldest - newest) / n
    return [
        int(oldest - step * i - random.uniform(0, step))
        for i in range(n)
    ]


def _activity_for(archetype: str) -> list[tuple[EventTypeEnum, float, datetime]]:
    events: list[tuple[EventTypeEnum, float, datetime]] = []

    if archetype == "active":
        # onboarded 4-24 months ago, steady cadence since, plus recent activity
        onboarded = random.randint(120, 720)
        for age in _spread_ages(random.randint(6, 11), onboarded, 75):
            events.append((random.choice(POSITIVE_EVENTS), 0.85, NOW - timedelta(days=age)))
        for _ in range(random.randint(2, 4)):
            events.append((
                random.choice(POSITIVE_EVENTS), 0.85,
                NOW - timedelta(days=random.randint(3, 70)),
            ))

    elif archetype == "dormant":
        onboarded = random.randint(240, 760)
        for age in _spread_ages(random.randint(3, 6), onboarded, 200):
            et = random.choice([
                EventTypeEnum.INSPECTION, EventTypeEnum.POWER_USAGE,
                EventTypeEnum.DOCUMENT_UPDATE, EventTypeEnum.COMPLAINT,
            ])
            events.append((et, 0.4, NOW - timedelta(days=age)))

    else:  # closed
        onboarded = random.randint(400, 820)
        for age in _spread_ages(random.randint(2, 4), onboarded, 260):
            events.append((EventTypeEnum.INSPECTION, 0.15, NOW - timedelta(days=age)))
        if random.random() < 0.75:
            events.append((
                EventTypeEnum.CLOSURE_NOTICE, -1.0,
                NOW - timedelta(days=random.randint(120, 420)),
            ))

    return events


def _refuse_in_production(force: bool) -> None:
    """This seeder drops tables and installs publicly-known demo passwords
    (see DEMO_USERS / README) — never something to run against a real
    deployment. Mirrors the fail-fast guard in core/config.py."""
    if force or settings.APP_ENV.lower() != "production":
        return
    raise SystemExit(
        "\nRefusing to run against APP_ENV=production: this seeder drops "
        "tables and/or installs publicly-known demo credentials.\n"
        "Pass --force-production-seed if you genuinely mean it.\n"
    )


def reset(force: bool = False) -> None:
    _refuse_in_production(force)
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)


def _require_firebase_target() -> None:
    if settings.FIREBASE_AUTH_EMULATOR_HOST or settings.FIREBASE_CREDENTIALS_JSON:
        return
    raise SystemExit(
        "\nNo Firebase Auth target configured: set FIREBASE_AUTH_EMULATOR_HOST "
        "(run `firebase emulators:start --only auth` for local dev) or "
        "FIREBASE_CREDENTIALS_JSON to seed a real project.\n"
    )


def seed_users(db) -> None:
    _require_firebase_target()
    created = 0
    for email, full_name, role, password in DEMO_USERS:
        if db.query(User).filter(User.email == email).first():
            continue
        try:
            record = firebase.get_user_by_email(email)
        except firebase.auth.UserNotFoundError:
            record = firebase.create_user(email=email, password=password)
        db.add(
            User(
                email=email,
                full_name=full_name,
                role=role,
                firebase_uid=record.uid,
                is_active=True,
            )
        )
        created += 1
    db.commit()
    print(f"[+] users            : {created} created ({len(DEMO_USERS)} total)")
    for email, _fn, role, password in DEMO_USERS:
        print(f"      {email:24s} / {password:16s} ({role.value})")


def seed(force: bool = False) -> None:
    _refuse_in_production(force)
    db = SessionLocal()
    try:
        seed_users(db)

        if db.query(BusinessEntity).count() > 0:
            print("[=] Database already has businesses; skipping. Use --reset.")
            return

        systems = [
            SourceSystem(code=c, name=n, department=d) for c, n, d in SYSTEMS
        ]
        db.add_all(systems)
        db.flush()

        businesses: list[BusinessEntity] = []
        for i in range(1, TOTAL_BUSINESSES + 1):
            name = f"{random.choice(PREFIXES)} {random.choice(SUFFIXES)}"
            district = random.choice(DISTRICTS)
            address = _address(district)
            has_pan = random.random() < 0.75
            pan = _pan() if has_pan else None
            gstin = _gstin(pan) if pan and random.random() < 0.6 else None
            be = BusinessEntity(
                ubid_code=f"UBID{i:06d}",
                legal_name=name,
                normalized_name=_normalize(name),
                pan=pan,
                gstin=gstin,
                address=address,
                normalized_address=normalize_address(address),
                pin_code=DISTRICT_PINS[district],
                phone=_phone(),
                email=_email(name),
                district=district,
                sector=random.choice(SECTORS),
                status=EntityStatusEnum.UNKNOWN,
            )
            businesses.append(be)
        db.add_all(businesses)
        db.flush()

        n_records = n_events = 0
        record_ids: list = []

        for be, archetype in zip(businesses, random.sample(
            ARCHETYPES * (TOTAL_BUSINESSES // len(ARCHETYPES) + 1),
            TOTAL_BUSINESSES,
        )):
            for system in random.sample(systems, random.randint(1, 4)):
                # ~1 in 8 departments holds the same business twice (renewal, re-registration),
                # which the matcher must resolve to a single identity.
                for _copy in range(2 if random.random() < 0.12 else 1):
                    dirty = _noisy(be.legal_name)
                    # roughly a third of departmental records lack a strong id —
                    # those rely on name + address + PIN to be resolved.
                    keep_pan = random.random() < 0.65
                    keep_gstin = keep_pan and random.random() < 0.6
                    sr = SourceRecord(
                        source_system_id=system.id,
                        external_id=str(uuid.uuid4())[:12],
                        raw_payload={"name": dirty, "system": system.code},
                        normalized_payload={"name": _normalize(dirty)},
                        extracted_name=dirty,
                        extracted_pan=be.pan if (keep_pan and be.pan) else None,
                        extracted_gstin=be.gstin if (keep_gstin and be.gstin) else None,
                        extracted_address=_noisy_address(be.address),
                        extracted_pin=_noisy_pin(be.pin_code) or None,
                        extracted_phone=_noisy_phone(be.phone) if random.random() < 0.5 else None,
                        extracted_email=be.email if random.random() < 0.3 else None,
                    )
                    db.add(sr)
                    db.flush()
                    record_ids.append(sr.id)
                    n_records += 1

            for et, sc, occurred in _activity_for(archetype):
                db.add(ActivityEvent(
                    business_entity_id=be.id,
                    event_type=et,
                    score=sc,
                    occurred_at=occurred,
                    created_at=occurred,
                    payload={"source": "synthetic_seed"},
                ))
                n_events += 1

        db.commit()

        # Resolve every source record through the real matching engine so the
        # seed data is consistent with production behaviour.
        print("[*] Running matching engine for every source record ...")
        for rid in record_ids:
            try:
                process_source_record(db, rid)
            except Exception as exc:  # noqa: BLE001
                db.rollback()
                print(f"    ! {rid}: {exc}")

        n_links = db.query(EntityRecordLink).count()
        n_reviews = (
            db.query(ReviewCase)
            .filter(ReviewCase.status == ReviewCaseStatusEnum.OPEN)
            .count()
        )

        print(f"[+] source_systems : {len(systems)}")
        print(f"[+] businesses     : {db.query(BusinessEntity).count()}")
        print(f"[+] source_records : {n_records}")
        print(f"[+] links          : {n_links}")
        print(f"[+] review_cases   : {n_reviews}")
        print(f"[+] activity_events: {n_events}")

        print("[*] Running status engine for every business ...")
        ids = [b.id for b in db.query(BusinessEntity).all()]
        for bid in ids:
            try:
                infer_business_status(db, bid)
            except Exception as exc:  # noqa: BLE001
                db.rollback()
                print(f"    ! {bid}: {exc}")

        counts = {
            s.value: db.query(BusinessEntity)
            .filter(BusinessEntity.status == s).count()
            for s in EntityStatusEnum
        }
        print(f"[+] status snapshot: {counts}")
        print("[done] seed complete")
    finally:
        db.close()


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--reset", action="store_true", help="drop + recreate")
    parser.add_argument(
        "--force-production-seed",
        action="store_true",
        help="required to run this against APP_ENV=production; see the warning it prints otherwise",
    )
    args = parser.parse_args()
    if args.reset:
        print("[*] Resetting schema ...")
        reset(force=args.force_production_seed)
    seed(force=args.force_production_seed)
