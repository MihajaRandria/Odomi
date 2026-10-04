"""
Module de construction de l'interface cartographique avec Dash Leaflet.
Gère l'affichage des tuiles OpenStreetMap, des marqueurs avec popups,
du tracé de l'itinéraire (Polyline) et du cadrage automatique (bounds).
"""

import dash_leaflet as dl
from dash import html
import config

# URL des tuiles OpenStreetMap en ligne.
# Pour basculer en mode 100% hors ligne ultérieurement, remplacer cette URL
# par un serveur de tuiles local (ex: http://127.0.0.1:8080/tile/{z}/{x}/{y}.png).
OSM_TILE_URL = "https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png"
OSM_ATTRIBUTION = '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors'


def create_initial_map():
    """
    Construit la carte initiale vierge centrée sur Antananarivo, Madagascar.

    Retourne:
        dl.MapContainer: Conteneur de carte Leaflet prêt à être intégré.
    """
    return dl.MapContainer(
        id="leaflet-map-element",
        center=config.INITIAL_CENTER,
        zoom=config.INITIAL_ZOOM,
        children=[
            dl.TileLayer(
                url=OSM_TILE_URL,
                attribution=OSM_ATTRIBUTION,
                maxZoom=19
            )
        ],
        style={"width": "100%", "height": "100%", "borderRadius": "6px"}
    )


def create_route_map(start_point, dest_point, route_coords):
    """
    Génère la carte enrichie avec le marqueur de départ, le marqueur d'arrivée,
    la polyline du trajet et l'ajustement automatique du zoom (bounds).

    Paramètres:
        start_point (list): [latitude, longitude] du point de départ.
        dest_point (list): [latitude, longitude] de la destination.
        route_coords (list): Liste de points [[latitude, longitude], ...] formatés pour Leaflet.

    Retourne:
        dl.MapContainer: Carte avec l'itinéraire complet tracé.
    """
    # Calcul des limites englobantes pour le cadrage automatique
    all_lats = [pt[0] for pt in route_coords] + [start_point[0], dest_point[0]]
    all_lons = [pt[1] for pt in route_coords] + [start_point[1], dest_point[1]]

    min_lat, max_lat = min(all_lats), max(all_lats)
    min_lon, max_lon = min(all_lons), max(all_lons)

    # Bounding box Leaflet : [[sud, ouest], [nord, est]]
    bounds = [[min_lat, min_lon], [max_lat, max_lon]]

    map_children = [
        # Couche de tuiles
        dl.TileLayer(
            url=OSM_TILE_URL,
            attribution=OSM_ATTRIBUTION,
            maxZoom=19
        ),
        # Ligne de l'itinéraire
        dl.Polyline(
            positions=route_coords,
            color="#2563eb",
            weight=6,
            opacity=0.85
        ),
        # Marqueur Départ
        dl.Marker(
            position=start_point,
            children=[
                dl.Popup(
                    html.Div([
                        html.B("Point de départ", style={"color": "#1e293b"}),
                        html.Br(),
                        html.Span(f"Lat : {start_point[0]:.4f}"),
                        html.Br(),
                        html.Span(f"Lon : {start_point[1]:.4f}")
                    ])
                )
            ]
        ),
        # Marqueur Destination
        dl.Marker(
            position=dest_point,
            children=[
                dl.Popup(
                    html.Div([
                        html.B("Point de destination", style={"color": "#dc2626"}),
                        html.Br(),
                        html.Span(f"Lat : {dest_point[0]:.4f}"),
                        html.Br(),
                        html.Span(f"Lon : {dest_point[1]:.4f}")
                    ])
                )
            ]
        )
    ]

    return dl.MapContainer(
        id="leaflet-map-element",
        bounds=bounds,
        children=map_children,
        style={"width": "100%", "height": "100%", "borderRadius": "6px"}
    )