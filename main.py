"""
main.py
-------
Serveur FastAPI unifié : Dashboard moderne avec KPIs et graphiques récents,
gestion fluide des onglets (Trajets, Pleins, Entretien, Carte), pagination Jinja2,
édition en direct et API d'odomètre rétroactif.
"""

import json
import logging
import warnings
from datetime import date
from pathlib import Path
from typing import Optional
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request, Depends, Form, status
from fastapi.responses import HTMLResponse, RedirectResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session

try:
    from a2wsgi import WSGIMiddleware
except ImportError:
    with warnings.catch_warnings():
        warnings.filterwarnings("ignore", category=DeprecationWarning)
        from starlette.middleware.wsgi import WSGIMiddleware

from database import (
    engine,
    Base,
    get_db,
    SessionLocal,
    settings,
    ensure_db_migrations,
    User,
    Moto,
    Trip,
    Refuel,
    Maintenance,
    RoutePreset,
)
from services import (
    verify_password,
    get_password_hash,
    create_access_token,
    get_current_user,
    get_active_moto,
    get_oil_change_status,
    calculate_odometer_at_date,
    resolve_period_dates,
    get_dashboard_stats,
    get_filtered_correlated_data,
    paginate_data,
    format_date_safe,
    parse_date_safe,
    service_create_trip,
    service_update_trip,
    service_create_refuel,
    service_delete_refuel,
    service_create_maintenance,
    service_update_maintenance,
    service_delete_maintenance,
    service_create_preset,
)
from dash_app import create_dash_app

logger = logging.getLogger("MotoTracker.Main")


@asynccontextmanager
async def lifespan(app: FastAPI):
    if not settings.SECURE_KEY_CONFIGURED:
        logger.warning(
            "SECRET_KEY utilise la valeur de développement par défaut. "
            "Définissez SECRET_KEY en production."
        )
    # Initialisation DB tolérante : sur serverless (Vercel), un backend
    # indisponible ne doit jamais empêcher l'import ni faire planter le boot.
    try:
        Base.metadata.create_all(bind=engine)
        ensure_db_migrations()
    except Exception as exc:
        logger.warning("Initialisation DB reportée: %s", exc)
    else:
        try:
            with SessionLocal() as db:
                if db.query(User).count() == 0:
                    demo_user = User(
                        email=settings.DEMO_EMAIL,
                        hashed_password=get_password_hash(settings.DEMO_PASSWORD),
                        name=settings.DEMO_NAME,
                    )
                    db.add(demo_user)
                    db.commit()
                    db.refresh(demo_user)

                    demo_moto = Moto(
                        user_id=demo_user.id,
                        name="Kymco VJR 100cc",
                        license_plate="1234-TAB",
                        initial_odometer=0.0,
                        oil_interval_km=1000.0,
                        is_active=True,
                    )
                    db.add(demo_moto)
                    db.commit()
                    logger.info("Compte de démonstration créé (%s).", settings.DEMO_EMAIL)
        except Exception as exc:
            logger.warning("Seed démo reporté: %s", exc)
    yield

app = FastAPI(title="Odomi MotoTracker Pro", lifespan=lifespan)

# Dash (Flask/WSGI) monté via a2wsgi. requests_pathname_prefix DOIT == "/planner/"
# car templates/app.html embarque <iframe src="/planner/"> (chemin préservé).
dash_app_instance = create_dash_app(requests_pathname_prefix="/planner/")

# Synchronisation styles et Tailwind pour Dash & Leaflet (local, voir setup_offline.py)
DASH_CUSTOM_HEAD = """
<link rel="stylesheet" href="/static/vendor/css/fonts.css">
<script src="/static/vendor/tailwind.js"></script>
<script>
    tailwind.config = {
        darkMode: 'class',
        theme: {
            extend: {
                colors: {
                    brand: { 50: '#fff7ed', 100: '#ffedd5', 400: '#fb923c', 500: '#f97316', 600: '#ea580c', 700: '#c2410c' }
                }
            }
        }
    };
</script>
<script>
    (function() {
        function applyLocalTheme() {
            try {
                var stored = localStorage.getItem('odomi_theme');
                var isDark = stored === 'dark';
                if (!stored && window.parent && window.parent.document && window.parent.document.documentElement) {
                    isDark = window.parent.document.documentElement.classList.contains('dark');
                }
                document.documentElement.classList.toggle('dark', isDark);
                if (document.body) {
                    document.body.classList.toggle('dark', isDark);
                    document.body.style.backgroundColor = isDark ? '#0f172a' : '#f8fafc';
                }
            } catch(e) {}
        }
        applyLocalTheme();
        document.addEventListener('DOMContentLoaded', function() {
            applyLocalTheme();
            setTimeout(function() { window.dispatchEvent(new Event('resize')); }, 300);
        });
        window.addEventListener('message', function(event) {
            if (event.data && event.data.type === 'ODOMI_THEME_CHANGE') {
                var isDark = event.data.theme === 'dark';
                document.documentElement.classList.toggle('dark', isDark);
                if (document.body) {
                    document.body.classList.toggle('dark', isDark);
                    document.body.style.backgroundColor = isDark ? '#0f172a' : '#f8fafc';
                }
            }
        });
    })();
</script>
"""

if hasattr(dash_app_instance, "index_string") and dash_app_instance.index_string:
    if "</head>" in dash_app_instance.index_string:
        dash_app_instance.index_string = dash_app_instance.index_string.replace(
            "</head>", f"{DASH_CUSTOM_HEAD}\n</head>"
        )

app.mount("/planner", WSGIMiddleware(dash_app_instance.server))

BASE_DIR = Path(__file__).resolve().parent
_TEMPLATES_CANDIDATE = BASE_DIR / "templates"
TEMPLATES_DIR = _TEMPLATES_CANDIDATE if _TEMPLATES_CANDIDATE.is_dir() else BASE_DIR
templates = Jinja2Templates(directory=str(TEMPLATES_DIR))
# Dossier statique (assets vendor telecharges via `python setup_offline.py`).
# Si des assets manquent et qu'Internet est indisponible, /static renverra
# 404 -> le bandeau d'erreur de templates/app.html explique la marche a suivre.
_STATIC_CANDIDATE = BASE_DIR / "static"
if _STATIC_CANDIDATE.is_dir():
    app.mount("/static", StaticFiles(directory=str(_STATIC_CANDIDATE)), name="static")
else:
    logger.warning(
        "Dossier 'static/' absent. Executez 'python setup_offline.py' avec "
        "une connexion Internet pour activer le mode hors-ligne."
    )


def format_number_fr(value) -> str:
    try:
        return f"{float(value or 0):,.1f}".replace(",", " ").replace(".", ",")
    except (TypeError, ValueError):
        return str(value)


def format_currency_fr(value) -> str:
    try:
        return f"{float(value or 0):,.0f} Ar".replace(",", " ")
    except (TypeError, ValueError):
        return f"{value} Ar"


# Filtres Jinja2
templates.env.filters["number_fr"] = format_number_fr
templates.env.filters["currency_fr"] = format_currency_fr
templates.env.filters["date_fr"] = format_date_safe


@app.get("/health", include_in_schema=False)
def health_check():
    """Sonde de santé (Vercel, Render, Docker...). Ne touche jamais la DB."""
    return {"status": "ok"}


# Entrypoint local Windows : `python main.py` (Vercel importe `main:app`,
# ce bloc __main__ n'est donc jamais exécuté en production serverless).
if __name__ == "__main__":
    import uvicorn

    uvicorn.run("main:app", host=settings.HOST, port=settings.PORT)


def render_template(request: Request, template_name: str, context: dict, status_code: int = 200) -> HTMLResponse:
    """
    Rendu robuste compatible Python 3.13 / Starlette.
    Ne bascule sur le fallback que si la signature de TemplateResponse est incompatible,
    évitant de masquer les erreurs de rendu Jinja.
    """
    ctx = dict(context)
    ctx["request"] = request
    try:
        return templates.TemplateResponse(
            request=request,
            name=template_name,
            context=ctx,
            status_code=status_code,
        )
    except TypeError as te:
        err_str = str(te)
        if "unexpected keyword argument" in err_str or "too many positional arguments" in err_str:
            return templates.TemplateResponse(template_name, ctx, status_code=status_code)
        raise te


TOASTS_MAP = {
    "trip_added": ("Trajet enregistré avec succès !", "success"),
    "trip_updated": ("Trajet mis à jour !", "success"),
    "trip_deleted": ("Trajet supprimé.", "info"),
    "refuel_added": ("Plein enregistré !", "success"),
    "refuel_deleted": ("Plein supprimé.", "info"),
    "maint_added": ("Entretien enregistré !", "success"),
    "maint_updated": ("Entretien mis à jour !", "success"),
    "maint_deleted": ("Entretien supprimé.", "info"),
    "moto_switched": ("Moto active modifiée.", "info"),
}


# --- AUTHENTIFICATION ---

@app.get("/login")
def login_view(request: Request, error: Optional[str] = None):
    return render_template(request, "app.html", {"is_login": True, "error": error})


@app.post("/login")
def login_post(
    request: Request,
    username: str = Form(...),
    password: str = Form(...),
    db: Session = Depends(get_db),
):
    user = db.query(User).filter(User.email == username.strip().lower()).first()
    if not user or not verify_password(password, user.hashed_password):
        return render_template(
            request, "app.html", {"is_login": True, "error": "Email ou mot de passe incorrect."}
        )

    token = create_access_token({"sub": user.email})
    resp = RedirectResponse(url="/", status_code=status.HTTP_303_SEE_OTHER)
    # En production derrière HTTPS (Vercel), le cookie doit être `Secure`.
    # En local (http://...), `Secure` empêcherait le navigateur de le renvoyer.
    # `settings.DEBUG=true` => http local ; sinon on suit le schéma de la requête.
    forwarded_proto = (request.headers.get("x-forwarded-proto", "") or "").split(",")[0].strip().lower()
    scheme = (forwarded_proto or request.url.scheme or "").lower()
    is_secure = (not settings.DEBUG) and scheme == "https"
    resp.set_cookie(
        key="access_token",
        value=f"Bearer {token}",
        httponly=True,
        samesite="lax",
        secure=is_secure,
        max_age=settings.ACCESS_TOKEN_EXPIRE_DAYS * 86400,
        path="/",
    )
    return resp


@app.get("/logout")
def logout():
    resp = RedirectResponse(url="/login", status_code=status.HTTP_303_SEE_OTHER)
    resp.delete_cookie("access_token")
    return resp


# --- VUE PRINCIPALE ---

@app.get("/")
def dashboard(
    request: Request,
    tab: str = "dashboard",
    subtab: str = "trajets",
    period: str = "all",
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    page: int = 1,
    q: Optional[str] = None,
    msg: Optional[str] = None,
    current_user: User = Depends(get_current_user),
    moto: Moto = Depends(get_active_moto),
    db: Session = Depends(get_db),
):
    p_start, p_end, active_period, prev_start, prev_end = resolve_period_dates(
        db, moto, period, start_date, end_date
    )
    stats = get_dashboard_stats(db, moto, p_start, p_end, prev_start, prev_end)
    oil_status = get_oil_change_status(db, moto)

    # Données corrélées & filtrées
    refuels, trips = get_filtered_correlated_data(db, moto, p_start, p_end, q)

    # Pagination compatible objet & liste
    paginated_trips = paginate_data(trips, page=page, page_size=15)
    paginated_refuels = paginate_data(refuels, page=page, page_size=15)

    maintenances = db.query(Maintenance).filter(Maintenance.moto_id == moto.id).order_by(Maintenance.date.desc(), Maintenance.id.desc()).all()
    presets = db.query(RoutePreset).filter(RoutePreset.moto_id == moto.id).all()
    all_motos = db.query(Moto).filter(Moto.user_id == current_user.id).all()

    toast_info = {"text": TOASTS_MAP[msg][0], "type": TOASTS_MAP[msg][1]} if msg in TOASTS_MAP else None

    return render_template(
        request=request,
        template_name="app.html",
        context={
            "is_login": False,
            "user": current_user,
            "moto": moto,
            "motos": all_motos,
            "active_tab": tab,
            "tab": tab,
            "active_subtab": subtab,
            "subtab": subtab,
            "period": active_period,
            "start_date": p_start.strftime("%Y-%m-%d") if p_start else "",
            "end_date": p_end.strftime("%Y-%m-%d") if p_end else "",
            "search_query": q or "",
            "q": q or "",
            "oil_status": oil_status,
            "stats": stats,
            # Objets paginés (.items est une liste)
            "paginated_trips": paginated_trips,
            "paginated_refuels": paginated_refuels,
            # Rétrocompatibilité directe
            "trips": paginated_trips.items,
            "refuels": paginated_refuels.items,
            "raw_trips_count": len(trips),
            "raw_refuels_count": len(refuels),
            "maintenances": maintenances,
            "presets": presets,
            "presets_json": json.dumps([p.to_dict() for p in presets]),
            "chart_data_json": json.dumps(stats.get("charts", {})),
            "today": date.today().strftime("%Y-%m-%d"),
            "default_fuel_price": settings.DEFAULT_FUEL_PRICE_PER_LITER,
            "toast": toast_info,
        },
    )


# --- API CALCUL ODOMÈTRE RÉTROACTIF ---
@app.get("/api/odometer-at-date")
def api_get_odometer_at_date(
    date_str: str,
    moto: Moto = Depends(get_active_moto),
    db: Session = Depends(get_db),
):
    target_d = parse_date_safe(date_str)
    odo = calculate_odometer_at_date(db, moto, target_d)
    return JSONResponse({"success": True, "date": str(target_d), "odometer": odo})


# --- ACTIONS TRAJETS ---
@app.post("/trips/add")
def add_trip(
    trip_date: str = Form(...),
    depart: Optional[str] = Form(None),
    destination: Optional[str] = Form(None),
    aller: float = Form(0.0),
    retour: float = Form(0.0),
    total: float = Form(...),
    has_refuel: Optional[bool] = Form(False),
    refuel_liters: float = Form(0.0),
    refuel_amount: float = Form(0.0),
    refuel_notes: Optional[str] = Form(None),
    is_full_tank: Optional[int] = Form(1),
    moto: Moto = Depends(get_active_moto),
    db: Session = Depends(get_db),
):
    service_create_trip(
        db, moto.id, trip_date, aller, retour, total, depart, destination,
        has_refuel=bool(has_refuel), refuel_liters=refuel_liters,
        refuel_amount=refuel_amount, refuel_notes=refuel_notes,
        is_full_tank=bool(is_full_tank),
    )
    return RedirectResponse(url="/?tab=trajets&msg=trip_added", status_code=status.HTTP_303_SEE_OTHER)


@app.post("/trips/update/{trip_id}")
def update_trip(
    trip_id: int,
    trip_date: str = Form(...),
    depart: Optional[str] = Form(None),
    destination: Optional[str] = Form(None),
    aller: float = Form(0.0),
    retour: float = Form(0.0),
    total: float = Form(...),
    moto: Moto = Depends(get_active_moto),
    db: Session = Depends(get_db),
):
    service_update_trip(db, trip_id, moto.id, trip_date, aller, retour, total, depart, destination)
    return RedirectResponse(url="/?tab=trajets&msg=trip_updated", status_code=status.HTTP_303_SEE_OTHER)


@app.post("/trips/delete/{trip_id}")
def delete_trip(trip_id: int, moto: Moto = Depends(get_active_moto), db: Session = Depends(get_db)):
    t = db.query(Trip).filter(Trip.id == trip_id, Trip.moto_id == moto.id).first()
    if t:
        db.delete(t)
        db.commit()
    return RedirectResponse(url="/?tab=trajets&msg=trip_deleted", status_code=status.HTTP_303_SEE_OTHER)


# --- ACTIONS PLEINS ---
@app.post("/refuels/add")
def add_refuel(
    refuel_date: str = Form(...),
    liters: float = Form(...),
    amount: float = Form(...),
    notes: Optional[str] = Form(None),
    is_full_tank: Optional[int] = Form(None),
    moto: Moto = Depends(get_active_moto),
    db: Session = Depends(get_db),
):
    service_create_refuel(db, moto.id, refuel_date, liters, amount, notes, bool(is_full_tank))
    return RedirectResponse(url="/?tab=trajets&subtab=pleins&msg=refuel_added", status_code=status.HTTP_303_SEE_OTHER)


@app.post("/refuels/delete/{refuel_id}")
def delete_refuel(refuel_id: int, moto: Moto = Depends(get_active_moto), db: Session = Depends(get_db)):
    service_delete_refuel(db, refuel_id, moto.id)
    return RedirectResponse(url="/?tab=trajets&subtab=pleins&msg=refuel_deleted", status_code=status.HTTP_303_SEE_OTHER)


# --- ACTIONS ENTRETIENS ---
@app.post("/maintenance/add")
def add_maintenance(
    service_date: str = Form(...),
    service_type: str = Form(...),
    service_type_custom: Optional[str] = Form(None),
    odometer: float = Form(...),
    cost: float = Form(0.0),
    notes: Optional[str] = Form(None),
    is_oil_change: Optional[int] = Form(None),
    moto: Moto = Depends(get_active_moto),
    db: Session = Depends(get_db),
):
    final_type = (service_type_custom or "").strip() if (service_type == "Autre" and service_type_custom) else service_type.strip()
    oil_flag = bool(is_oil_change or (final_type.lower() == "vidange moteur"))
    service_create_maintenance(db, moto.id, service_date, final_type, odometer, cost, notes, is_oil_change=oil_flag)
    return RedirectResponse(url="/?tab=entretien&msg=maint_added", status_code=status.HTTP_303_SEE_OTHER)


@app.post("/maintenance/update/{maint_id}")
def update_maintenance(
    maint_id: int,
    service_date: str = Form(...),
    service_type: str = Form(...),
    service_type_custom: Optional[str] = Form(None),
    odometer: float = Form(...),
    cost: float = Form(0.0),
    notes: Optional[str] = Form(None),
    is_oil_change: Optional[int] = Form(None),
    moto: Moto = Depends(get_active_moto),
    db: Session = Depends(get_db),
):
    final_type = (service_type_custom or "").strip() if (service_type == "Autre" and service_type_custom) else service_type.strip()
    oil_flag = bool(is_oil_change or (final_type.lower() == "vidange moteur"))
    service_update_maintenance(db, maint_id, moto.id, service_date, final_type, odometer, cost, notes, is_oil_change=oil_flag)
    return RedirectResponse(url="/?tab=entretien&msg=maint_updated", status_code=status.HTTP_303_SEE_OTHER)


@app.post("/maintenance/delete/{maint_id}")
def delete_maintenance(maint_id: int, moto: Moto = Depends(get_active_moto), db: Session = Depends(get_db)):
    service_delete_maintenance(db, maint_id, moto.id)
    return RedirectResponse(url="/?tab=entretien&msg=maint_deleted", status_code=status.HTTP_303_SEE_OTHER)


# --- ACTIONS PRESETS ---
@app.post("/presets/add")
def add_preset(
    name: str = Form(...),
    depart: str = Form(...),
    destination: str = Form(...),
    aller: float = Form(0.0),
    retour: float = Form(0.0),
    moto: Moto = Depends(get_active_moto),
    db: Session = Depends(get_db),
):
    service_create_preset(db, moto.id, name, depart, destination, aller, retour)
    return RedirectResponse(url="/?tab=trajets", status_code=status.HTTP_303_SEE_OTHER)


@app.post("/presets/delete/{preset_id}")
def delete_preset(preset_id: int, moto: Moto = Depends(get_active_moto), db: Session = Depends(get_db)):
    p = db.query(RoutePreset).filter(RoutePreset.id == preset_id, RoutePreset.moto_id == moto.id).first()
    if p:
        db.delete(p)
        db.commit()
    return RedirectResponse(url="/?tab=trajets", status_code=status.HTTP_303_SEE_OTHER)


# --- SÉLECTION MOTO ---
@app.post("/motos/switch/{moto_id}")
def switch_moto(moto_id: int, current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    db.query(Moto).filter(Moto.user_id == current_user.id).update({"is_active": False})
    t = db.query(Moto).filter(Moto.id == moto_id, Moto.user_id == current_user.id).first()
    if t:
        t.is_active = True
        db.commit()
    return RedirectResponse(url="/?msg=moto_switched", status_code=status.HTTP_303_SEE_OTHER)