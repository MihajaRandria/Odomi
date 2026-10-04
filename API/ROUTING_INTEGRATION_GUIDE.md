```markdown
# ROUTING_INTEGRATION_GUIDE.md
> **Guide de référence contractuel pour l'intégration de `dash_route_planner.py`**  
> Ce document est conçu pour permettre à un développeur ou à un agent LLM d'intégrer le module de calcul d'itinéraire et de géocodage dans n'importe quelle application Dash existante sans ambiguïté, sans conflit d'IDs et sans rien inventer.

---

## 1. VUE D'ENSEMBLE TECHNIQUE

Le module `dash_route_planner.py` fournit une solution autonome à trois niveaux :
1. **Moteur Métier Pur (`RouteEngine`)** : Routage routier (GraphHopper API), géocodage textuel (GraphHopper avec fallback automatique Nominatim OpenStreetMap), et parsing résilient des clics cartographiques.
2. **Éléments Visuels Réutilisables** : Marqueurs Leaflet (`create_route_markers`) avec tooltips permanents et popups détaillés.
3. **Composant d'Intégration Clé-en-main (`DashRoutePlanner`)** : Gestionnaire encapsulé avec système de préfixage anti-collision (`prefix`), générant les stores, les contrôles UI, les calques Leaflet, et enregistrant l'ensemble des callbacks Dash réactifs.

---

## 2. DÉPENDANCES ET CONFIGURATION SYSTÈME

### 2.1 Paquets Python requis
```bash
pip install dash dash-leaflet requests
```

### 2.2 Variables d'environnement
| Variable | Obligatoire | Description | Comportement par défaut |
|---|---|---|---|
| `GRAPHHOPPER_API_KEY` | **Oui** (pour le routage) | Clé d'API GraphHopper pour le calcul de route. | Si absente, `calculate_route` retourne une erreur explicite dans `error_message`. Le géocodage bascule automatiquement sur Nominatim (gratuit). |

---

## 3. CONTRATS DE DONNÉES STRICTS (SCHÉMAS PYTHON)

### 3.1 Format des Coordonnées
- **Leaflet / UI** : Toujours `[latitude, longitude]` (ex: `[-18.8792, 47.5079]`).
- **GeoJSON natif** : `[longitude, latitude]` (géré et inversé en interne de manière transparente par le moteur).

### 3.2 Données des Stores Dash (`store-start` et `store-dest`)
Les points géographiques stockés dans Dash doivent respecter rigoureusement ce dictionnaire :
```python
{
    "lat": float,       # Ex: -18.8792
    "lon": float,       # Ex: 47.5079
    "name": str         # Ex: "Antananarivo (Analakely)" ou "Coord. (-18.8792, 47.5079)"
}
```

### 3.3 Format de retour de `RouteEngine.geocode(query)`
```python
{
    "success": bool,            # True si un point a été résolu, False sinon
    "lat": Optional[float],     # Latitude décimale
    "lon": Optional[float],     # Longitude décimale
    "name": str,                # Nom normalisé du lieu ou coordonnée
    "error_message": Optional[str] # Message d'erreur explicite en cas d'échec
}
```

### 3.4 Format de retour de `RouteEngine.calculate_route(...)`
```python
{
    "success": bool,                     # True si l'itinéraire est trouvé
    "distance_km": float,                # Distance routière arrondie à 2 décimales
    "duration_min": float,               # Durée de parcours en minutes arrondie à 1 décimale
    "coordinates": List[List[float]],    # Tracé Leaflet: [[lat_1, lon_1], [lat_2, lon_2], ...]
    "error_message": Optional[str]        # None si succès, sinon libellé de l'erreur HTTP/métier
}
```

---

## 4. MATRICE EXHAUSTIVE DES IDENTIFIANTS DU DOM (NAMESPACING)

Tous les identifiants générés dynamiquement par une instance `DashRoutePlanner(prefix="<prefix>")` suivent la règle : `f"{prefix}-{nom_composant}"`.

Si `prefix="planner"`, les IDs générés dans le layout sont :

| Identifiant DOM exact | Type Dash | Rôle technique |
|---|---|---|
| `planner-store-start` | `dcc.Store` | Stocke le dictionnaire du point de départ. |
| `planner-store-dest` | `dcc.Store` | Stocke le dictionnaire de la destination. |
| `planner-layer-route` | `dl.LayerGroup` | Conteneur Leaflet recevant le `dl.Polyline`. |
| `planner-layer-markers` | `dl.LayerGroup` | Conteneur Leaflet recevant les `dl.Marker`. |
| `planner-radio-click-mode` | `dcc.RadioItems` | Valeurs : `"start"` (vert) ou `"dest"` (rouge). |
| `planner-input-start` | `dcc.Input` | Champ texte pour recherche du départ. |
| `planner-btn-search-start` | `html.Button` | Déclencheur du géocodage départ. |
| `planner-badge-start-coords` | `html.Div` | Badge affichant les coordonnées du départ. |
| `planner-input-dest` | `dcc.Input` | Champ texte pour recherche de la destination. |
| `planner-btn-search-dest` | `html.Button` | Déclencheur du géocodage destination. |
| `planner-badge-dest-coords` | `html.Div` | Badge affichant les coordonnées de destination. |
| `planner-select-profile` | `dcc.Dropdown` | Profil sélectionné : `"car"`, `"bike"`, `"foot"`. |
| `planner-btn-calculate` | `html.Button` | Déclencheur du calcul d'itinéraire. |
| `planner-status-feedback` | `html.Div` | Conteneur des alertes et statuts. |
| `planner-metrics-panel` | `html.Div` | Conteneur affichant distance (km) et durée (min). |
| `planner-leaflet-map` | `dl.MapContainer`| ID de la carte générée (si `create_map()` est utilisé). |

---

## 5. SCÉNARIOS D'INTÉGRATION

### SCÉNARIO A : Intégration Clé-en-main Complète
*Cas d'usage : Vous souhaitez intégrer le bloc d'itinéraire et sa carte dans une page existante.*

```python
import os
import dash
from dash import html
from dash_route_planner import DashRoutePlanner

# 1. Initialisation de l'application Dash existante
app = dash.Dash(__name__, suppress_callback_exceptions=True)

# 2. Instanciation avec préfixe unique pour éviter toute collision
planner = DashRoutePlanner(
    prefix="nav",
    initial_start={"lat": -18.8792, "lon": 47.5079, "name": "Analakely"},
    initial_dest={"lat": -18.9100, "lon": 47.5238, "name": "Ankadimbahoaka"}
)

# 3. Injection dans votre arborescence layout existante
app.layout = html.Div(
    style={"padding": "20px", "fontFamily": "sans-serif"},
    children=[
        html.H1("Mon Dashboard Existant"),
        html.Div(
            style={"display": "flex", "gap": "20px", "marginTop": "20px"},
            children=[
                # Bloc latéral de commandes (inputs, boutons, badges)
                html.Div(planner.create_controls_panel(), style={"width": "360px"}),
                # Carte Leaflet prête à l'emploi
                html.Div(planner.create_map(), style={"flex": "1", "minHeight": "600px"})
            ]
        )
    ]
)

# 4. Enregistrement automatique de tous les callbacks
planner.register_callbacks(app)

if __name__ == "__main__":
    app.run(debug=True, port=8050)
```

---

### SCÉNARIO B : Intégration dans un `MapContainer` Leaflet DÉJÀ EXISTANT
*Cas d'usage : Votre interface dispose déjà d'un composant `dl.MapContainer` et vous ne souhaitez pas créer une seconde carte.*

```python
import dash
from dash import html
import dash_leaflet as dl
from dash_route_planner import DashRoutePlanner

app = dash.Dash(__name__, suppress_callback_exceptions=True)

CUSTOM_MAP_ID = "main-gis-map"
planner = DashRoutePlanner(prefix="route_module")

app.layout = html.Div([
    html.Header(html.H2("SIG d'Entreprise")),
    
    # 1. Insertion du panneau de commandes où vous le souhaitez
    html.Div(planner.create_controls_panel(), style={"width": "350px", "marginBottom": "20px"}),

    # 2. Carte existante : injectez get_map_layers() dans la liste des children
    dl.MapContainer(
        id=CUSTOM_MAP_ID,
        center=[-18.8792, 47.5079],
        zoom=12,
        children=[
            dl.TileLayer(url="https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png"),
            # INJECTION DES CALQUES ROUTE ET MARQUEURS (dl.LayerGroup)
            *planner.get_map_layers()
        ],
        style={"width": "100%", "height": "650px", "cursor": "crosshair"}
    )
])

# 3. Enregistrement des callbacks en passant explicitement l'ID de votre carte
planner.register_callbacks(app, map_id=CUSTOM_MAP_ID)

if __name__ == "__main__":
    app.run(debug=True, port=8050)
```

---

### SCÉNARIO C : Intégration Headless (Moteur Pur sans UI imposée)
*Cas d'usage : Votre projet a déjà ses propres formulaires, inputs, tableaux ou boutons et vous voulez uniquement exécuter le calcul ou le géocodage.*

```python
import dash
from dash import Input, Output, State, html
from dash_route_planner import RouteEngine

engine = RouteEngine(
    graphhopper_api_key="VOTRE_CLE_GRAPHHOPPER",
    nominatim_viewbox="43.0,-11.5,50.8,-25.8", # Optionnel (Ex: Bounding Box Madagascar)
    timeout=10
)

app = dash.Dash(__name__)
app.layout = html.Div([
    html.Button("Calculer Trajet Personnalisé", id="btn-run-custom"),
    html.Div(id="out-custom-result")
])

@app.callback(
    Output("out-custom-result", "children"),
    Input("btn-run-custom", "n_clicks"),
    prevent_initial_call=True
)
def compute_custom_route(n_clicks):
    # 1. Géocodage textuel (si nécessaire)
    start_geo = engine.geocode("Analakely, Antananarivo")
    if not start_geo["success"]:
        return f"Erreur départ : {start_geo['error_message']}"

    # 2. Calcul d'itinéraire
    res = engine.calculate_route(
        start_lat=start_geo["lat"],
        start_lon=start_geo["lon"],
        dest_lat=-18.9100,
        dest_lon=47.5238,
        profile="car"
    )

    if not res["success"]:
        return f"Échec routage : {res['error_message']}"

    # 3. Exploitation directe des résultats
    return f"Trajet calculé : {res['distance_km']} km en {res['duration_min']} min. {len(res['coordinates'])} points GPS."
```

---

## 6. GESTION DES CLICS CARTE ET COMPATIBILITÉ

L'extraction des coordonnées d'un clic Leaflet peut varier selon les versions de `dash-leaflet` (`0.1.x` vs `1.x.x`).  
Le moteur intègre une méthode normalisée : `engine.extract_lat_lon_from_click(click_data)`.

Elle gère nativement :
- `{"latlng": {"lat": -18.87, "lng": 47.50}}`
- `{"latlng": [-18.87, 47.50]}`
- `{"lat": -18.87, "lon": 47.50}` ou `{"latitude": -18.87, "longitude": 47.50}`
- Les tuples ou listes `[-18.87, 47.50]`

Si vous écrivez vos propres callbacks de capture de clic, utilisez systématiquement cette méthode :
```python
lat, lon = engine.extract_lat_lon_from_click(click_data)
if lat is None or lon is None:
    return dash.no_update
```

---

## 7. RÈGLES D'OR ET PIÈGES À ÉVITER POUR L'INTÉGRATEUR

1. **`suppress_callback_exceptions=True`** :  
   Toujours instancier l'application Dash avec ce paramètre si vos pages utilisent des layouts dynamiques, des sous-onglets (`dcc.Tabs`) ou Dash Pages.
2. **Ordre des Coordonnées pour Leaflet** :  
   Ne pas ré-inverser les coordonnées issues de `res["coordinates"]`. Elles sont **déjà au format Leaflet `[lat, lon]`**.
3. **Collision d'identifiants** :  
   Si vous intégrez plusieurs modules d'itinéraire sur la même application (ex: onglet A et onglet B), instanciez deux objets `DashRoutePlanner` avec des préfixes distincts (ex: `prefix="planner_tab_a"` et `prefix="planner_tab_b"`).
4. **Curseur de la carte** :  
   Lors de l'utilisation d'une carte existante (Scénario B), assurez-vous d'ajouter `"cursor": "crosshair"` au style de votre `dl.MapContainer` pour indiquer visuellement à l'utilisateur que la carte est cliquable.
```