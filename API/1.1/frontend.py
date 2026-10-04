"""
frontend.py
-----------
Couche présentation :
- Définition des styles CSS en ligne.
- Carte Dash-Leaflet interactive avec curseur crosshair.
- Marqueurs différenciés avec Tooltips permanents.
"""

from dash import dcc, html
import dash_leaflet as dl
import backend

# ==============================================================================
# STYLES CSS
# ==============================================================================
STYLE_CONTAINER = {
    "fontFamily": "Segoe UI, Roboto, Helvetica, Arial, sans-serif",
    "backgroundColor": "#f8fafc",
    "minHeight": "100vh",
    "margin": "0",
    "padding": "20px",
    "boxSizing": "border-box"
}

STYLE_HEADER = {
    "backgroundColor": "#ffffff",
    "padding": "16px 24px",
    "borderRadius": "8px",
    "boxShadow": "0 1px 3px rgba(0, 0, 0, 0.08)",
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
    "maxWidth": "440px",
    "display": "flex",
    "flexDirection": "column",
    "gap": "14px"
}

STYLE_MAP_AREA = {
    "flex": "2",
    "minWidth": "460px",
    "minHeight": "680px",
    "backgroundColor": "#ffffff",
    "borderRadius": "8px",
    "boxShadow": "0 1px 3px rgba(0, 0, 0, 0.08)",
    "padding": "8px",
    "display": "flex",
    "flexDirection": "column"
}

STYLE_CARD = {
    "backgroundColor": "#ffffff",
    "borderRadius": "8px",
    "padding": "16px",
    "boxShadow": "0 1px 3px rgba(0, 0, 0, 0.06)",
    "border": "1px solid #e2e8f0"
}

STYLE_LABEL = {
    "display": "block",
    "fontSize": "13px",
    "fontWeight": "600",
    "color": "#334155",
    "marginBottom": "6px"
}

STYLE_SEARCH_ROW = {
    "display": "flex",
    "gap": "8px",
    "marginBottom": "6px"
}

STYLE_INPUT = {
    "flex": "1",
    "padding": "8px 12px",
    "borderRadius": "6px",
    "border": "1px solid #cbd5e1",
    "fontSize": "13px",
    "outline": "none",
    "boxSizing": "border-box"
}

STYLE_BTN_SEARCH = {
    "backgroundColor": "#0ea5e9",
    "color": "#ffffff",
    "border": "none",
    "borderRadius": "6px",
    "padding": "8px 14px",
    "fontSize": "13px",
    "fontWeight": "600",
    "cursor": "pointer"
}

STYLE_BTN_CALCULATE = {
    "width": "100%",
    "backgroundColor": "#2563eb",
    "color": "#ffffff",
    "border": "none",
    "borderRadius": "6px",
    "padding": "12px",
    "fontSize": "15px",
    "fontWeight": "bold",
    "cursor": "pointer",
    "boxShadow": "0 2px 4px rgba(37, 99, 235, 0.25)"
}

STYLE_COORDS_BADGE = {
    "fontSize": "11px",
    "color": "#64748b",
    "backgroundColor": "#f1f5f9",
    "padding": "3px 8px",
    "borderRadius": "4px",
    "display": "inline-block"
}

OSM_TILE_URL = "https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png"
OSM_ATTRIBUTION = '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors'


# ==============================================================================
# CARTE ET MARQUEURS
# ==============================================================================
def create_initial_map():
    """Génère la carte avec le curseur crosshair pour faciliter le ciblage."""
    return dl.MapContainer(
        id="leaflet-map-element",
        center=backend.INITIAL_CENTER,
        zoom=backend.INITIAL_ZOOM,
        children=[
            dl.TileLayer(url=OSM_TILE_URL, attribution=OSM_ATTRIBUTION, maxZoom=19),
            dl.LayerGroup(id="layer-route"),
            dl.LayerGroup(id="layer-markers")
        ],
        style={
            "width": "100%",
            "height": "100%",
            "borderRadius": "6px",
            "cursor": "crosshair"  # Indique visuellement que le clic sélectionne un point
        }
    )


def create_marker_elements(start_data, dest_data):
    """Génère les marqueurs avec Tooltips permanents visibles immédiatement."""
    markers = []
    if start_data and "lat" in start_data and "lon" in start_data:
        markers.append(
            dl.Marker(
                position=[start_data["lat"], start_data["lon"]],
                children=[
                    dl.Tooltip("🟢 Départ", permanent=True, direction="top", className="leaflet-tooltip-own"),
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
                    dl.Tooltip("🔴 Destination", permanent=True, direction="top", className="leaflet-tooltip-own"),
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


def create_error_box(message):
    return html.Div(
        style={"backgroundColor": "#fee2e2", "color": "#991b1b", "padding": "10px 14px", "borderRadius": "6px", "fontSize": "13px", "border": "1px solid #f87171"},
        children=[html.Strong("Erreur : "), html.Span(message)]
    )


def create_success_box(message="Itinéraire calculé avec succès."):
    return html.Div(
        style={"backgroundColor": "#dcfce7", "color": "#166534", "padding": "10px 14px", "borderRadius": "6px", "fontSize": "13px", "border": "1px solid #86efac"},
        children=[html.Strong("Succès : "), html.Span(message)]
    )


def create_metrics_box(dist_km, dur_min):
    return html.Div(
        style=STYLE_CARD,
        children=[
            html.H4("Résultats du parcours", style={"margin": "0 0 10px 0", "fontSize": "14px", "color": "#0f172a"}),
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


# ==============================================================================
# MISE EN PAGE PRINCIPALE
# ==============================================================================
def build_layout():
    return html.Div(
        style=STYLE_CONTAINER,
        children=[
            dcc.Store(id="store-start-point", data=backend.DEFAULT_START),
            dcc.Store(id="store-dest-point", data=backend.DEFAULT_DEST),

            html.Header(
                style=STYLE_HEADER,
                children=[
                    html.H1("Calculateur d'Itinéraire - Madagascar", style={"margin": "0 0 4px 0", "fontSize": "22px", "color": "#0f172a"}),
                    html.P("Sélectionnez par simple clic sur la carte ou recherchez un lieu par son nom", style={"margin": "0", "fontSize": "14px", "color": "#64748b"})
                ]
            ),

            html.Div(
                style=STYLE_LAYOUT,
                children=[
                    html.Div(
                        style=STYLE_SIDEBAR,
                        children=[
                            # Mode Clic Carte
                            html.Div(
                                style=STYLE_CARD,
                                children=[
                                    html.Label("Clic sur la carte définit :", style=STYLE_LABEL),
                                    dcc.RadioItems(
                                        id="radio-click-mode",
                                        options=[
                                            {"label": " 🟢 Le Départ", "value": "start"},
                                            {"label": " 🔴 La Destination", "value": "dest"}
                                        ],
                                        value="start",
                                        inline=True,
                                        style={"fontSize": "13px", "display": "flex", "gap": "15px", "marginBottom": "6px"}
                                    ),
                                    html.Small("Faites un simple clic (sans glisser) pour positionner le repère sélectionné.", style={"color": "#64748b", "fontSize": "11px"})
                                ]
                            ),

                            # Recherche Départ
                            html.Div(
                                style=STYLE_CARD,
                                children=[
                                    html.Label("Point de départ :", style=STYLE_LABEL),
                                    html.Div(
                                        style=STYLE_SEARCH_ROW,
                                        children=[
                                            dcc.Input(id="input-start-search", type="text", placeholder="Ex: Analakely, Ivato...", value=backend.DEFAULT_START["name"], style=STYLE_INPUT),
                                            html.Button("Localiser", id="btn-search-start", style=STYLE_BTN_SEARCH)
                                        ]
                                    ),
                                    html.Span(id="badge-start-coords", style=STYLE_COORDS_BADGE)
                                ]
                            ),

                            # Recherche Destination
                            html.Div(
                                style=STYLE_CARD,
                                children=[
                                    html.Label("Point de destination :", style=STYLE_LABEL),
                                    html.Div(
                                        style=STYLE_SEARCH_ROW,
                                        children=[
                                            dcc.Input(id="input-dest-search", type="text", placeholder="Ex: Ankadimbahoaka...", value=backend.DEFAULT_DEST["name"], style=STYLE_INPUT),
                                            html.Button("Localiser", id="btn-search-dest", style=STYLE_BTN_SEARCH)
                                        ]
                                    ),
                                    html.Span(id="badge-dest-coords", style=STYLE_COORDS_BADGE)
                                ]
                            ),

                            # Profil & Calcul
                            html.Div(
                                style=STYLE_CARD,
                                children=[
                                    html.Label("Moyen de transport :", style=STYLE_LABEL),
                                    dcc.Dropdown(
                                        id="select-profile",
                                        options=backend.AVAILABLE_PROFILES,
                                        value=backend.DEFAULT_PROFILE,
                                        clearable=False,
                                        style={"marginBottom": "14px"}
                                    ),
                                    html.Button("Calculer l'itinéraire", id="btn-calculate", n_clicks=0, style=STYLE_BTN_CALCULATE)
                                ]
                            ),

                            html.Div(id="status-search"),
                            html.Div(id="status-route"),
                            html.Div(id="metrics-container")
                        ]
                    ),

                    # Carte Leaflet
                    html.Div(
                        style=STYLE_MAP_AREA,
                        children=[
                            html.Div(
                                id="map-container",
                                style={"flex": "1", "width": "100%", "height": "100%"},
                                children=create_initial_map()
                            )
                        ]
                    )
                ]
            )
        ]
    )