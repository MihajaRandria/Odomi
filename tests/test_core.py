"""Tests critiques MotoTracker (SQLite en mémoire, sans toucher moto_tracker.db)."""

import sys
from datetime import date, timedelta
from pathlib import Path

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from database import Base, User, Moto, Trip, Refuel, Maintenance  # noqa: E402
from services import (  # noqa: E402
    Pagination,
    calculate_odometer_at_date,
    get_dashboard_stats,
    get_oil_change_status,
    paginate_data,
    service_create_preset,
    service_create_refuel,
    service_create_trip,
)
from dash_route_planner import haversine_distance_km  # noqa: E402


@pytest.fixture()
def db():
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    TestingSession = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    Base.metadata.create_all(bind=engine)
    session = TestingSession()
    try:
        user = User(email="test@odomi.app", hashed_password="x", name="Test")
        session.add(user)
        session.flush()
        moto = Moto(
            user_id=user.id,
            name="Test Moto",
            license_plate="TEST-001",
            initial_odometer=1000.0,
            oil_interval_km=1000.0,
            is_active=True,
        )
        session.add(moto)
        session.commit()
        session.refresh(moto)
        yield session
    finally:
        session.close()
        Base.metadata.drop_all(bind=engine)


def test_haversine_antananarivo_orders_of_magnitude():
    # Antananarivo -> Ivato ≈ 10-15 km (ordre de grandeur, pas valeur exacte).
    dist = haversine_distance_km(-18.8792, 47.5079, -18.7969, 47.4788)
    assert 5.0 < dist < 25.0


def test_pagination_pages_and_bounds():
    items = list(range(1, 26))
    page1 = paginate_data(items, page=1, page_size=10)
    assert isinstance(page1, Pagination)
    assert page1.items == list(range(1, 11))
    assert page1.total_pages == 3
    assert page1.has_next and not page1.has_prev

    last = paginate_data(items, page=99, page_size=10)
    assert last.page == 3
    assert last.items == list(range(21, 26))


def test_trip_crud_recalculates_total(db):
    trip = service_create_trip(db, 1, date(2026, 9, 1), 12.5, 10.0, 22.5, depart="A", destination="B")
    assert trip.total == pytest.approx(22.5)
    updated = service_create_trip(db, 1, date(2026, 9, 2), 5.0, 0.0, 5.0, depart="A", destination="B")
    assert updated.total == pytest.approx(5.0)


def test_odometer_retroactive_uses_trips(db):
    day0 = date(2026, 9, 1)
    service_create_trip(db, 1, day0, 10.0, 5.0, 15.0, depart="A", destination="B")
    service_create_trip(db, 1, day0 + timedelta(days=2), 7.0, 0.0, 7.0, depart="B", destination="C")
    assert calculate_odometer_at_date(db, db.get(Moto, 1), day0) == pytest.approx(1015.0)
    assert calculate_odometer_at_date(db, db.get(Moto, 1), day0 + timedelta(days=1)) == pytest.approx(1015.0)
    assert calculate_odometer_at_date(db, db.get(Moto, 1), day0 + timedelta(days=2)) == pytest.approx(1022.0)


def test_dashboard_stats_totals(db):
    service_create_trip(db, 1, date(2026, 9, 1), 10.0, 5.0, 15.0, depart="A", destination="B")
    service_create_refuel(db, 1, date(2026, 9, 1), liters=4.0, amount=20000.0)
    stats = get_dashboard_stats(db, db.get(Moto, 1))
    assert stats["total_km"] == pytest.approx(15.0)
    assert stats["total_fuel_cost"] == pytest.approx(20000.0)
    assert stats["consommation_moyenne"] == pytest.approx(round(20000.0 / 15.0, 2))
    assert stats["avg_l_per_100"] == pytest.approx(round(400.0 / 15.0, 2))


def test_oil_change_status_threshold(db):
    moto = db.get(Moto, 1)
    db.add(Maintenance(moto_id=moto.id, date=date(2026, 9, 1), service_type="Vidange moteur", odometer=1000.0, is_oil_change=True))
    db.commit()
    service_create_trip(db, 1, date(2026, 9, 2), 900.0, 0.0, 900.0, depart="A", destination="B")
    moto = db.get(Moto, 1)
    status = get_oil_change_status(db, moto)
    assert status["distance_since_vidange"] == pytest.approx(900.0)
    assert status["status"] in {"OK", "WARNING", "CRITICAL"}


def test_preset_payload_total(db):
    preset = service_create_preset(db, 1, "Maison", "A", "B", 6.0, 6.5)
    assert preset.to_dict()["total"] == pytest.approx(12.5)


def test_trip_model_to_dict_handles_none_dates():
    trip = Trip(moto_id=1, date=date(2026, 9, 30), aller=1.0, retour=2.0, total=3.0, depart="A", destination="B")
    payload = trip.to_dict()
    assert payload["total"] == pytest.approx(3.0)
    assert payload["date"] == "2026-09-30"
    assert isinstance(Refuel.__tablename__, str)
