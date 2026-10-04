"""
services.py
-----------
Logique métier, authentification unifiée, calculs statistiques temporels
(agrégation journalière si <= 30 jours, sinon mensuelle), deltas N-1,
calcul rétroactif d'odomètre et objet Pagination compatible Jinja2.
"""

import logging
import bcrypt
from datetime import datetime, date, timedelta, timezone
from typing import Optional, List, Dict, Any, Tuple
from fastapi import Depends, HTTPException, status, Request
from jose import JWTError, jwt
from sqlalchemy.orm import Session
from sqlalchemy import func, distinct

from database import (
    User,
    Moto,
    Trip,
    Refuel,
    Maintenance,
    RoutePreset,
    settings,
    get_db,
)

logger = logging.getLogger("MotoTracker.Services")


# ==============================================================================
# UTILITAIRES DE DATE & FORMATAGE
# ==============================================================================

def parse_date_safe(val: Any, default: Optional[date] = None) -> date:
    if not val:
        return default or date.today()
    if isinstance(val, date):
        return val
    if isinstance(val, datetime):
        return val.date()
    try:
        val_str = str(val).strip()[:10]
        return datetime.strptime(val_str, "%Y-%m-%d").date()
    except Exception:
        return default or date.today()


def format_date_safe(val: Any) -> str:
    if not val:
        return "—"
    if isinstance(val, (datetime, date)):
        return val.strftime("%d/%m/%Y")
    if isinstance(val, str):
        try:
            return datetime.strptime(val[:10], "%Y-%m-%d").strftime("%d/%m/%Y")
        except Exception:
            return val
    return str(val)


# ==============================================================================
# SÉCURITÉ & AUTHENTIFICATION
# ==============================================================================

def verify_password(plain_password: str, hashed_password: str) -> bool:
    try:
        return bcrypt.checkpw(plain_password.encode("utf-8"), hashed_password.encode("utf-8"))
    except (ValueError, TypeError) as exc:
        logger.warning("Échec vérification mot de passe: %s", exc)
        return False


def get_password_hash(password: str) -> str:
    salt = bcrypt.gensalt()
    return bcrypt.hashpw(password.encode("utf-8"), salt).decode("utf-8")


def create_access_token(data: dict, expires_delta: Optional[timedelta] = None) -> str:
    to_encode = data.copy()
    now_utc = datetime.now(timezone.utc)
    expire = now_utc + (expires_delta or timedelta(days=settings.ACCESS_TOKEN_EXPIRE_DAYS))
    to_encode.update({"exp": expire})
    return jwt.encode(to_encode, settings.SECRET_KEY, algorithm=settings.ALGORITHM)


def extract_user_from_token(token: Optional[str], db: Session) -> Optional[User]:
    if not token:
        return None
    if token.startswith("Bearer "):
        token = token[7:]
    try:
        payload = jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])
        email: str = payload.get("sub")
        if not email:
            return None
        return db.query(User).filter(User.email == email).first()
    except JWTError:
        return None


def get_current_user_optional(request: Request, db: Session) -> Optional[User]:
    token = request.cookies.get("access_token")
    return extract_user_from_token(token, db)


def get_current_user(request: Request, db: Session = Depends(get_db)) -> User:
    user = get_current_user_optional(request, db)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_303_SEE_OTHER,
            detail="Non authentifié",
            headers={"Location": "/login"},
        )
    return user


def resolve_active_moto_for_user(user: User, db: Session) -> Moto:
    moto = db.query(Moto).filter(Moto.user_id == user.id, Moto.is_active == True).first()
    if not moto:
        moto = db.query(Moto).filter(Moto.user_id == user.id).first()

    if not moto:
        moto = Moto(
            user_id=user.id,
            name="Ma Moto",
            license_plate="1234-TAB",
            initial_odometer=0.0,
            oil_interval_km=1000.0,
            is_active=True,
        )
        db.add(moto)
        db.commit()
        db.refresh(moto)

    return moto


def get_active_moto(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> Moto:
    return resolve_active_moto_for_user(current_user, db)


def get_authenticated_session_from_cookie(cookie_token: Optional[str], db: Session) -> Tuple[Optional[User], Optional[Moto], Optional[str]]:
    user = extract_user_from_token(cookie_token, db)
    if not user:
        return None, None, "Session expirée. Veuillez vous reconnecter."
    moto = resolve_active_moto_for_user(user, db)
    return user, moto, None


# ==============================================================================
# GESTION DES PÉRIODES & DELTAS DE COMPARAISON
# ==============================================================================

def resolve_period_dates(
    db: Session,
    moto: Moto,
    period: Optional[str] = "all",
    start_date_str: Optional[str] = None,
    end_date_str: Optional[str] = None,
) -> Tuple[Optional[date], Optional[date], str, Optional[date], Optional[date]]:
    latest_trip = db.query(func.max(Trip.date)).filter(Trip.moto_id == moto.id).scalar()
    today_val = date.today()
    ref_date = max(latest_trip, today_val) if latest_trip else today_val

    p_norm = (period or "all").lower().strip()
    p_start: Optional[date] = None
    p_end: Optional[date] = None

    if p_norm == "today":
        p_start, p_end = ref_date, ref_date
    elif p_norm == "week":
        p_start = ref_date - timedelta(days=ref_date.weekday())
        p_end = ref_date
    elif p_norm == "month":
        p_start = ref_date.replace(day=1)
        p_end = ref_date
    elif p_norm == "30days":
        p_start = ref_date - timedelta(days=30)
        p_end = ref_date
    elif p_norm == "year":
        p_start = ref_date.replace(month=1, day=1)
        p_end = ref_date
    elif p_norm == "custom":
        p_start = parse_date_safe(start_date_str, default=None)
        p_end = parse_date_safe(end_date_str, default=None)
        if p_start and not p_end:
            p_end = ref_date
        elif p_end and not p_start:
            p_start = p_end - timedelta(days=30)
    else:
        p_norm = "all"
        p_start, p_end = None, None

    prev_start: Optional[date] = None
    prev_end: Optional[date] = None

    if p_start and p_end:
        duration_days = (p_end - p_start).days + 1
        prev_end = p_start - timedelta(days=1)
        prev_start = prev_end - timedelta(days=duration_days - 1)

    return p_start, p_end, p_norm, prev_start, prev_end


# ==============================================================================
# CALCUL DES STATS & GRAPHES (JOURNALIER OU MENSUEL)
# ==============================================================================

def get_dashboard_stats(
    db: Session,
    moto: Moto,
    start_date: Optional[date] = None,
    end_date: Optional[date] = None,
    prev_start: Optional[date] = None,
    prev_end: Optional[date] = None,
) -> Dict[str, Any]:
    trip_q = db.query(Trip).filter(Trip.moto_id == moto.id)
    refuel_q = db.query(Refuel).filter(Refuel.moto_id == moto.id)
    maint_q = db.query(Maintenance).filter(Maintenance.moto_id == moto.id)

    if start_date:
        trip_q = trip_q.filter(Trip.date >= start_date)
        refuel_q = refuel_q.filter(Refuel.date >= start_date)
        maint_q = maint_q.filter(Maintenance.date >= start_date)
    if end_date:
        trip_q = trip_q.filter(Trip.date <= end_date)
        refuel_q = refuel_q.filter(Refuel.date <= end_date)
        maint_q = maint_q.filter(Maintenance.date <= end_date)

    total_km = round(float(trip_q.with_entities(func.coalesce(func.sum(Trip.total), 0.0)).scalar() or 0.0), 2)
    total_fuel_cost = round(float(refuel_q.with_entities(func.coalesce(func.sum(Refuel.amount), 0.0)).scalar() or 0.0), 2)
    total_liters = round(float(refuel_q.with_entities(func.coalesce(func.sum(Refuel.liters), 0.0)).scalar() or 0.0), 2)
    nb_refuel = refuel_q.with_entities(func.count(Refuel.id)).scalar() or 0
    nb_trips = trip_q.with_entities(func.count(Trip.id)).scalar() or 0
    nb_jours = trip_q.with_entities(func.count(distinct(Trip.date))).scalar() or 0
    total_maint_cost = round(float(maint_q.with_entities(func.coalesce(func.sum(Maintenance.cost), 0.0)).scalar() or 0.0), 2)

    consommation_moyenne = round(total_fuel_cost / total_km, 2) if total_km > 0 else 0.0
    avg_l_per_100 = round((total_liters / total_km) * 100, 2) if total_km > 0 else 0.0

    date_debut_raw = trip_q.with_entities(func.min(Trip.date)).scalar() or start_date
    date_fin_raw = trip_q.with_entities(func.max(Trip.date)).scalar() or end_date

    delta_km_pct = None
    delta_fuel_pct = None
    if prev_start and prev_end:
        p_km = float(db.query(func.coalesce(func.sum(Trip.total), 0.0)).filter(
            Trip.moto_id == moto.id, Trip.date >= prev_start, Trip.date <= prev_end
        ).scalar() or 0.0)
        p_fuel = float(db.query(func.coalesce(func.sum(Refuel.amount), 0.0)).filter(
            Refuel.moto_id == moto.id, Refuel.date >= prev_start, Refuel.date <= prev_end
        ).scalar() or 0.0)

        if p_km > 0:
            delta_km_pct = round(((total_km - p_km) / p_km) * 100, 1)
        if p_fuel > 0:
            delta_fuel_pct = round(((total_fuel_cost - p_fuel) / p_fuel) * 100, 1)

    is_daily = False
    if start_date and end_date:
        is_daily = (end_date - start_date).days <= 31
    elif not start_date and not end_date and date_debut_raw and date_fin_raw:
        is_daily = (date_fin_raw - date_debut_raw).days <= 31

    trips = trip_q.order_by(Trip.date.asc()).all()
    refuels = refuel_q.order_by(Refuel.date.asc()).all()

    labels, km_series, fuel_series = [], [], []

    if is_daily:
        actual_start = start_date or date_debut_raw or date.today()
        actual_end = end_date or date_fin_raw or actual_start
        curr_d = actual_start
        daily_km_map: Dict[str, float] = {}
        daily_fuel_map: Dict[str, float] = {}

        for t in trips:
            k = t.date.strftime("%Y-%m-%d")
            daily_km_map[k] = daily_km_map.get(k, 0.0) + float(t.total or 0.0)

        for r in refuels:
            k = r.date.strftime("%Y-%m-%d")
            daily_fuel_map[k] = daily_fuel_map.get(k, 0.0) + float(r.amount or 0.0)

        while curr_d <= actual_end:
            k = curr_d.strftime("%Y-%m-%d")
            labels.append(curr_d.strftime("%d/%m"))
            km_series.append(round(daily_km_map.get(k, 0.0), 1))
            fuel_series.append(round(daily_fuel_map.get(k, 0.0), 1))
            curr_d += timedelta(days=1)
        
        granularity_label = "Journalier"
    else:
        monthly_km: Dict[str, float] = {}
        monthly_fuel: Dict[str, float] = {}

        for t in trips:
            m_key = t.date.strftime("%Y-%m")
            monthly_km[m_key] = monthly_km.get(m_key, 0.0) + float(t.total or 0.0)

        for r in refuels:
            m_key = r.date.strftime("%Y-%m")
            monthly_fuel[m_key] = monthly_fuel.get(m_key, 0.0) + float(r.amount or 0.0)

        all_months = sorted(list(set(list(monthly_km.keys()) + list(monthly_fuel.keys()))))
        if not all_months:
            all_months = [(start_date or date.today()).strftime("%Y-%m")]

        month_names_fr = {
            "01": "Jan", "02": "Fév", "03": "Mar", "04": "Avr",
            "05": "Mai", "06": "Juin", "07": "Juil", "08": "Août",
            "09": "Sept", "10": "Oct", "11": "Nov", "12": "Déc",
        }

        for m in all_months:
            parts = m.split("-")
            lbl = f"{month_names_fr.get(parts[1], parts[1])} {parts[0]}" if len(parts) == 2 else m
            labels.append(lbl)
            km_series.append(round(monthly_km.get(m, 0.0), 1))
            fuel_series.append(round(monthly_fuel.get(m, 0.0), 1))

        granularity_label = "Mensuel"

    total_odo = round(float(moto.initial_odometer or 0.0) + float(
        db.query(func.coalesce(func.sum(Trip.total), 0.0)).filter(Trip.moto_id == moto.id).scalar() or 0.0
    ), 2)

    return {
        "total_km": total_km,
        "current_odometer": total_odo,
        "total_fuel_cost": total_fuel_cost,
        "total_liters": total_liters,
        "avg_l_per_100": avg_l_per_100,
        "nb_refuel": nb_refuel,
        "nb_trips": nb_trips,
        "nb_jours": nb_jours,
        "total_maintenance_cost": total_maint_cost,
        "consommation_moyenne": consommation_moyenne,
        "date_debut": format_date_safe(date_debut_raw),
        "date_fin": format_date_safe(date_fin_raw),
        "delta_km_pct": delta_km_pct,
        "delta_fuel_pct": delta_fuel_pct,
        "is_daily": is_daily,
        "charts": {
            "labels": labels,
            "km_series": km_series,
            "fuel_series": fuel_series,
            "granularity": granularity_label,
        },
    }


# ==============================================================================
# SUIVI TECHNIQUE & VIDANGE
# ==============================================================================

def get_oil_change_status(db: Session, moto: Moto) -> Dict[str, Any]:
    total_trip_km = (
        db.query(func.coalesce(func.sum(Trip.total), 0.0))
        .filter(Trip.moto_id == moto.id)
        .scalar()
        or 0.0
    )
    init_odo = float(moto.initial_odometer or 0.0)
    current_odometer = round(init_odo + float(total_trip_km), 2)
    interval = float(moto.oil_interval_km or 1000.0)

    last_oil = (
        db.query(Maintenance)
        .filter(Maintenance.moto_id == moto.id, Maintenance.is_oil_change == True)
        .order_by(Maintenance.odometer.desc(), Maintenance.date.desc(), Maintenance.id.desc())
        .first()
    )

    if last_oil:
        last_vidange_km = round(float(last_oil.odometer or 0.0), 2)
        last_vidange_date = format_date_safe(last_oil.date)
    else:
        last_vidange_km = round(init_odo, 2)
        last_vidange_date = f"Initial ({init_odo} km)"

    distance_since_vidange = round(max(0.0, current_odometer - last_vidange_km), 2)
    remaining_vidange_km = round(interval - distance_since_vidange, 2)
    warning_threshold = max(50.0, round(interval * 0.15, 1))

    if remaining_vidange_km <= 0:
        status_code = "CRITICAL"
        badge_bg = "bg-rose-500/20 text-rose-300 border-rose-500/40"
        bar_color = "bg-rose-500"
    elif 0 < remaining_vidange_km <= warning_threshold:
        status_code = "WARNING"
        badge_bg = "bg-amber-500/20 text-amber-300 border-amber-500/40"
        bar_color = "bg-amber-500"
    else:
        status_code = "OK"
        badge_bg = "bg-emerald-500/20 text-emerald-300 border-emerald-500/40"
        bar_color = "bg-emerald-500"

    percentage = min(100.0, max(0.0, round((distance_since_vidange / interval) * 100, 1)))

    return {
        "current_odometer": current_odometer,
        "last_vidange_km": last_vidange_km,
        "last_vidange_date": last_vidange_date,
        "distance_since_vidange": distance_since_vidange,
        "remaining_vidange_km": remaining_vidange_km,
        "percentage": percentage,
        "status": status_code,
        "badge_bg": badge_bg,
        "bar_color": bar_color,
        "interval_km": interval,
        "is_alert": status_code in ("CRITICAL", "WARNING"),
    }


def calculate_odometer_at_date(db: Session, moto: Moto, target_date: date) -> float:
    """Calcule le kilométrage total théorique à une date précise."""
    trip_km = (
        db.query(func.coalesce(func.sum(Trip.total), 0.0))
        .filter(Trip.moto_id == moto.id, Trip.date <= target_date)
        .scalar()
        or 0.0
    )
    init_odo = float(moto.initial_odometer or 0.0)
    return round(init_odo + float(trip_km), 2)


# ==============================================================================
# FILTRAGE, RECHERCHE & CORRÉLATION
# ==============================================================================

def get_filtered_correlated_data(
    db: Session,
    moto: Moto,
    start_date: Optional[date] = None,
    end_date: Optional[date] = None,
    search_query: Optional[str] = None,
) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
    refuels = (
        db.query(Refuel)
        .filter(Refuel.moto_id == moto.id)
        .order_by(Refuel.date.asc(), Refuel.id.asc())
        .all()
    )
    trips_all = (
        db.query(Trip)
        .filter(Trip.moto_id == moto.id)
        .order_by(Trip.date.asc(), Trip.id.asc())
        .all()
    )

    refuel_results: List[Dict[str, Any]] = []
    trip_refuel_map: Dict[int, Dict[str, Any]] = {}

    trip_idx = 0
    total_trips = len(trips_all)
    prev_refuel_date: Optional[date] = None

    for refuel in refuels:
        window_km = 0.0
        while trip_idx < total_trips and trips_all[trip_idx].date <= refuel.date:
            t = trips_all[trip_idx]
            if prev_refuel_date is None or t.date > prev_refuel_date:
                window_km += float(t.total or 0.0)
            trip_idx += 1

        window_km = round(window_km, 2)
        amount = round(float(refuel.amount or 0.0), 2)
        liters = round(float(refuel.liters or 0.0), 2)

        cost_per_km = round(amount / window_km, 2) if window_km > 0 else 0.0
        l_per_100 = round((liters / window_km) * 100, 2) if (window_km > 0 and liters > 0) else 0.0

        refuel_dict = {
            "id": refuel.id,
            "date": refuel.date,
            "date_iso": refuel.date.isoformat() if refuel.date else "",
            "date_str": format_date_safe(refuel.date),
            "amount": amount,
            "liters": liters,
            "notes": refuel.notes or "",
            "is_full_tank": refuel.is_full_tank,
            "km_since_last_refuel": window_km,
            "cycle_km": window_km,
            "cost_per_km": cost_per_km,
            "l_per_100": l_per_100,
        }

        in_range = True
        if start_date and refuel.date < start_date:
            in_range = False
        if end_date and refuel.date > end_date:
            in_range = False
        if in_range:
            refuel_results.append(refuel_dict)

        trip_refuel_map[refuel.date] = {
            "km": window_km,
            "liters": liters,
            "amount": amount,
            "is_full": refuel.is_full_tank,
        }
        prev_refuel_date = refuel.date

    trip_results: List[Dict[str, Any]] = []
    q_clean = (search_query or "").strip().lower()

    for t in trips_all:
        if start_date and t.date < start_date:
            continue
        if end_date and t.date > end_date:
            continue
        if q_clean:
            match_dep = q_clean in (t.depart or "").lower()
            match_dest = q_clean in (t.destination or "").lower()
            if not (match_dep or match_dest):
                continue

        r_info = trip_refuel_map.get(t.date)
        trip_results.append({
            "id": t.id,
            "date": t.date,
            "date_iso": t.date.isoformat() if t.date else "",
            "date_str": format_date_safe(t.date),
            "aller": round(float(t.aller or 0.0), 2),
            "retour": round(float(t.retour or 0.0), 2),
            "total": round(float(t.total or 0.0), 2),
            "depart": t.depart or "—",
            "destination": t.destination or "—",
            "has_refuel": bool(r_info),
            "refuel_is_full": r_info.get("is_full", True) if r_info else True,
            "refuel_km": r_info.get("km", 0.0) if r_info else 0.0,
            "refuel_liters": r_info.get("liters", 0.0) if r_info else 0.0,
            "refuel_amount": r_info.get("amount", 0.0) if r_info else 0.0,
        })

    refuel_results.reverse()
    trip_results.reverse()
    return refuel_results, trip_results


# ==============================================================================
# OBJET DE PAGINATION COMPATIBLE JINJA2 (.items sous forme de LISTE)
# ==============================================================================

class Pagination:
    """
    Encapsule les données paginées. L'attribut `.items` est une VRAIE liste,
    ce qui empêche Jinja2 de la confondre avec la méthode native dict.items().
    """
    def __init__(self, full_list: List[Any], page: int = 1, page_size: int = 15):
        self.total_items = len(full_list)
        self.page_size = max(1, page_size)
        self.total_pages = max(1, (self.total_items + self.page_size - 1) // self.page_size)
        self.page = max(1, min(page, self.total_pages))

        start_idx = (self.page - 1) * self.page_size
        end_idx = min(start_idx + self.page_size, self.total_items)

        self.items = full_list[start_idx:end_idx]
        self.has_prev = self.page > 1
        self.has_next = self.page < self.total_pages
        self.prev_page = self.page - 1
        self.next_page = self.page + 1
        self.start_idx = start_idx + 1 if self.total_items > 0 else 0
        self.end_idx = end_idx

    def __iter__(self):
        return iter(self.items)

    def __len__(self):
        return len(self.items)

    def __getitem__(self, key: str):
        if hasattr(self, key):
            return getattr(self, key)
        raise KeyError(key)

    def get(self, key: str, default: Any = None):
        return getattr(self, key, default)


def paginate_data(items: List[Any], page: int = 1, page_size: int = 15) -> Pagination:
    return Pagination(items, page=page, page_size=page_size)


# ==============================================================================
# CRUD SERVICES
# ==============================================================================

def service_create_trip(
    db: Session,
    moto_id: int,
    trip_date: Any,
    aller: float,
    retour: float,
    total: float,
    depart: Optional[str] = None,
    destination: Optional[str] = None,
    has_refuel: bool = False,
    refuel_liters: float = 0.0,
    refuel_amount: float = 0.0,
    refuel_notes: Optional[str] = None,
    is_full_tank: bool = True,
) -> Trip:
    p_date = parse_date_safe(trip_date)
    trip = Trip(
        moto_id=moto_id,
        date=p_date,
        aller=float(aller or 0.0),
        retour=float(retour or 0.0),
        total=float(total or 0.0),
        depart=(depart or "—").strip(),
        destination=(destination or "—").strip(),
    )
    db.add(trip)

    if has_refuel and (refuel_liters > 0 or refuel_amount > 0):
        refuel = Refuel(
            moto_id=moto_id,
            date=p_date,
            liters=float(refuel_liters or 0.0),
            amount=float(refuel_amount or 0.0),
            is_full_tank=is_full_tank,
            notes=(refuel_notes or "").strip() or None,
        )
        db.add(refuel)

    db.commit()
    db.refresh(trip)
    return trip


def service_update_trip(
    db: Session,
    trip_id: int,
    moto_id: int,
    trip_date: Any,
    aller: float,
    retour: float,
    total: float,
    depart: Optional[str] = None,
    destination: Optional[str] = None,
) -> Optional[Trip]:
    t = db.query(Trip).filter(Trip.id == trip_id, Trip.moto_id == moto_id).first()
    if not t:
        return None
    t.date = parse_date_safe(trip_date)
    t.aller = float(aller or 0.0)
    t.retour = float(retour or 0.0)
    t.total = float(total or 0.0)
    t.depart = (depart or "—").strip()
    t.destination = (destination or "—").strip()
    db.commit()
    db.refresh(t)
    return t


def service_create_refuel(
    db: Session,
    moto_id: int,
    refuel_date: Any,
    liters: float,
    amount: float,
    notes: Optional[str] = None,
    is_full_tank: bool = True,
) -> Refuel:
    refuel = Refuel(
        moto_id=moto_id,
        date=parse_date_safe(refuel_date),
        liters=float(liters or 0.0),
        amount=float(amount or 0.0),
        is_full_tank=is_full_tank,
        notes=(notes or "").strip() or None,
    )
    db.add(refuel)
    db.commit()
    db.refresh(refuel)
    return refuel


def service_delete_refuel(db: Session, refuel_id: int, moto_id: int) -> bool:
    r = db.query(Refuel).filter(Refuel.id == refuel_id, Refuel.moto_id == moto_id).first()
    if r:
        db.delete(r)
        db.commit()
        return True
    return False


def service_create_preset(
    db: Session,
    moto_id: int,
    name: str,
    depart: str,
    destination: str,
    aller: float,
    retour: float,
) -> RoutePreset:
    clean_name = name.strip() or f"{depart} ➔ {destination}"
    preset = RoutePreset(
        moto_id=moto_id,
        name=clean_name,
        depart=depart.strip(),
        destination=destination.strip(),
        aller=float(aller or 0.0),
        retour=float(retour or 0.0),
    )
    db.add(preset)
    db.commit()
    db.refresh(preset)
    return preset


def service_create_maintenance(
    db: Session,
    moto_id: int,
    service_date: Any,
    service_type: str,
    odometer: float,
    cost: float = 0.0,
    notes: Optional[str] = None,
    is_oil_change: bool = False,
) -> Maintenance:
    oil_flag = bool(is_oil_change or (service_type.strip().lower() == "vidange moteur"))
    maint = Maintenance(
        moto_id=moto_id,
        date=parse_date_safe(service_date),
        service_type=service_type.strip(),
        odometer=float(odometer or 0.0),
        cost=float(cost or 0.0),
        notes=(notes or "").strip() or None,
        is_oil_change=oil_flag,
    )
    db.add(maint)
    db.commit()
    db.refresh(maint)
    return maint


def service_update_maintenance(
    db: Session,
    maint_id: int,
    moto_id: int,
    service_date: Any,
    service_type: str,
    odometer: float,
    cost: float = 0.0,
    notes: Optional[str] = None,
    is_oil_change: bool = False,
) -> Optional[Maintenance]:
    maint = db.query(Maintenance).filter(Maintenance.id == maint_id, Maintenance.moto_id == moto_id).first()
    if not maint:
        return None
    maint.date = parse_date_safe(service_date)
    maint.service_type = service_type.strip()
    maint.odometer = float(odometer or 0.0)
    maint.cost = float(cost or 0.0)
    maint.notes = (notes or "").strip() or None
    maint.is_oil_change = bool(is_oil_change or (service_type.strip().lower() == "vidange moteur"))
    db.commit()
    db.refresh(maint)
    return maint


def service_delete_maintenance(db: Session, maint_id: int, moto_id: int) -> bool:
    m = db.query(Maintenance).filter(Maintenance.id == maint_id, Maintenance.moto_id == moto_id).first()
    if m:
        db.delete(m)
        db.commit()
        return True
    return False