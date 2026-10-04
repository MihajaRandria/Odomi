"""
Module de configuration générale de l'application.
Centralise la gestion des clés API, les chemins d'accès locaux,
les coordonnées initiales de Madagascar et les paramètres réseau.
"""

import os
from pathlib import Path

# Chemins absolus du projet
BASE_DIR = Path(__file__).resolve().parent
DATA_DIR = BASE_DIR / "data"

# Fichier OSM PBF réservé pour la future intégration d'un moteur de routage hors ligne
OSM_PBF_PATH = DATA_DIR / "madagascar-260925.osm.pbf"

# Récupération sécurisée de la clé API depuis la variable d'environnement Windows
GRAPHHOPPER_API_KEY = os.environ.get("GRAPHHOPPER_API_KEY", "").strip()

# URL de l'API GraphHopper (Routing API v1)
GRAPHHOPPER_URL = "https://graphhopper.com/api/1/route"

# Profils de déplacement supportés
DEFAULT_PROFILE = "car"
AVAILABLE_PROFILES = [
    {"label": "Voiture (car)", "value": "car"},
    {"label": "Vélo (bike)", "value": "bike"},
    {"label": "Piéton (foot)", "value": "foot"}
]

# Coordonnées géographiques centrales initiales (Antananarivo, Madagascar)
INITIAL_CENTER = [-18.8792, 47.5079]
INITIAL_ZOOM = 13

# Valeurs de coordonnées par défaut au lancement
DEFAULT_START_LAT = -18.8792
DEFAULT_START_LON = 47.5079
DEFAULT_DEST_LAT = -18.9100
DEFAULT_DEST_LON = 47.5238

# Limites géographiques WGS84
LAT_MIN, LAT_MAX = -90.0, 90.0
LON_MIN, LON_MAX = -180.0, 180.0

# Paramètres réseau
REQUEST_TIMEOUT = 12  # Durée maximale en secondes d'attente HTTP

# Paramètres du serveur Dash
SERVER_HOST = "127.0.0.1"
SERVER_PORT = 8050
DEBUG_MODE = False

# Message explicatif en cas d'absence de la clé d'environnement
API_KEY_MISSING_HELP = (
    "La clé GraphHopper est absente.\n"
    "Pour la configurer sous Windows, ouvrez une invite de commandes (cmd) et exécutez :\n"
    '    setx GRAPHHOPPER_API_KEY "VOTRE_CLE_API"\n'
    "Redémarrez ensuite le terminal avant de relancer l'application."
)