"""
dash_route_planner.py
---------------------
Module universel et réutilisable de calcul d'itinéraire et géocodage pour Dash.
S'intègre dans toute application Dash existante ou fonctionne de manière autonome.

Auteur : Module d'intégration Dash / Leaflet
Dépendances : dash, dash-leaflet, requests
"""

import os
import re
import logging
from typing import Dict, Any, Tuple, Optional, List
import requests
import dash
from dash import dcc, html, Input, Output, State
import dash_leaflet as dl

logger = logging.getLogger("DashRoutePlanner")

# ==============================================================================
# 1. MOTEUR MÉTIER (GÉOCODAGE & CALCUL D'ITINÉRAIRE)
# ==============================================================================

class RouteEngine:
    """Moteur de calcul d'itinéraires et de géocodage sans adhérence à l'interface."""

    def __init__(
        self,
        graphhopper_api_key: Optional[str] = None,
        timeout: int = 12,
        default_profile: str = "car",
        nominatim_viewbox: Optional[str] = None,  # ex: "43.0,-11.5,50.8,-25.8" pour Madagascar
        user_agent: str = "DashRoutePlanner/2.0"
    ):
        self.api_key = graphhopper_api_key or os.environ.get("GRAPHHOPPER_API_KEY", "").strip()
        self.timeout = timeout
        self.default_profile = default_profile
        self.nominatim_viewbox = nominatim_viewbox
        self.user_agent = user_agent
        self.route_url = "https://graphhopper.com/api/1/route"
        self.geocode_url = "https://graphhopper.com/api/1/geocode"
        self.nominatim_url = "https://nominatim.openstreetmap.org/search"

    def extract_lat_lon_from_click(self, click_data: Any) -> Tuple[Optional[float], Optional[float]]:
        """
        Extrait uniformément [lat, lon] depuis l'événement de clic Dash-Leaflet
        (compatible clickData, click_lat_lng, dicts et listes).
        """
        if not click_data:
            return None, None

        if isinstance(click_data, dict):
            # Format Leaflet clickData : {"latlng": {"lat": x, "lng": y}}
            latlng = click_data.get("latlng")
            if isinstance(latlng, dict):
                lat = latlng.get("lat")
                lon = latlng.get("lng") or latlng.get("lon")
                if lat is not None and lon is not None:
                    return float(lat), float(lon)
            elif isinstance(latlng, (list, tuple)) and len(latlng) >= 2:
                return float(latlng[0]), float(latlng[1])

            # Clés directes
            lat = click_data.get("lat") or click_data.get("latitude")
            lon = click_data.get("lng") or click_data.get("lon") or click_data.get("longitude")
            if lat is not None and lon is not None:
                return float(lat), float(lon)

        if isinstance(click_data, (list, tuple)) and len(click_data) >= 2:
            return float(click_data[0]), float(click_data[1])

        return None, None

    def geocode(self, query: str) -> Dict[str, Any]:
        """
        Résout une adresse ou des coordonnées brutes "lat, lon".
        Retourne : {"success": bool, "lat": float, "lon": float, "name": str, "error_message": str}
        """
        if not query or not str(query).strip():
            return {"success": False, "lat": None, "lon": None, "name": "", "error_message": "Veuillez saisir un lieu valide."}

        query_str = str(query).strip()

        # 1. Vérification saisie coordonnées directes ("lat, lon")
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

        # 2. GraphHopper Geocoding (si clé disponible)
        if self.api_key:
            try:
                params = {"q": query_str, "locale": "fr", "limit": 1, "key": self.api_key}
                res = requests.get(self.geocode_url, params=params, timeout=self.timeout)
                if res.status_code == 200:
                    hits = res.json().get("hits", [])
                    if hits:
                        hit = hits[0]
                        pt = hit.get("point", {})
                        parts_name = [hit.get("name"), hit.get("city"), hit.get("country")]
                        clean_name = ", ".join([p for p in parts_name if p]) or query_str
                        return {
                            "success": True,
                            "lat": float(pt["lat"]),
                            "lon": float(pt["lng"]),
                            "name": clean_name,
                            "error_message": None
                        }
            except Exception as exc:
                logger.warning("Échec géocodage GraphHopper, repli sur Nominatim : %s", exc)

        # 3. Fallback Nominatim (OSM)
        try:
            params = {"q": query_str, "format": "json", "limit": 1}
            if self.nominatim_viewbox:
                params["viewbox"] = self.nominatim_viewbox
                params["bounded"] = 0

            headers = {"User-Agent": self.user_agent}
            res = requests.get(self.nominatim_url, params=params, headers=headers, timeout=self.timeout)
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
                return {"success": False, "lat": None, "lon": None, "name": "", "error_message": f"Aucun résultat pour « {query_str} »."}
            return {"success": False, "lat": None, "lon": None, "name": "", "error_message": f"Erreur de recherche HTTP {res.status_code}."}
        except requests.exceptions.Timeout:
            return {"success": False, "lat": None, "lon": None, "name": "", "error_message": "Délai de recherche dépassé (timeout)."}
        except Exception as exc:
            return {"success": False, "lat": None, "lon": None, "name": "", "error_message": f"Erreur de géocodage : {str(exc)}"}

    def calculate_route(
        self,
        start_lat: float,
        start_lon: float,
        dest_lat: float,
        dest_lon: float,
        profile: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Calcule l'itinéraire via l'API GraphHopper.
        Inversion automatique de GeoJSON [lon, lat] vers Leaflet [lat, lon].
        """
        if not self.api_key:
            return {
                "success": False,
                "distance_km": 0.0,
                "duration_min": 0.0,
                "coordinates": [],
                "error_message": "Clé API GraphHopper absente. Configurez la clé dans l'initialiseur ou la variable d'environnement GRAPHHOPPER_API_KEY."
            }

        transport_profile = profile or self.default_profile
        params = [
            ("point", f"{start_lat},{start_lon}"),
            ("point", f"{dest_lat},{dest_lon}"),
            ("profile", transport_profile),
            ("locale", "fr"),
            ("calc_points", "true"),
            ("points_encoded", "false"),
            ("key", self.api_key)
        ]

        try:
            res = requests.get(self.route_url, params=params, timeout=self.timeout)
            if res.status_code == 400:
                return self._err("Points inaccessibles ou profil de transport indisponible sur cette zone.")
            if res.status_code in (401, 403):
                return self._err("Erreur d'authentification ou quota dépassé pour l'API GraphHopper.")
            if res.status_code == 429:
                return self._err("Trop de requêtes envoyées à l'API de routage (HTTP 429).")
            if res.status_code != 200:
                return self._err(f"Erreur du service de calcul (HTTP {res.status_code}).")

            data = res.json()
            paths = data.get("paths", [])
            if not paths:
                return self._err("Aucun itinéraire routier trouvé entre ces deux points.")

            primary = paths[0]
            raw_pts = primary.get("points", {}).get("coordinates", [])
            if not raw_pts:
                return self._err("Aucun tracé géographique fourni dans la réponse.")

            # Inversion [lon, lat] -> [lat, lon] pour Leaflet
            leaflet_coords = [[pt[1], pt[0]] for pt in raw_pts]
            dist_km = round(float(primary.get("distance", 0.0)) / 1000.0, 2)
            dur_min = round(float(primary.get("time", 0.0)) / 60000.0, 1)

            return {
                "success": True,
                "distance_km": dist_km,
                "duration_min": dur_min,
                "coordinates": leaflet_coords,
                "error_message": None
            }
        except requests.exceptions.Timeout:
            return self._err("Délai de calcul dépassé lors de l'appel GraphHopper.")
        except Exception as exc:
            return self._err(f"Erreur lors du calcul d'itinéraire : {str(exc)}")

    @staticmethod
    def _err(msg: str) -> Dict[str, Any]:
        return {"success": False, "distance_km": 0.0, "duration_min": 0.0, "coordinates": [], "error_message": msg}


# ==============================================================================
# 2. CONSTRUCTEURS D'ÉLÉMENTS UI & MARQUEURS LEAFLET
# ==============================================================================

def create_route_markers(start_data: Optional[Dict], dest_data: Optional[Dict]) -> List[Any]:
    """Construit les éléments Marker et Tooltips Leaflet pour le départ et l'arrivée."""
    markers = []
    if start_data and "lat" in start_data and "lon" in start_data:
        markers.append(
            dl.Marker(
                position=[start_data["lat"], start_data["lon"]],
                children=[
                    dl.Tooltip("🟢 Départ", permanent=True, direction="top"),
                    dl.Popup(
                        html.Div([
                            html.B("🟢 Point de Départ", style={"color": "#15803d"}),
                            html.Br(),
                            html.Span(start_data.get("name", "")),
                            html.Br(),
                            html.Small(f"[{start_data['lat']:.4f}, {start_data['lon']:.4f}]", style={"color": "#64748b"})
                        ])
                    )
                ]
            )
        )
    if dest_data and "lat" in dest_data and "lon" in dest_data:
        markers.append(
            dl.Marker(
                position=[dest_data["lat"], dest_data["lon"]],
                children=[
                    dl.Tooltip("🔴 Destination", permanent=True, direction="top"),
                    dl.Popup(
                        html.Div([
                            html.B("🔴 Point de Destination", style={"color": "#b91c1c"}),
                            html.Br(),
                            html.Span(dest_data.get("name", "")),
                            html.Br(),
                            html.Small(f"[{dest_data['lat']:.4f}, {dest_data['lon']:.4f}]", style={"color": "#64748b"})
                        ])
                    )
                ]
            )
        )
    return markers


# ==============================================================================
# 3. GESTIONNAIRE D'INTÉGRATION (COMPOSANT ENCAPSULÉ AVEC NAMESPACE)
# ==============================================================================

class DashRoutePlanner:
    """
    Composant d'intégration tout-en-un pour applications Dash existantes.
    Permet de générer l'UI, d'intégrer les calques sur une carte existante et d'enregistrer les callbacks.
    """

    def __init__(
        self,
        prefix: str = "planner",
        engine: Optional[RouteEngine] = None,
        initial_start: Optional[Dict[str, Any]] = None,
        initial_dest: Optional[Dict[str, Any]] = None,
        profiles: Optional[List[Dict[str, str]]] = None
    ):
        self.prefix = prefix
        self.engine = engine or RouteEngine()
        self.initial_start = initial_start or {"lat": -18.8792, "lon": 47.5079, "name": "Antananarivo (Analakely)"}
        self.initial_dest = initial_dest or {"lat": -18.9100, "lon": 47.5238, "name": "Ankadimbahoaka"}
        self.profiles = profiles or [
            {"label": "🚗 Voiture", "value": "car"},
            {"label": "🚲 Vélo", "value": "bike"},
            {"label": "🚶 Piéton", "value": "foot"}
        ]

    # Générateurs d'identifiants
    def id(self, name: str) -> str:
        """Génère un identifiant unique avec le préfixe anti-collision."""
        return f"{self.prefix}-{name}"

    def get_map_layers(self) -> List[Any]:
        """
        Retourne les calques Leaflet à insérer comme 'children' d'un dl.MapContainer existant.
        """
        return [
            dl.LayerGroup(id=self.id("layer-route")),
            dl.LayerGroup(id=self.id("layer-markers"))
        ]

    def create_stores(self) -> html.Div:
        """Stores nécessaires à la synchronisation d'état."""
        return html.Div([
            dcc.Store(id=self.id("store-start"), data=self.initial_start),
            dcc.Store(id=self.id("store-dest"), data=self.initial_dest)
        ])

    def create_controls_panel(self, style: Optional[Dict[str, Any]] = None) -> html.Div:
        """
        Génère le bloc UI de contrôles (recherche textuelle, sélecteur de mode de clic, profils et calcul).
        """
        default_style = {
            "display": "flex",
            "flexDirection": "column",
            "gap": "12px",
            "backgroundColor": "#ffffff",
            "padding": "16px",
            "borderRadius": "8px",
            "border": "1px solid #e2e8f0",
            "boxShadow": "0 1px 3px rgba(0,0,0,0.05)"
        }
        if style:
            default_style.update(style)

        return html.Div(
            style=default_style,
            children=[
                self.create_stores(),
                
                # Mode clic
                html.Div([
                    html.Label("Mode du clic carte :", style={"fontWeight": "600", "fontSize": "13px", "marginBottom": "4px", "display": "block"}),
                    dcc.RadioItems(
                        id=self.id("radio-click-mode"),
                        options=[
                            {"label": " 🟢 Départ", "value": "start"},
                            {"label": " 🔴 Destination", "value": "dest"}
                        ],
                        value="start",
                        inline=True,
                        style={"fontSize": "13px", "display": "flex", "gap": "14px"}
                    )
                ]),

                # Recherche Départ
                html.Div([
                    html.Label("Point de départ :", style={"fontWeight": "600", "fontSize": "13px", "display": "block"}),
                    html.Div(
                        style={"display": "flex", "gap": "6px", "marginTop": "4px"},
                        children=[
                            dcc.Input(
                                id=self.id("input-start"),
                                type="text",
                                value=self.initial_start.get("name", ""),
                                placeholder="Adresse ou coordonnées...",
                                style={"flex": "1", "padding": "6px 10px", "borderRadius": "4px", "border": "1px solid #cbd5e1", "fontSize": "13px"}
                            ),
                            html.Button("Chercher", id=self.id("btn-search-start"), style={"cursor": "pointer", "backgroundColor": "#0ea5e9", "color": "#fff", "border": "none", "borderRadius": "4px", "padding": "6px 12px", "fontSize": "12px"})
                        ]
                    ),
                    html.Div(id=self.id("badge-start-coords"), style={"fontSize": "11px", "color": "#64748b", "marginTop": "4px"})
                ]),

                # Recherche Destination
                html.Div([
                    html.Label("Point d'arrivée :", style={"fontWeight": "600", "fontSize": "13px", "display": "block"}),
                    html.Div(
                        style={"display": "flex", "gap": "6px", "marginTop": "4px"},
                        children=[
                            dcc.Input(
                                id=self.id("input-dest"),
                                type="text",
                                value=self.initial_dest.get("name", ""),
                                placeholder="Adresse ou coordonnées...",
                                style={"flex": "1", "padding": "6px 10px", "borderRadius": "4px", "border": "1px solid #cbd5e1", "fontSize": "13px"}
                            ),
                            html.Button("Chercher", id=self.id("btn-search-dest"), style={"cursor": "pointer", "backgroundColor": "#0ea5e9", "color": "#fff", "border": "none", "borderRadius": "4px", "padding": "6px 12px", "fontSize": "12px"})
                        ]
                    ),
                    html.Div(id=self.id("badge-dest-coords"), style={"fontSize": "11px", "color": "#64748b", "marginTop": "4px"})
                ]),

                # Mode de transport
                html.Div([
                    html.Label("Moyen de transport :", style={"fontWeight": "600", "fontSize": "13px", "display": "block"}),
                    dcc.Dropdown(
                        id=self.id("select-profile"),
                        options=self.profiles,
                        value=self.profiles[0]["value"],
                        clearable=False,
                        style={"marginTop": "4px"}
                    )
                ]),

                # Bouton de calcul
                html.Button(
                    "Calculer l'itinéraire",
                    id=self.id("btn-calculate"),
                    n_clicks=0,
                    style={
                        "backgroundColor": "#2563eb",
                        "color": "#ffffff",
                        "border": "none",
                        "borderRadius": "6px",
                        "padding": "10px",
                        "fontSize": "14px",
                        "fontWeight": "bold",
                        "cursor": "pointer"
                    }
                ),

                # Messages de retour
                html.Div(id=self.id("status-feedback")),
                html.Div(id=self.id("metrics-panel"))
            ]
        )

    def create_map(
        self,
        map_id: Optional[str] = None,
        center: Optional[List[float]] = None,
        zoom: int = 13,
        style: Optional[Dict[str, Any]] = None
    ) -> dl.MapContainer:
        """Génère un composant Leaflet autonome prêt à l'emploi."""
        map_element_id = map_id or self.id("leaflet-map")
        map_style = {"width": "100%", "height": "600px", "borderRadius": "8px", "cursor": "crosshair"}
        if style:
            map_style.update(style)

        return dl.MapContainer(
            id=map_element_id,
            center=center or [self.initial_start["lat"], self.initial_start["lon"]],
            zoom=zoom,
            children=[
                dl.TileLayer(url="https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png", maxZoom=19),
                *self.get_map_layers()
            ],
            style=map_style
        )

    def register_callbacks(self, app: dash.Dash, map_id: Optional[str] = None):
        """
        Enregistre l'ensemble des callbacks sur l'instance `app` Dash.
        Si la carte a un ID personnalisé, fournissez-le via `map_id`.
        """
        map_element_id = map_id or self.id("leaflet-map")

        # ----------------------------------------------------------------------
        # CALLBACK 1 : CLICS CARTE & GÉOCODAGE
        # ----------------------------------------------------------------------
        @app.callback(
            [
                Output(self.id("store-start"), "data"),
                Output(self.id("store-dest"), "data"),
                Output(self.id("input-start"), "value"),
                Output(self.id("input-dest"), "value"),
                Output(self.id("radio-click-mode"), "value"),
                Output(self.id("status-feedback"), "children")
            ],
            [
                Input(self.id("btn-search-start"), "n_clicks"),
                Input(self.id("input-start"), "n_submit"),
                Input(self.id("btn-search-dest"), "n_clicks"),
                Input(self.id("input-dest"), "n_submit"),
                Input(map_element_id, "clickData")
            ],
            [
                State(self.id("input-start"), "value"),
                State(self.id("input-dest"), "value"),
                State(self.id("radio-click-mode"), "value"),
                State(self.id("store-start"), "data"),
                State(self.id("store-dest"), "data")
            ],
            prevent_initial_call=True
        )
        def _handle_locations(b_start, s_start, b_dest, s_dest, click_data, q_start, q_dest, mode, cur_start, cur_dest):
            trigger = dash.ctx.triggered_id

            # Clic Carte
            if trigger == map_element_id:
                lat, lon = self.engine.extract_lat_lon_from_click(click_data)
                if lat is None or lon is None:
                    return dash.no_update, dash.no_update, dash.no_update, dash.no_update, dash.no_update, dash.no_update

                lbl = f"Coord. ({lat:.4f}, {lon:.4f})"
                if mode == "start":
                    new_start = {"lat": lat, "lon": lon, "name": lbl}
                    msg = html.Span("✓ Départ sélectionné sur la carte", style={"color": "#16a34a", "fontSize": "12px", "fontWeight": "bold"})
                    return new_start, cur_dest, lbl, q_dest, "dest", msg
                else:
                    new_dest = {"lat": lat, "lon": lon, "name": lbl}
                    msg = html.Span("✓ Destination sélectionnée sur la carte", style={"color": "#dc2626", "fontSize": "12px", "fontWeight": "bold"})
                    return cur_start, new_dest, q_start, lbl, "dest", msg

            # Recherche Départ
            if trigger in (self.id("btn-search-start"), self.id("input-start")):
                res = self.engine.geocode(q_start)
                if not res["success"]:
                    err = html.Div(f"Départ : {res['error_message']}", style={"color": "#dc2626", "fontSize": "12px"})
                    return dash.no_update, dash.no_update, dash.no_update, dash.no_update, dash.no_update, err
                new_start = {"lat": res["lat"], "lon": res["lon"], "name": res["name"]}
                return new_start, cur_dest, res["name"], q_dest, mode, html.Div()

            # Recherche Destination
            if trigger in (self.id("btn-search-dest"), self.id("input-dest")):
                res = self.engine.geocode(q_dest)
                if not res["success"]:
                    err = html.Div(f"Destination : {res['error_message']}", style={"color": "#dc2626", "fontSize": "12px"})
                    return dash.no_update, dash.no_update, dash.no_update, dash.no_update, dash.no_update, err
                new_dest = {"lat": res["lat"], "lon": res["lon"], "name": res["name"]}
                return cur_start, new_dest, q_start, res["name"], mode, html.Div()

            return dash.no_update, dash.no_update, dash.no_update, dash.no_update, dash.no_update, dash.no_update

        # ----------------------------------------------------------------------
        # CALLBACK 2 : DESSIN DES MARQUEURS
        # ----------------------------------------------------------------------
        @app.callback(
            [
                Output(self.id("layer-markers"), "children"),
                Output(self.id("badge-start-coords"), "children"),
                Output(self.id("badge-dest-coords"), "children")
            ],
            [
                Input(self.id("store-start"), "data"),
                Input(self.id("store-dest"), "data")
            ]
        )
        def _render_markers(start_data, dest_data):
            markers = create_route_markers(start_data, dest_data)
            b_start = f"Lat: {start_data['lat']:.4f}, Lon: {start_data['lon']:.4f}" if start_data else "Non défini"
            b_dest = f"Lat: {dest_data['lat']:.4f}, Lon: {dest_data['lon']:.4f}" if dest_data else "Non défini"
            return markers, b_start, b_dest

        # ----------------------------------------------------------------------
        # CALLBACK 3 : CALCUL D'ITINÉRAIRE & TRACÉ
        # ----------------------------------------------------------------------
        @app.callback(
            [
                Output(self.id("layer-route"), "children"),
                Output(map_element_id, "bounds"),
                Output(self.id("metrics-panel"), "children")
            ],
            [Input(self.id("btn-calculate"), "n_clicks")],
            [
                State(self.id("store-start"), "data"),
                State(self.id("store-dest"), "data"),
                State(self.id("select-profile"), "value")
            ],
            prevent_initial_call=True
        )
        def _execute_route(n_clicks, start_data, dest_data, profile):
            if not n_clicks:
                return dash.no_update, dash.no_update, dash.no_update

            if not start_data or not dest_data:
                err = html.Div("Veuillez définir un départ et une destination.", style={"color": "#dc2626", "fontSize": "13px"})
                return [], dash.no_update, err

            result = self.engine.calculate_route(
                start_lat=start_data["lat"],
                start_lon=start_data["lon"],
                dest_lat=dest_data["lat"],
                dest_lon=dest_data["lon"],
                profile=profile
            )

            if not result["success"]:
                err = html.Div(f"Erreur : {result['error_message']}", style={"color": "#dc2626", "fontSize": "13px", "padding": "8px", "backgroundColor": "#fee2e2", "borderRadius": "4px"})
                return [], dash.no_update, err

            coords = result["coordinates"]
            polyline = dl.Polyline(positions=coords, color="#2563eb", weight=6, opacity=0.85)

            # Calcul du cadrage (bounds)
            all_lats = [pt[0] for pt in coords] + [start_data["lat"], dest_data["lat"]]
            all_lons = [pt[1] for pt in coords] + [start_data["lon"], dest_data["lon"]]
            bounds = [[min(all_lats), min(all_lons)], [max(all_lats), max(all_lons)]]

            metrics = html.Div(
                style={"marginTop": "8px", "padding": "10px", "backgroundColor": "#f0fdf4", "border": "1px solid #bbf7d0", "borderRadius": "6px"},
                children=[
                    html.Div(f"Distance : {result['distance_km']} km", style={"fontWeight": "600", "color": "#166534"}),
                    html.Div(f"Durée estimée : {result['duration_min']} min", style={"color": "#166534"})
                ]
            )

            return [polyline], bounds, metrics


# ==============================================================================
# TEST AUTONOME (Lancement si exécuté directement)
# ==============================================================================
if __name__ == "__main__":
    test_app = dash.Dash(__name__)
    planner = DashRoutePlanner(prefix="demo")

    test_app.layout = html.Div(
        style={"display": "flex", "gap": "20px", "padding": "20px", "fontFamily": "sans-serif"},
        children=[
            html.Div(planner.create_controls_panel(), style={"width": "350px"}),
            html.Div(planner.create_map(), style={"flex": "1"})
        ]
    )
    planner.register_callbacks(test_app)
    print("Test standalone lancé sur http://127.0.0.1:8050")
    test_app.run(debug=True, port=8050)