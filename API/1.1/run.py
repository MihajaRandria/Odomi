"""
run.py
------
Callbacks réactifs :
- Capture robuste des clics carte via 'clickData'.
- Synchronisation des stores, inputs et marqueurs.
- Recalcul et tracé de l'itinéraire routier.
"""

import logging
import dash
from dash import Input, Output, State, html
import dash_leaflet as dl

import backend
import frontend

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s"
)
logger = logging.getLogger("run")

app = dash.Dash(
    __name__,
    title="Calculateur d'Itinéraire - Madagascar",
    suppress_callback_exceptions=True
)

app.layout = frontend.build_layout()


def _extract_lat_lon_from_click(click_data):
    """
    Extrait les coordonnées [lat, lon] depuis l'événement clickData de Dash-Leaflet.
    Compatible avec toutes les versions de dash-leaflet.
    """
    if not click_data:
        return None, None

    # Format standard dash-leaflet : {"latlng": {"lat": -18.87, "lng": 47.50}}
    if isinstance(click_data, dict):
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


# ==============================================================================
# CALLBACK 1 : GESTION DES CLICS CARTE ET DES RECHERCHES
# ==============================================================================
@app.callback(
    [
        Output("store-start-point", "data"),
        Output("store-dest-point", "data"),
        Output("input-start-search", "value"),
        Output("input-dest-search", "value"),
        Output("radio-click-mode", "value"),
        Output("status-search", "children")
    ],
    [
        Input("btn-search-start", "n_clicks"),
        Input("input-start-search", "n_submit"),
        Input("btn-search-dest", "n_clicks"),
        Input("input-dest-search", "n_submit"),
        Input("leaflet-map-element", "clickData")  # <-- Corrigé : 'clickData' au lieu de 'click_lat_lng'
    ],
    [
        State("input-start-search", "value"),
        State("input-dest-search", "value"),
        State("radio-click-mode", "value"),
        State("store-start-point", "data"),
        State("store-dest-point", "data")
    ],
    prevent_initial_call=True
)
def handle_location_updates(
    btn_start, submit_start,
    btn_dest, submit_dest,
    click_data,
    start_text, dest_text,
    click_mode,
    current_start, current_dest
):
    trigger = dash.ctx.triggered_id

    # Cas A : Clic direct sur la carte
    if trigger == "leaflet-map-element":
        lat, lon = _extract_lat_lon_from_click(click_data)
        if lat is None or lon is None:
            return dash.no_update, dash.no_update, dash.no_update, dash.no_update, dash.no_update, dash.no_update

        label = f"Coord. ({lat:.4f}, {lon:.4f})"

        if click_mode == "start":
            new_start = {"lat": lat, "lon": lon, "name": label}
            msg = html.Div("✓ Point de départ sélectionné sur la carte", style={"color": "#16a34a", "fontSize": "12px", "fontWeight": "600"})
            # Bascule automatiquement le mode de clic vers la destination pour le clic suivant
            return new_start, current_dest, label, dest_text, "dest", msg
        else:
            new_dest = {"lat": lat, "lon": lon, "name": label}
            msg = html.Div("✓ Destination sélectionnée sur la carte", style={"color": "#dc2626", "fontSize": "12px", "fontWeight": "600"})
            return current_start, new_dest, start_text, label, "dest", msg

    # Cas B : Recherche textuelle du départ
    if trigger in ("btn-search-start", "input-start-search"):
        result = backend.geocode_location(start_text)
        if not result["success"]:
            return dash.no_update, dash.no_update, dash.no_update, dash.no_update, dash.no_update, frontend.create_error_box(result["error_message"])

        new_start = {"lat": result["lat"], "lon": result["lon"], "name": result["name"]}
        return new_start, current_dest, result["name"], dest_text, click_mode, html.Div()

    # Cas C : Recherche textuelle de la destination
    if trigger in ("btn-search-dest", "input-dest-search"):
        result = backend.geocode_location(dest_text)
        if not result["success"]:
            return dash.no_update, dash.no_update, dash.no_update, dash.no_update, dash.no_update, frontend.create_error_box(result["error_message"])

        new_dest = {"lat": result["lat"], "lon": result["lon"], "name": result["name"]}
        return current_start, new_dest, start_text, result["name"], click_mode, html.Div()

    return dash.no_update, dash.no_update, dash.no_update, dash.no_update, dash.no_update, dash.no_update


# ==============================================================================
# CALLBACK 2 : DESSIN DES MARQUEURS
# ==============================================================================
@app.callback(
    [
        Output("layer-markers", "children"),
        Output("badge-start-coords", "children"),
        Output("badge-dest-coords", "children")
    ],
    [
        Input("store-start-point", "data"),
        Input("store-dest-point", "data")
    ]
)
def update_map_markers(start_data, dest_data):
    markers = frontend.create_marker_elements(start_data, dest_data)
    badge_start = f"Lat: {start_data['lat']:.4f}, Lon: {start_data['lon']:.4f}" if start_data else "Non défini"
    badge_dest = f"Lat: {dest_data['lat']:.4f}, Lon: {dest_data['lon']:.4f}" if dest_data else "Non défini"
    return markers, badge_start, badge_dest


# ==============================================================================
# CALLBACK 3 : CALCUL D'ITINÉRAIRE
# ==============================================================================
@app.callback(
    [
        Output("layer-route", "children"),
        Output("leaflet-map-element", "bounds"),
        Output("status-route", "children"),
        Output("metrics-container", "children")
    ],
    [
        Input("btn-calculate", "n_clicks")
    ],
    [
        State("store-start-point", "data"),
        State("store-dest-point", "data"),
        State("select-profile", "value")
    ],
    prevent_initial_call=True
)
def handle_route_calculation(n_clicks, start_data, dest_data, profile):
    if not n_clicks:
        return dash.no_update, dash.no_update, dash.no_update, dash.no_update

    if not start_data or not dest_data:
        return (
            [],
            dash.no_update,
            frontend.create_error_box("Veuillez définir un départ et une destination."),
            html.Div()
        )

    result = backend.calculate_route(
        start_lat=start_data["lat"],
        start_lon=start_data["lon"],
        dest_lat=dest_data["lat"],
        dest_lon=dest_data["lon"],
        profile=profile
    )

    if not result["success"]:
        return (
            [],
            dash.no_update,
            frontend.create_error_box(result.get("error_message", "Erreur lors du calcul.")),
            html.Div()
        )

    route_coords = result["coordinates"]
    dist_km = result["distance_km"]
    dur_min = result["duration_min"]

    polyline = dl.Polyline(positions=route_coords, color="#2563eb", weight=6, opacity=0.85)

    all_lats = [pt[0] for pt in route_coords] + [start_data["lat"], dest_data["lat"]]
    all_lons = [pt[1] for pt in route_coords] + [start_data["lon"], dest_data["lon"]]
    bounds = [[min(all_lats), min(all_lons)], [max(all_lats), max(all_lons)]]

    return (
        [polyline],
        bounds,
        frontend.create_success_box(),
        frontend.create_metrics_box(dist_km, dur_min)
    )


# ==============================================================================
# DÉMARRAGE
# ==============================================================================
if __name__ == "__main__":
    logger.info("Application prête sur http://%s:%s", backend.SERVER_HOST, backend.SERVER_PORT)
    app.run(
        host=backend.SERVER_HOST,
        port=backend.SERVER_PORT,
        debug=backend.DEBUG_MODE
    )