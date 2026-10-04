"""
backend.py
----------
Couche métier, configuration et services géographiques :
- Paramètres d'environnement et constantes.
- Service de Géocodage (nom de lieu -> [lat, lon]) avec fallback Nominatim.
- Service de Calcul d'itinéraire routier (GraphHopper API).
"""

import os
import re
import logging
from pathlib import Path
import requests

logger = logging.getLogger("backend")

# ==============================================================================
# CONFIGURATION & CONSTANTES
# ==============================================================================
BASE_DIR = Path(__file__).resolve().parent
DATA_DIR = BASE_DIR / "data"

GRAPHHOPPER_API_KEY = os.environ.get("GRAPHHOPPER_API_KEY", "").strip()
GRAPHHOPPER_ROUTE_URL = "https://graphhopper.com/api/1/route"
GRAPHHOPPER_GEOCODE_URL = "https://graphhopper.com/api/1/geocode"
NOMINATIM_GEOCODE_URL = "https://nominatim.openstreetmap.org/search"

DEFAULT_PROFILE = "car"
AVAILABLE_PROFILES = [
    {"label": "🚗 Voiture (car)", "value": "car"},
    {"label": "🚲 Vélo (bike)", "value": "bike"},
    {"label": "🚶 Piéton (foot)", "value": "foot"}
]

# Antananarivo, Madagascar
INITIAL_CENTER = [-18.8792, 47.5079]
INITIAL_ZOOM = 13

DEFAULT_START = {
    "lat": -18.8792,
    "lon": 47.5079,
    "name": "Antananarivo (Analakely)"
}

DEFAULT_DEST = {
    "lat": -18.9100,
    "lon": 47.5238,
    "name": "Ankadimbahoaka"
}

LAT_MIN, LAT_MAX = -90.0, 90.0
LON_MIN, LON_MAX = -180.0, 180.0

REQUEST_TIMEOUT = 12
SERVER_HOST = "127.0.0.1"
SERVER_PORT = 8050
DEBUG_MODE = False

USER_AGENT = "MadagascarRoutingApp/2.0 (Dash-Leaflet Application)"


# ==============================================================================
# SERVICE DE GÉOCODAGE (RECHERCHE TEXTUELLE)
# ==============================================================================
def geocode_location(query):
    """
    Convertit un nom de lieu ou une adresse en coordonnées [lat, lon].
    Gère également la saisie directe de coordonnées au format "lat, lon".
    Tente GraphHopper si la clé est présente, sinon bascule sur OSM Nominatim.
    """
    if not query or not str(query).strip():
        return {"success": False, "error_message": "Veuillez saisir un nom de lieu ou une adresse."}

    query_str = str(query).strip()

    # Détection directe de coordonnées au format "lat, lon"
    coord_pattern = r"^[-+]?([1-8]?\d(\.\d+)?|90(\.0+)?),\s*[-+]?(180(\.0+)?|((1[0-7]\d)|([1-9]?\d))(\.\d+)?)$"
    if re.match(coord_pattern, query_str):
        try:
            parts = [float(p.strip()) for p in query_str.split(",")]
            return {
                "success": True,
                "lat": parts[0],
                "lon": parts[1],
                "name": f"Coord. ({parts[0]:.4f}, {parts[1]:.4f})",
                "error_message": None
            }
        except ValueError:
            pass

    # 1. Tentative avec l'API GraphHopper Geocoding
    if GRAPHHOPPER_API_KEY:
        try:
            logger.info("Géocodage GraphHopper pour : %s", query_str)
            params = {
                "q": query_str,
                "locale": "fr",
                "limit": 1,
                "point": f"{INITIAL_CENTER[0]},{INITIAL_CENTER[1]}",
                "key": GRAPHHOPPER_API_KEY
            }
            res = requests.get(GRAPHHOPPER_GEOCODE_URL, params=params, timeout=REQUEST_TIMEOUT)
            if res.status_code == 200:
                data = res.json()
                hits = data.get("hits", [])
                if hits:
                    hit = hits[0]
                    point = hit.get("point", {})
                    name_parts = [hit.get("name"), hit.get("city"), hit.get("country")]
                    clean_name = ", ".join([p for p in name_parts if p]) or query_str
                    return {
                        "success": True,
                        "lat": float(point["lat"]),
                        "lon": float(point["lng"]),
                        "name": clean_name,
                        "error_message": None
                    }
        except Exception as exc:
            logger.warning("Échec géocodage GraphHopper, bascule Nominatim : %s", exc)

    # 2. Repli automatique (Fallback) : OpenStreetMap Nominatim
    try:
        logger.info("Géocodage Nominatim pour : %s", query_str)
        headers = {"User-Agent": USER_AGENT}
        params = {
            "q": query_str,
            "format": "json",
            "limit": 1,
            # Bounding box approximative englobant Madagascar
            "viewbox": "43.0,-11.5,50.8,-25.8",
            "bounded": 0
        }
        res = requests.get(NOMINATIM_GEOCODE_URL, params=params, headers=headers, timeout=REQUEST_TIMEOUT)
        if res.status_code == 200:
            results = res.json()
            if results:
                match = results[0]
                return {
                    "success": True,
                    "lat": float(match["lat"]),
                    "lon": float(match["lon"]),
                    "name": match.get("display_name", query_str).split(",")[0],
                    "error_message": None
                }
            return {"success": False, "error_message": f"Aucun résultat trouvé pour « {query_str} »."}
        return {"success": False, "error_message": f"Erreur de géocodage HTTP {res.status_code}."}
    except requests.exceptions.Timeout:
        return {"success": False, "error_message": "Délai dépassé lors de la recherche du lieu (timeout)."}
    except requests.exceptions.ConnectionError:
        return {"success": False, "error_message": "Erreur réseau : impossible de joindre le service de recherche."}
    except Exception as exc:
        logger.exception("Erreur inattendue géocodage : %s", exc)
        return {"success": False, "error_message": "Erreur technique lors de la localisation."}


# ==============================================================================
# SERVICE DE ROUTAGE (CALCUL D'ITINÉRAIRE)
# ==============================================================================
def calculate_route(start_lat, start_lon, dest_lat, dest_lon, profile="car"):
    """Calcule l'itinéraire entre deux coordonnées via GraphHopper."""
    if not GRAPHHOPPER_API_KEY:
        return _build_error_response("Clé API GraphHopper absente. Configurez la variable GRAPHHOPPER_API_KEY.")

    transport_profile = profile if profile else DEFAULT_PROFILE

    params = [
        ("point", f"{start_lat},{start_lon}"),
        ("point", f"{dest_lat},{dest_lon}"),
        ("profile", transport_profile),
        ("locale", "fr"),
        ("calc_points", "true"),
        ("points_encoded", "false"),
        ("key", GRAPHHOPPER_API_KEY)
    ]

    try:
        logger.info("Calcul itinéraire : [%f, %f] -> [%f, %f] (%s)", start_lat, start_lon, dest_lat, dest_lon, transport_profile)
        response = requests.get(GRAPHHOPPER_ROUTE_URL, params=params, timeout=REQUEST_TIMEOUT)

        if response.status_code == 400:
            return _build_error_response("Point inaccessible ou profil de transport indisponible sur cette zone.")
        if response.status_code == 401:
            return _build_error_response("Erreur 401 : Clé API GraphHopper invalide.")
        if response.status_code == 403:
            return _build_error_response("Erreur 403 : Quota dépassé ou restrictions de compte.")
        if response.status_code == 429:
            return _build_error_response("Erreur 429 : Trop de requêtes. Veuillez patienter un instant.")
        if response.status_code != 200:
            return _build_error_response(f"Erreur du service de routage (HTTP {response.status_code}).")

        data = response.json()
        paths = data.get("paths", [])
        if not paths:
            return _build_error_response("Aucun itinéraire routier trouvé entre ces deux points.")

        primary_path = paths[0]
        points_data = primary_path.get("points", {})
        raw_coordinates = points_data.get("coordinates", [])

        if not raw_coordinates:
            return _build_error_response("Aucun tracé géographique fourni pour ce trajet.")

        # Inversion [lon, lat] (GeoJSON) -> [lat, lon] (Leaflet)
        leaflet_coordinates = [[pt[1], pt[0]] for pt in raw_coordinates]

        distance_meters = float(primary_path.get("distance", 0.0))
        time_ms = float(primary_path.get("time", 0.0))
        duration_seconds = time_ms / 1000.0

        return {
            "success": True,
            "distance_m": distance_meters,
            "distance_km": round(distance_meters / 1000.0, 2),
            "duration_s": duration_seconds,
            "duration_min": round(duration_seconds / 60.0, 1),
            "coordinates": leaflet_coordinates,
            "error_message": None
        }

    except requests.exceptions.Timeout:
        return _build_error_response("Le délai de calcul d'itinéraire a expiré.")
    except requests.exceptions.ConnectionError:
        return _build_error_response("Erreur de connexion avec le serveur de calcul d'itinéraire.")
    except Exception as exc:
        logger.exception("Erreur inattendue calcul : %s", exc)
        return _build_error_response("Une erreur interne est survenue lors du calcul.")


def _build_error_response(message):
    return {
        "success": False,
        "distance_m": 0.0,
        "distance_km": 0.0,
        "duration_s": 0.0,
        "duration_min": 0.0,
        "coordinates": [],
        "error_message": message
    }