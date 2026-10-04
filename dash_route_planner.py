"""
dash_route_planner.py
---------------------
Moteur cartographique, géocodeur direct & inverse pour Dash & Leaflet.
Cartographie standard claire (OpenStreetMap) et Satellite (Esri), sans clé requise.
"""

import re
import math
import logging
from typing import Dict, Any, Tuple, Optional
import requests

from database import settings

logger = logging.getLogger("MotoTracker.RoutePlanner")

DEFAULT_PRELOADED_PLACES: Dict[str, Tuple[float, float, str]] = {
    # Centre & Nord
    "analakely": (-18.8792, 47.5079, "Antananarivo (Analakely)"),
    "antananarivo": (-18.8792, 47.5079, "Antananarivo"),
    "ankorondrano": (-18.8820, 47.5240, "Ankorondrano"),
    "analamahitsy": (-18.8680, 47.5450, "Analamahitsy"),
    "ivato": (-18.7969, 47.4788, "Aéroport Ivato"),
    "talatamaty": (-18.8350, 47.4650, "Talatamaty"),
    "sabotsy namehana": (-18.8250, 47.5400, "Sabotsy Namehana"),
    # Sud & RN7
    "ankadimbahoaka": (-18.9100, 47.5238, "Ankadimbahoaka"),
    "anosy": (-18.9140, 47.5210, "Lac Anosy"),
    "tanjombato": (-18.9567, 47.5273, "Tanjombato"),
    "andoharanofotsy": (-18.9800, 47.5300, "Andoharanofotsy"),
    "ambatofotsy": (-19.0400, 47.5300, "Ambatofotsy"),
    # Ouest & RN1
    "fenoarivo": (-18.9333, 47.4333, "Fenoarivo"),
    "alakamisy": (-18.9485, 47.4215, "Alakamisy Fenoarivo"),
    "ambohimangidy": (-18.9550, 47.4750, "Ambohimangidy"),
    "atsimombohitra": (-18.9450, 47.4800, "Atsimombohitra"),
    "ampitatafika": (-18.9280, 47.4850, "Ampitatafika"),
    "malaza": (-18.9420, 47.4600, "Malaza"),
    "vontovorona": (-18.9750, 47.4350, "Vontovorona"),
    "itaosy": (-18.8950, 47.4780, "Itaosy"),
    "andavamamba": (-18.9080, 47.5050, "Andavamamba"),
    "ambohimandroso": (-18.9180, 47.4700, "Ambohimandroso"),
    "ambajanahary": (-18.9300, 47.4500, "Ambajanahary"),
    # Est
    "ambohimangakely": (-18.9050, 47.5750, "Ambohimangakely"),
}

# Uniquement des calques fiables, gratuits et sans clé API requise
MAP_THEMES = {
    "simple": {
        "url": "https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png",
        "attribution": '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a>',
        "name": "Carte",
    },
    "satellite": {
        "url": "https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}",
        "attribution": "Tiles &copy; Esri",
        "name": "Satellite",
    },
}


def haversine_distance_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    r = 6371.0
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    delta_phi = math.radians(lat2 - lat1)
    delta_lambda = math.radians(lon2 - lon1)
    a = (
        math.sin(delta_phi / 2.0) ** 2
        + math.cos(phi1) * math.cos(phi2) * math.sin(delta_lambda / 2.0) ** 2
    )
    return r * 2.0 * math.atan2(math.sqrt(a), math.sqrt(1.0 - a))


class RouteEngine:
    def __init__(self, graphhopper_api_key: Optional[str] = None, timeout: int = 8):
        raw_key = graphhopper_api_key if graphhopper_api_key else settings.GRAPHHOPPER_API_KEY
        self.api_key = str(raw_key or "").strip().strip('"').strip("'")
        # Timeout borné : Vercel (Hobby ~10-15s, Pro 60s) ne supporte pas les
        # requêtes sortantes bloquantes longues. 8s max par appel externe.
        try:
            self.timeout = max(1, min(int(timeout), 8))
        except (TypeError, ValueError):
            self.timeout = 8
        self.places = dict(DEFAULT_PRELOADED_PLACES)
        self.user_agent = "OdomiMotoTracker/2.0 (contact@odomi.app)"

    def extract_lat_lon(self, click_data: Any) -> Tuple[Optional[float], Optional[float]]:
        if not click_data:
            return None, None
        if isinstance(click_data, dict):
            latlng = click_data.get("latlng")
            if isinstance(latlng, dict):
                return float(latlng.get("lat")), float(latlng.get("lng") or latlng.get("lon"))
            lat = click_data.get("lat") or click_data.get("latitude")
            lon = click_data.get("lng") or click_data.get("lon")
            if lat is not None and lon is not None:
                return float(lat), float(lon)
        return None, None

    def reverse_geocode(self, lat: float, lon: float) -> str:
        closest_name = None
        min_dist = float("inf")
        for key, val in self.places.items():
            dist = haversine_distance_km(lat, lon, val[0], val[1])
            if dist < min_dist:
                min_dist = dist
                closest_name = val[2]

        if min_dist <= 1.8 and closest_name:
            return closest_name

        try:
            url = "https://nominatim.openstreetmap.org/reverse"
            params = {
                "lat": lat,
                "lon": lon,
                "format": "json",
                "zoom": 15,
                "addressdetails": 1,
            }
            res = requests.get(url, params=params, headers={"User-Agent": self.user_agent}, timeout=self.timeout)
            if res.status_code == 200:
                data = res.json()
                addr = data.get("address", {})
                place = (
                    addr.get("village")
                    or addr.get("suburb")
                    or addr.get("neighbourhood")
                    or addr.get("hamlet")
                    or addr.get("town")
                    or addr.get("city_district")
                    or addr.get("municipality")
                    or addr.get("city")
                )
                if place:
                    clean_place = str(place).strip()
                    self.places[clean_place.lower()] = (lat, lon, clean_place)
                    return clean_place
        except requests.RequestException as exc:
            logger.debug("Géocodage inverse indisponible: %s", exc)

        if min_dist <= 6.0 and closest_name:
            return f"{closest_name} (proche)"

        return f"Secteur ({lat:.3f}, {lon:.3f})"

    def geocode(self, query: str) -> Dict[str, Any]:
        q = str(query or "").strip()
        if not q:
            return {"success": False, "error_message": "Veuillez saisir un lieu."}

        if re.match(r"^[-+]?\d+(\.\d+)?[,\s]+[-+]?\d+(\.\d+)?$", q):
            try:
                parts = [float(p.strip()) for p in re.split(r"[,;\s]+", q) if p.strip()]
                name = self.reverse_geocode(parts[0], parts[1])
                return {"success": True, "lat": parts[0], "lon": parts[1], "name": name}
            except (ValueError, IndexError) as exc:
                logger.debug("Coordonnées invalides: %s", exc)

        q_norm = q.lower()
        for k, v in self.places.items():
            if k in q_norm or q_norm in k:
                return {"success": True, "lat": v[0], "lon": v[1], "name": v[2]}

        if self.api_key:
            try:
                res = requests.get(
                    "https://graphhopper.com/api/1/geocode",
                    params={"q": q, "locale": "fr", "limit": 1, "key": self.api_key},
                    timeout=self.timeout,
                )
                if res.status_code == 200:
                    hits = res.json().get("hits", [])
                    if hits:
                        pt = hits[0].get("point", {})
                        return {"success": True, "lat": float(pt["lat"]), "lon": float(pt["lng"]), "name": hits[0].get("name") or q}
            except requests.RequestException as exc:
                logger.debug("Géocodeur GraphHopper indisponible: %s", exc)

        try:
            res = requests.get(
                "https://nominatim.openstreetmap.org/search",
                params={"q": q, "format": "json", "limit": 1},
                headers={"User-Agent": self.user_agent},
                timeout=self.timeout,
            )
            if res.status_code == 200 and res.json():
                r = res.json()[0]
                name = r.get("display_name", q).split(",")[0]
                return {"success": True, "lat": float(r["lat"]), "lon": float(r["lon"]), "name": name}
        except requests.RequestException as exc:
            logger.debug("Géocodeur Nominatim indisponible: %s", exc)

        return {"success": False, "error_message": f"Introuvable : « {q} »"}

    def calculate_route(self, start_lat: float, start_lon: float, dest_lat: float, dest_lon: float, profile: str = "car") -> Dict[str, Any]:
        if self.api_key:
            try:
                params = [
                    ("point", f"{start_lat},{start_lon}"),
                    ("point", f"{dest_lat},{dest_lon}"),
                    ("profile", "car" if profile not in ("bike", "foot") else profile),
                    ("locale", "fr"),
                    ("calc_points", "true"),
                    ("points_encoded", "false"),
                    ("key", self.api_key),
                ]
                res = requests.get("https://graphhopper.com/api/1/route", params=params, timeout=self.timeout)
                if res.status_code == 200:
                    path = res.json()["paths"][0]
                    coords = [[pt[1], pt[0]] for pt in path.get("points", {}).get("coordinates", [])]
                    return {
                        "success": True,
                        "distance_km": round(float(path.get("distance", 0.0)) / 1000.0, 2),
                        "duration_min": round(float(path.get("time", 0.0)) / 60000.0, 1),
                        "coordinates": coords,
                        "source": "GraphHopper",
                    }
            except requests.RequestException as exc:
                logger.debug("Routage GraphHopper indisponible: %s", exc)

        try:
            mode = "routed-bike" if profile == "bike" else ("routed-foot" if profile == "foot" else "routed-car")
            url = f"https://routing.openstreetmap.de/{mode}/route/v1/driving/{start_lon},{start_lat};{dest_lon},{dest_lat}"
            res = requests.get(url, params={"overview": "full", "geometries": "geojson"}, headers={"User-Agent": self.user_agent}, timeout=self.timeout)
            if res.status_code == 200:
                data = res.json()
                if data.get("code") == "Ok" and data.get("routes"):
                    r = data["routes"][0]
                    coords = [[pt[1], pt[0]] for pt in r["geometry"]["coordinates"]]
                    return {
                        "success": True,
                        "distance_km": round(float(r["distance"]) / 1000.0, 2),
                        "duration_min": round(float(r["duration"]) / 60.0, 1),
                        "coordinates": coords,
                        "source": "OSM",
                    }
        except requests.RequestException as exc:
            logger.debug("Routage OSM indisponible: %s", exc)

        return {"success": False, "error_message": "Calcul d'itinéraire indisponible."}