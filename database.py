"""
database.py
-----------
Modèles de données SQLAlchemy, configuration de base et gestion du cycle de vie SQLite.
"""

import logging
import os
from datetime import datetime, date, timezone
from pathlib import Path
from typing import Optional, Dict, Any
from urllib.parse import urlparse, unquote
from pydantic_settings import BaseSettings, SettingsConfigDict
from sqlalchemy import (
    create_engine,
    Column,
    Integer,
    String,
    Float,
    Boolean,
    Date,
    DateTime,
    ForeignKey,
    event,
    text,
)
from sqlalchemy.orm import declarative_base, sessionmaker, relationship

BASE_DIR = Path(__file__).resolve().parent
DEFAULT_DB_PATH = BASE_DIR / "moto_tracker.db"
# IMPORTANT : le fichier .env réel est exclu du périmètre (jamais lu/modifié ici).
# pydantic-settings le chargera automatiquement s'il existe, sans l'altérer.
ENV_FILE_PATH = BASE_DIR / ".env"

logger = logging.getLogger("MotoTracker.Database")


class Settings(BaseSettings):
    PROJECT_NAME: str = "MotoTracker Pro"
    # Sécurité: en production, définir SECRET_KEY via variable d'environnement.
    # La valeur par défaut ne sert que pour le développement local.
    SECRET_KEY: str = "dev-only-insecure-secret-key-change-me"
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_DAYS: int = 30
    DATABASE_URL: str = f"sqlite:///{DEFAULT_DB_PATH.as_posix()}"
    DEFAULT_FUEL_PRICE_PER_LITER: float = 5300.0
    GRAPHHOPPER_API_KEY: str = ""
    # Compte de démonstration créé uniquement si la table users est vide.
    DEMO_EMAIL: str = "pilote@odomi.app"
    DEMO_PASSWORD: str = "pilote123"
    DEMO_NAME: str = "Mihaja"
    # Déploiement web (ex. Render/Heroku : PORT injecté par la plateforme).
    HOST: str = "0.0.0.0"
    PORT: int = 8000
    DEBUG: bool = False

    model_config = SettingsConfigDict(env_file=str(ENV_FILE_PATH), extra="ignore")

    @property
    def SECURE_KEY_CONFIGURED(self) -> bool:
        """Vrai si SECRET_KEY a été surchargé via l'environnement (pas la valeur dev)."""
        return self.SECRET_KEY != "dev-only-insecure-secret-key-change-me"


settings = Settings()


def _is_vercel() -> bool:
    """Vrai sur Vercel (filesystem en lecture seule sauf /tmp)."""
    return bool(os.environ.get("VERCEL"))


def _resolve_database_url(raw_url: str) -> str:
    """Normalise DATABASE_URL pour un usage portable local + serverless.

    - Convertit ``postgres://`` en ``postgresql://`` (SQLAlchemy).
    - Sur Vercel, redirige tout SQLite fichier vers ``/tmp`` (seul dossier
      inscriptible). ``:memory:`` est conservé tel quel.
    """
    url = (raw_url or "").strip()
    if url.startswith("postgres://"):
        url = "postgresql://" + url[len("postgres://"):]
    if _is_vercel() and url.startswith("sqlite:") and ":memory:" not in url:
        # sqlite:////abs/path ou sqlite:///rel/path -> /tmp/<nom>.db
        filename = Path(url.rsplit("/", 1)[-1] or "moto_tracker.db")
        name = filename.name if filename.suffix else "moto_tracker.db"
        return f"sqlite:////tmp/{name}"
    return url


DATABASE_URL = _resolve_database_url(settings.DATABASE_URL)
IS_SQLITE = DATABASE_URL.strip().startswith("sqlite:")

if IS_SQLITE and ":memory:" not in DATABASE_URL and not _is_vercel():
    # Crée le dossier parent local si DATABASE_URL pointe vers un dossier inexistant.
    try:
        _path_part = DATABASE_URL.split("sqlite:///", 1)[-1]
        _parent = Path(_path_part).expanduser().parent
        if str(_parent) and str(_parent) != ".":
            _parent.mkdir(parents=True, exist_ok=True)
    except OSError:
        pass

engine_kwargs: Dict[str, Any] = {}
if IS_SQLITE:
    engine_kwargs["connect_args"] = {"check_same_thread": False}

engine = create_engine(DATABASE_URL, **engine_kwargs)

if IS_SQLITE:
    # Activation des clés étrangères et du mode WAL pour la concurrence SQLite.
    # Sur Vercel (/tmp) le WAL peut échouer : on bascule en DELETE sans bloquer.
    @event.listens_for(engine, "connect")
    def set_sqlite_pragma(dbapi_connection, connection_record):  # noqa: F811
        cursor = dbapi_connection.cursor()
        try:
            cursor.execute("PRAGMA foreign_keys=ON")
            try:
                cursor.execute("PRAGMA journal_mode=WAL")
            except Exception:
                try:
                    cursor.execute("PRAGMA journal_mode=DELETE")
                except Exception:
                    pass
        finally:
            cursor.close()

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


# ==============================================================================
# MODÈLES SQLALCHEMY
# ==============================================================================

class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    email = Column(String(255), unique=True, index=True, nullable=False)
    hashed_password = Column(String(255), nullable=False)
    name = Column(String(100), nullable=False, default="Pilote")
    created_at = Column(DateTime(timezone=True), default=utc_now, nullable=False)

    motos = relationship("Moto", back_populates="user", cascade="all, delete-orphan")


class Moto(Base):
    __tablename__ = "motos"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    name = Column(String(100), nullable=False)
    license_plate = Column(String(50), nullable=True)
    initial_odometer = Column(Float, default=0.0, nullable=False)
    oil_interval_km = Column(Float, default=1000.0, nullable=False)
    is_active = Column(Boolean, default=True, nullable=False)
    created_at = Column(DateTime(timezone=True), default=utc_now, nullable=False)

    user = relationship("User", back_populates="motos")
    trips = relationship("Trip", back_populates="moto", cascade="all, delete-orphan")
    refuels = relationship("Refuel", back_populates="moto", cascade="all, delete-orphan")
    maintenances = relationship("Maintenance", back_populates="moto", cascade="all, delete-orphan")
    presets = relationship("RoutePreset", back_populates="moto", cascade="all, delete-orphan")

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "name": self.name,
            "license_plate": self.license_plate,
            "initial_odometer": self.initial_odometer,
            "oil_interval_km": self.oil_interval_km,
            "is_active": self.is_active,
        }


class Trip(Base):
    __tablename__ = "trips"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    moto_id = Column(Integer, ForeignKey("motos.id", ondelete="CASCADE"), nullable=False, index=True)
    date = Column(Date, nullable=False, default=date.today, index=True)
    aller = Column(Float, default=0.0, nullable=False)
    retour = Column(Float, default=0.0, nullable=False)
    total = Column(Float, default=0.0, nullable=False)
    depart = Column(String(100), nullable=True)
    destination = Column(String(100), nullable=True)
    created_at = Column(DateTime(timezone=True), default=utc_now, nullable=False)

    moto = relationship("Moto", back_populates="trips")

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "date": self.date.isoformat() if self.date else None,
            "aller": round(float(self.aller or 0.0), 2),
            "retour": round(float(self.retour or 0.0), 2),
            "total": round(float(self.total or 0.0), 2),
            "depart": self.depart or "—",
            "destination": self.destination or "—",
        }


class Refuel(Base):
    __tablename__ = "refuels"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    moto_id = Column(Integer, ForeignKey("motos.id", ondelete="CASCADE"), nullable=False, index=True)
    date = Column(Date, nullable=False, default=date.today, index=True)
    amount = Column(Float, nullable=False, default=0.0)
    liters = Column(Float, nullable=False, default=0.0)
    is_full_tank = Column(Boolean, default=True, nullable=False)
    notes = Column(String(255), nullable=True)
    created_at = Column(DateTime(timezone=True), default=utc_now, nullable=False)

    moto = relationship("Moto", back_populates="refuels")


class Maintenance(Base):
    __tablename__ = "maintenances"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    moto_id = Column(Integer, ForeignKey("motos.id", ondelete="CASCADE"), nullable=False, index=True)
    date = Column(Date, nullable=False, default=date.today, index=True)
    service_type = Column(String(100), nullable=False)
    cost = Column(Float, default=0.0, nullable=False)
    odometer = Column(Float, nullable=False, default=0.0)
    is_oil_change = Column(Boolean, default=False, nullable=False)
    notes = Column(String(255), nullable=True)
    created_at = Column(DateTime(timezone=True), default=utc_now, nullable=False)

    moto = relationship("Moto", back_populates="maintenances")


class RoutePreset(Base):
    __tablename__ = "route_presets"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    moto_id = Column(Integer, ForeignKey("motos.id", ondelete="CASCADE"), nullable=False, index=True)
    name = Column(String(100), nullable=False)
    depart = Column(String(100), nullable=False)
    destination = Column(String(100), nullable=False)
    aller = Column(Float, default=0.0, nullable=False)
    retour = Column(Float, default=0.0, nullable=False)

    moto = relationship("Moto", back_populates="presets")

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "name": self.name,
            "depart": self.depart,
            "destination": self.destination,
            "aller": round(float(self.aller or 0.0), 2),
            "retour": round(float(self.retour or 0.0), 2),
            "total": round(float((self.aller or 0.0) + (self.retour or 0.0)), 2),
        }


def ensure_db_migrations():
    """Applique les migrations légères SQLite (ex: nouvelle colonne sans détruire la base)."""
    if not IS_SQLITE:
        return
    try:
        with engine.connect() as conn:
            try:
                res = conn.execute(text("PRAGMA table_info(refuels)"))
                columns = [row[1] for row in res.fetchall()]
                if "is_full_tank" not in columns:
                    conn.execute(text("ALTER TABLE refuels ADD COLUMN is_full_tank BOOLEAN DEFAULT 1 NOT NULL"))
                    conn.commit()
            except Exception as exc:
                logger.warning("Migration SQLite ignorée: %s", exc)
    except Exception as exc:
        logger.warning("Migration SQLite indisponible: %s", exc)