"""
Point d'entrée principal de l'application Dash de calcul d'itinéraire pour Madagascar.
Fournit une interface utilisateur responsive avec saisie des coordonnées,
choix du profil de transport, affichage des métriques et intégration cartographique Leaflet.
Compatible avec les versions modernes de Dash (app.run).
"""

import logging
import dash
from dash import dcc, html, Input, Output, State

import config
import routing
import map_ui

# Configuration du journal d'événements
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s"
)
logger = logging.getLogger("app")

# Initialisation de l'application Dash
app = dash.Dash(
    __name__,
    title="Calculateur d'Itinéraire - Madagascar",
    suppress_callback_exceptions=True
)

# Styles CSS modulaires en ligne
STYLE_CONTAINER = {
    "fontFamily": "Segoe UI, Roboto, Helvetica, Arial, sans-serif",
    "backgroundColor": "#f1f5f9",
    "minHeight": "100vh",
    "margin": "0",
    "padding": "20px",
    "boxSizing": "border-box"
}

STYLE_HEADER = {
    "backgroundColor": "#ffffff",
    "padding": "16px 24px",
    "borderRadius": "8px",
    "boxShadow": "0 1px 3px rgba(0, 0, 0, 0.1)",
    "marginBottom": "20px"
}

STYLE_LAYOUT = {
    "display": "flex",
    "flexDirection": "row",
    "flexWrap": "wrap",
    "gap": "20px"
}

STYLE_SIDEBAR = {
    "flex": "1",
    "minWidth": "340px",
    "maxWidth": "420px",
    "display": "flex",
    "flexDirection": "column",
    "gap": "16px"
}

STYLE_MAP_AREA = {
    "flex": "2",
    "minWidth": "450px",
    "minHeight": "650px",
    "backgroundColor": "#ffffff",
    "borderRadius": "8px",
    "boxShadow": "0 1px 3px rgba(0, 0, 0, 0.1)",
    "padding": "8px",
    "display": "flex",
    "flexDirection": "column"
}

STYLE_CARD = {
    "backgroundColor": "#ffffff",
    "borderRadius": "8px",
    "padding": "16px",
    "boxShadow": "0 1px 3px rgba(0, 0, 0, 0.08)"
}

STYLE_LABEL = {
    "display": "block",
    "fontSize": "13px",
    "fontWeight": "600",
    "color": "#334155",
    "marginBottom": "4px"
}

STYLE_INPUT = {
    "width": "100%",
    "padding": "8px 10px",
    "borderRadius": "6px",
    "border": "1px solid #cbd5e1",
    "fontSize": "14px",
    "boxSizing": "border-box",
    "marginBottom": "8px"
}

STYLE_BUTTON = {
    "width": "100%",
    "backgroundColor": "#2563eb",
    "color": "#ffffff",
    "border": "none",
    "borderRadius": "6px",
    "padding": "12px",
    "fontSize": "15px",
    "fontWeight": "bold",
    "cursor": "pointer",
    "boxShadow": "0 2px 4px rgba(37, 99, 235, 0.3)"
}

# Structure de la mise en page Dash
app.layout = html.Div(
    style=STYLE_CONTAINER,
    children=[
        # En-tête
        html.Header(
            style=STYLE_HEADER,
            children=[
                html.H1(
                    "Calculateur d'Itinéraire - Madagascar",
                    style={"margin": "0 0 4px 0", "fontSize": "22px", "color": "#0f172a"}
                ),
                html.P(
                    "Calcul d'itinéraire routier via l'API GraphHopper et cartographie dynamique Dash Leaflet",
                    style={"margin": "0", "fontSize": "14px", "color": "#64748b"}
                )
            ]
        ),

        # Corps de l'application
        html.Div(
            style=STYLE_LAYOUT,
            children=[
                # Volet latéral gauche : Formulaire de saisie et métriques
                html.Div(
                    style=STYLE_SIDEBAR,
                    children=[
                        # Bloc Coordonnées de départ
                        html.Div(
                            style=STYLE_CARD,
                            children=[
                                html.H3(
                                    "Point de départ (Antananarivo)",
                                    style={"margin": "0 0 12px 0", "fontSize": "15px", "color": "#1e293b"}
                                ),
                                html.Label("Latitude :", style=STYLE_LABEL),
                                dcc.Input(
                                    id="input-start-lat",
                                    type="number",
                                    value=config.DEFAULT_START_LAT,
                                    step="any",
                                    placeholder="Ex: -18.8792",
                                    style=STYLE_INPUT
                                ),
                                html.Label("Longitude :", style=STYLE_LABEL),
                                dcc.Input(
                                    id="input-start-lon",
                                    type="number",
                                    value=config.DEFAULT_START_LON,
                                    step="any",
                                    placeholder="Ex: 47.5079",
                                    style=STYLE_INPUT
                                ),
                            ]
                        ),

                        # Bloc Coordonnées de destination
                        html.Div(
                            style=STYLE_CARD,
                            children=[
                                html.H3(
                                    "Point de destination",
                                    style={"margin": "0 0 12px 0", "fontSize": "15px", "color": "#1e293b"}
                                ),
                                html.Label("Latitude :", style=STYLE_LABEL),
                                dcc.Input(
                                    id="input-dest-lat",
                                    type="number",
                                    value=config.DEFAULT_DEST_LAT,
                                    step="any",
                                    placeholder="Ex: -18.9100",
                                    style=STYLE_INPUT
                                ),
                                html.Label("Longitude :", style=STYLE_LABEL),
                                dcc.Input(
                                    id="input-dest-lon",
                                    type="number",
                                    value=config.DEFAULT_DEST_LON,
                                    step="any",
                                    placeholder="Ex: 47.5238",
                                    style=STYLE_INPUT
                                ),
                            ]
                        ),

                        # Bloc Profil et Action
                        html.Div(
                            style=STYLE_CARD,
                            children=[
                                html.Label("Profil de déplacement :", style=STYLE_LABEL),
                                dcc.Dropdown(
                                    id="select-profile",
                                    options=config.AVAILABLE_PROFILES,
                                    value=config.DEFAULT_PROFILE,
                                    clearable=False,
                                    style={"marginBottom": "14px"}
                                ),
                                html.Button(
                                    "Calculer l'itinéraire",
                                    id="btn-calculate",
                                    n_clicks=0,
                                    style=STYLE_BUTTON
                                )
                            ]
                        ),

                        # Zone d'affichage des statuts et erreurs
                        html.Div(id="status-container"),

                        # Zone d'affichage des résultats (Distance & Durée)
                        html.Div(id="metrics-container")
                    ]
                ),

                # Volet principal droit : Carte interactive Leaflet
                html.Div(
                    style=STYLE_MAP_AREA,
                    children=[
                        html.Div(
                            id="map-container",
                            style={"flex": "1", "width": "100%", "height": "100%"},
                            children=map_ui.create_initial_map()
                        )
                    ]
                )
            ]
        )
    ]
)


@app.callback(
    [
        Output("map-container", "children"),
        Output("status-container", "children"),
        Output("metrics-container", "children")
    ],
    [
        Input("btn-calculate", "n_clicks")
    ],
    [
        State("input-start-lat", "value"),
        State("input-start-lon", "value"),
        State("input-dest-lat", "value"),
        State("input-dest-lon", "value"),
        State("select-profile", "value")
    ],
    prevent_initial_call=True
)
def handle_route_calculation(n_clicks, start_lat, start_lon, dest_lat, dest_lon, profile):
    """
    Traite la demande de calcul de trajet lors du clic sur le bouton.
    Valide les données, appelle l'API GraphHopper et actualise la carte et les indicateurs.
    """
    if not n_clicks:
        return dash.no_update, dash.no_update, dash.no_update

    # Exécution du calcul d'itinéraire
    result = routing.calculate_route(
        start_lat=start_lat,
        start_lon=start_lon,
        dest_lat=dest_lat,
        dest_lon=dest_lon,
        profile=profile
    )

    # Gestion du cas d'échec
    if not result["success"]:
        error_msg = result.get("error_message", "Une erreur inconnue est survenue.")
        status_box = html.Div(
            style={
                "backgroundColor": "#fee2e2",
                "color": "#991b1b",
                "padding": "12px",
                "borderRadius": "6px",
                "fontSize": "13px",
                "border": "1px solid #f87171"
            },
            children=[
                html.Strong("Erreur : "),
                html.Span(error_msg)
            ]
        )
        return dash.no_update, status_box, html.Div()

    # Succès : Extraction des données
    start_pt = [result["start_point"]["lat"], result["start_point"]["lon"]]
    dest_pt = [result["dest_point"]["lat"], result["dest_point"]["lon"]]
    route_coords = result["coordinates"]
    dist_km = result["distance_km"]
    dur_min = result["duration_min"]

    # Création de la carte avec l'itinéraire
    new_map = map_ui.create_route_map(
        start_point=start_pt,
        dest_point=dest_pt,
        route_coords=route_coords
    )

    # Bloc de statut positif
    status_box = html.Div(
        style={
            "backgroundColor": "#dcfce7",
            "color": "#166534",
            "padding": "12px",
            "borderRadius": "6px",
            "fontSize": "13px",
            "border": "1px solid #86efac"
        },
        children=[
            html.Strong("Succès : "),
            html.Span("Itinéraire calculé avec succès.")
        ]
    )

    # Bloc récapitulatif des métriques
    metrics_box = html.Div(
        style=STYLE_CARD,
        children=[
            html.H4(
                "Informations de parcours",
                style={"margin": "0 0 10px 0", "fontSize": "14px", "color": "#0f172a"}
            ),
            html.Div(
                style={"display": "flex", "justifyContent": "space-between", "marginBottom": "6px"},
                children=[
                    html.Span("Distance totale :", style={"color": "#475569", "fontSize": "13px"}),
                    html.Strong(f"{dist_km} km", style={"color": "#0f172a", "fontSize": "14px"})
                ]
            ),
            html.Div(
                style={"display": "flex", "justifyContent": "space-between"},
                children=[
                    html.Span("Durée estimée :", style={"color": "#475569", "fontSize": "13px"}),
                    html.Strong(f"{dur_min} min", style={"color": "#0f172a", "fontSize": "14px"})
                ]
            )
        ]
    )

    return new_map, status_box, metrics_box


if __name__ == "__main__":
    logger.info("Démarrage de l'application Dash d'itinéraire Madagascar...")
    app.run(
        host=config.SERVER_HOST,
        port=config.SERVER_PORT,
        debug=config.DEBUG_MODE
    )