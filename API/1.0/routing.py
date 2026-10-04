"""
Module métier assurant l'interaction avec le service de calcul d'itinéraire GraphHopper.
Prend en charge la validation des coordonnées, la conversion des systèmes d'axes,
l'interrogation HTTP et la mise en forme des résultats pour Dash Leaflet.
"""

import logging
import requests
import config

logger = logging.getLogger("routing")


def validate_coordinate_pair(lat_val, lon_val, label="point"):
    """
    Vérifie la validité numérique et géographique d'une paire latitude/longitude.

    Retourne:
        tuple: (succès: bool, lat: float|None, lon: float|None, message_erreur: str|None)
    """
    if lat_val is None or lon_val is None:
        return False, None, None, f"Veuillez saisir toutes les coordonnées pour le {label}."

    if isinstance(lat_val, str) and not lat_val.strip():
        return False, None, None, f"Veuillez renseigner la latitude du {label}."
    if isinstance(lon_val, str) and not lon_val.strip():
        return False, None, None, f"Veuillez renseigner la longitude du {label}."

    try:
        lat = float(lat_val)
        lon = float(lon_val)
    except (TypeError, ValueError):
        return False, None, None, f"Les coordonnées du {label} doivent être des nombres valides."

    if not (config.LAT_MIN <= lat <= config.LAT_MAX):
        return False, None, None, f"La latitude du {label} doit être comprise entre -90 et 90."

    if not (config.LON_MIN <= lon <= config.LON_MAX):
        return False, None, None, f"La longitude du {label} doit être comprise entre -180 et 180."

    return True, lat, lon, None


def calculate_route(start_lat, start_lon, dest_lat, dest_lon, profile="car"):
    """
    Envoie une requête de routage à l'API GraphHopper et formate la réponse.

    Conversion d'axes :
    - GraphHopper prend en paramètre d'URL le format 'latitude,longitude'.
    - Avec 'points_encoded=false', GraphHopper retourne la géométrie GeoJSON au format [longitude, latitude].
    - Dash Leaflet requiert des positions au format [latitude, longitude].
    Ce module effectue explicitement l'inversion nécessaire.

    Retourne:
        dict: Contient le statut, les coordonnées converties, distance, durée et erreurs.
    """
    # 1. Vérification de la clé API
    if not config.GRAPHHOPPER_API_KEY:
        logger.error("Tentative d'appel API sans variable GRAPHHOPPER_API_KEY définie.")
        return {
            "success": False,
            "distance_m": 0.0,
            "distance_km": 0.0,
            "duration_s": 0.0,
            "duration_min": 0.0,
            "coordinates": [],
            "start_point": None,
            "dest_point": None,
            "error_message": config.API_KEY_MISSING_HELP
        }

    # 2. Validation des coordonnées de départ
    valid_start, s_lat, s_lon, err_start = validate_coordinate_pair(start_lat, start_lon, "départ")
    if not valid_start:
        return {
            "success": False,
            "distance_m": 0.0,
            "distance_km": 0.0,
            "duration_s": 0.0,
            "duration_min": 0.0,
            "coordinates": [],
            "start_point": None,
            "dest_point": None,
            "error_message": err_start
        }

    # 3. Validation des coordonnées de destination
    valid_dest, d_lat, d_lon, err_dest = validate_coordinate_pair(dest_lat, dest_lon, "destination")
    if not valid_dest:
        return {
            "success": False,
            "distance_m": 0.0,
            "distance_km": 0.0,
            "duration_s": 0.0,
            "duration_min": 0.0,
            "coordinates": [],
            "start_point": None,
            "dest_point": None,
            "error_message": err_dest
        }

    # Profil par défaut si non renseigné
    transport_profile = profile if profile else config.DEFAULT_PROFILE

    # 4. Construction de la requête HTTP
    # Les coordonnées passées en paramètre 'point' suivent l'ordre : latitude,longitude
    params = [
        ("point", f"{s_lat},{s_lon}"),
        ("point", f"{d_lat},{d_lon}"),
        ("profile", transport_profile),
        ("locale", "fr"),
        ("calc_points", "true"),
        ("points_encoded", "false"),
        ("key", config.GRAPHHOPPER_API_KEY)
    ]

    try:
        logger.info(
            "Requête GraphHopper : profil=%s, départ=[%f, %f], destination=[%f, %f]",
            transport_profile, s_lat, s_lon, d_lat, d_lon
        )
        response = requests.get(
            config.GRAPHHOPPER_URL,
            params=params,
            timeout=config.REQUEST_TIMEOUT
        )

        # Gestion explicite des statuts HTTP
        if response.status_code == 400:
            logger.warning("GraphHopper 400: %s", response.text)
            return {
                "success": False,
                "distance_m": 0.0,
                "distance_km": 0.0,
                "duration_s": 0.0,
                "duration_min": 0.0,
                "coordinates": [],
                "start_point": None,
                "dest_point": None,
                "error_message": "Coordonnées inaccessibles ou profil de transport non disponible sur cette zone."
            }

        if response.status_code == 401:
            logger.error("GraphHopper 401: Clé API non valide.")
            return {
                "success": False,
                "distance_m": 0.0,
                "distance_km": 0.0,
                "duration_s": 0.0,
                "duration_min": 0.0,
                "coordinates": [],
                "start_point": None,
                "dest_point": None,
                "error_message": "Erreur 401 : La clé API GraphHopper est invalide ou non autorisée."
            }

        if response.status_code == 403:
            logger.error("GraphHopper 403: Accès interdit.")
            return {
                "success": False,
                "distance_m": 0.0,
                "distance_km": 0.0,
                "duration_s": 0.0,
                "duration_min": 0.0,
                "coordinates": [],
                "start_point": None,
                "dest_point": None,
                "error_message": "Erreur 403 : Accès refusé par le serveur (quota dépassé ou service restreint)."
            }

        if response.status_code == 429:
            logger.warning("GraphHopper 429: Limite de taux atteinte.")
            return {
                "success": False,
                "distance_m": 0.0,
                "distance_km": 0.0,
                "duration_s": 0.0,
                "duration_min": 0.0,
                "coordinates": [],
                "start_point": None,
                "dest_point": None,
                "error_message": "Limite de requêtes GraphHopper atteinte (Erreur 429). Veuillez patienter."
            }

        if response.status_code != 200:
            logger.error("GraphHopper HTTP %d: %s", response.status_code, response.text)
            return {
                "success": False,
                "distance_m": 0.0,
                "distance_km": 0.0,
                "duration_s": 0.0,
                "duration_min": 0.0,
                "coordinates": [],
                "start_point": None,
                "dest_point": None,
                "error_message": f"Erreur de communication avec le serveur (Code HTTP {response.status_code})."
            }

        # Décodage JSON
        data = response.json()

        paths = data.get("paths")
        if not paths or len(paths) == 0:
            return {
                "success": False,
                "distance_m": 0.0,
                "distance_km": 0.0,
                "duration_s": 0.0,
                "duration_min": 0.0,
                "coordinates": [],
                "start_point": None,
                "dest_point": None,
                "error_message": "Aucun itinéraire trouvé."
            }

        primary_path = paths[0]
        points_data = primary_path.get("points")
        if not points_data or "coordinates" not in points_data:
            return {
                "success": False,
                "distance_m": 0.0,
                "distance_km": 0.0,
                "duration_s": 0.0,
                "duration_min": 0.0,
                "coordinates": [],
                "start_point": None,
                "dest_point": None,
                "error_message": "Géométrie du trajet manquante dans la réponse du serveur."
            }

        raw_coordinates = points_data["coordinates"]
        if not raw_coordinates:
            return {
                "success": False,
                "distance_m": 0.0,
                "distance_km": 0.0,
                "duration_s": 0.0,
                "duration_min": 0.0,
                "coordinates": [],
                "start_point": None,
                "dest_point": None,
                "error_message": "Aucun tracé géographique disponible pour ce trajet."
            }

        # Conversion :
        # raw_coordinates contient des éléments GeoJSON : [lon, lat]
        # Dash Leaflet attend des paires : [lat, lon]
        leaflet_coordinates = [[point[1], point[0]] for point in raw_coordinates]

        distance_meters = float(primary_path.get("distance", 0.0))
        distance_kilometers = round(distance_meters / 1000.0, 2)

        time_milliseconds = float(primary_path.get("time", 0.0))
        duration_seconds = time_milliseconds / 1000.0
        duration_minutes = round(duration_seconds / 60.0, 1)

        return {
            "success": True,
            "distance_m": distance_meters,
            "distance_km": distance_kilometers,
            "duration_s": duration_seconds,
            "duration_min": duration_minutes,
            "coordinates": leaflet_coordinates,
            "start_point": {"lat": s_lat, "lon": s_lon},
            "dest_point": {"lat": d_lat, "lon": d_lon},
            "error_message": None
        }

    except requests.exceptions.Timeout:
        logger.error("Délai d'attente dépassé lors de la requête GraphHopper.")
        return {
            "success": False,
            "distance_m": 0.0,
            "distance_km": 0.0,
            "duration_s": 0.0,
            "duration_min": 0.0,
            "coordinates": [],
            "start_point": None,
            "dest_point": None,
            "error_message": "Le délai d'attente vers GraphHopper a expiré (timeout)."
        }

    except requests.exceptions.ConnectionError:
        logger.error("Échec de connexion au réseau / GraphHopper.")
        return {
            "success": False,
            "distance_m": 0.0,
            "distance_km": 0.0,
            "duration_s": 0.0,
            "duration_min": 0.0,
            "coordinates": [],
            "start_point": None,
            "dest_point": None,
            "error_message": "Erreur de connexion à GraphHopper. Vérifiez votre connexion Internet."
        }

    except Exception as exc:
        logger.exception("Erreur imprévue lors de l'exécution du calcul d'itinéraire : %s", exc)
        return {
            "success": False,
            "distance_m": 0.0,
            "distance_km": 0.0,
            "duration_s": 0.0,
            "duration_min": 0.0,
            "coordinates": [],
            "start_point": None,
            "dest_point": None,
            "error_message": "Une erreur technique s'est produite lors du calcul."
        }


# ==============================================================================
# Préparation pour le futur moteur hors ligne (V2) :
# Le fichier madagascar-260925.osm.pbf situé dans config.OSM_PBF_PATH sera
# exploité ultérieurement par un moteur local (ex: instance locale OSRM ou Pyrosm).
# La signature ci-dessous préserve la compatibilité avec l'interface Dash.
# ==============================================================================
def calculate_route_offline(start_lat, start_lon, dest_lat, dest_lon, profile="car"):
    """
    Emplacement prévu pour le futur moteur de routage hors ligne exploitant
    le fichier madagascar-260925.osm.pbf.
    """
    raise NotImplementedError("Le calcul hors ligne sera activé dans une version ultérieure.")