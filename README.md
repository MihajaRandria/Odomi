# Odomi • MotoTracker Pro

Application FastAPI + Jinja2 + Dash/Leaflet pour le suivi moto :
trajets, pleins, entretiens, statistiques et planificateur d'itinéraires.

## Prérequis

- Python 3.11+ (testé 3.13 ; `.python-version` fige 3.13, version supportée par Vercel)
- SQLite (aucun serveur requis)

## Installation

```bash
python -m venv .venv
# Windows PowerShell :
.venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

Raccourci Windows : `.\create.ps1` (venv + dépendances + assets hors-ligne).

## Configuration

Copier le modèle d'environnement puis l'adapter :

```bash
copy .env.example .env
```

Variables principales :

| Variable | Défaut | Rôle |
|---|---|---|
| `SECRET_KEY` | dev-only… | Clé JWT — **obligatoire en production** |
| `DATABASE_URL` | `sqlite:///.../moto_tracker.db` | Emplacement SQLite (dossier persistant en prod) |
| `GRAPHHOPPER_API_KEY` | vide | Routage premium optionnel (repli OSM sinon) |
| `HOST` / `PORT` / `DEBUG` | `0.0.0.0` / `8000` / `false` | Serveur |
| `DEMO_EMAIL` / `DEMO_PASSWORD` | pilote… | Compte démo créé si DB vide |

Le fichier `.env` est ignoré par git : ne jamais committer de secret. Le modèle
`.env.example` documente toutes les variables. Sur Vercel, ces valeurs se
définissent dans les variables d'environnement du projet.

## Lancement

```bash
uvicorn main:app --host 0.0.0.0 --port 8000
# dev avec reload :
uvicorn main:app --reload
# alternatives : python main.py   |   .\launch.ps1 (Windows)
```

- UI : `http://127.0.0.1:8000/`
- Planificateur (Dash) : `http://127.0.0.1:8000/planner/`
- Santé : `http://127.0.0.1:8000/health`

## Tests

```bash
pytest -q
```

La collecte est limitée à `tests/` via `pytest.ini` (`version/` contient des
archives, dont des copies de tests, qui faussaient la découverte).

## Production (Docker / Render / Heroku / VPS)

```bash
uvicorn main:app --host 0.0.0.0 --port $PORT
```

`Procfile` fourni pour les plateformes type Render/Heroku. Points d'attention :

- définir `SECRET_KEY` (≥ 32 caractères) et `DEBUG=false`
- monter un volume persistant pour le fichier SQLite (`DATABASE_URL`)
- `moto_tracker.db` et `.env` ne sont jamais versionnés (voir `.gitignore`)

## Déploiement GitHub

Le dépôt local a été initialisé (branche `main`) :

```bash
git add -A
git commit -m "Version initiale — préparation déploiement"
git remote add origin https://github.com/<compte>/<depot>.git
git push -u origin main
```

Le `.gitignore` exclut ce qui ne doit pas être committé :

- `.env` et `moto_tracker.db*` (secrets et base locale)
- `version/` (archives de versions locales)
- `API/data/` et `*.pbf` (`madagascar-260925.osm.pbf` ≈ 371 Mo, au-delà de la
  limite GitHub de 100 Mo par fichier)
- caches (`__pycache__/`, `.pytest_cache/`, `.venv/`)

À l'inverse, `static/vendor/` (Tailwind, Chart.js, FontAwesome, polices) est
versionné : ces assets sont nécessaires pour que l'interface s'affiche sur
Vercel, où `setup_offline.py` n'est pas exécuté. Régénération locale :
`python setup_offline.py`.

## Déploiement Vercel

Aucun `vercel.json` ni dossier `api/` n'est nécessaire : Vercel détecte le
framework FastAPI depuis `requirements.txt` et charge l'instance `app` de
`main.py` (entrypoints reconnus : `main.py`, `app.py`, `index.py`, `server.py`,
`wsgi.py`, `asgi.py` — à la racine, dans `src/` ou `app/`).

- Le planificateur Dash monté sur `/planner` (WSGI encapsulé via `a2wsgi`) est
  servi par la même fonction serverless.
- `app.mount("/static", StaticFiles(...))` est promu automatiquement au CDN
  Vercel au build.
- `.vercelignore` exclut `version/`, `API/data/`, `tests/`, caches et `.env`
  du déploiement.

Étapes :

1. Importer le dépôt GitHub dans Vercel (framework détecté : *FastAPI*).
2. Définir les variables d'environnement (Project → Settings → Environment
   Variables) : `SECRET_KEY`, `DATABASE_URL`, `DEMO_EMAIL`, `DEMO_PASSWORD`,
   `GRAPHHOPPER_API_KEY` (optionnelle), `DEBUG=false`.
3. Déployer, puis vérifier `/health`, `/login` et `/planner/`.

Les événements `lifespan` (création des tables + compte démo) sont supportés
par le runtime Vercel.

## Base de données et limites de production

- **Local / serveur classique** : SQLite (`moto_tracker.db`, mode WAL), aucun
  service externe requis.
- **Vercel** : le système de fichiers est en lecture seule ; seul `/tmp` est
  inscriptible et **non persistant**. `database.py` redirige automatiquement
  tout `DATABASE_URL` SQLite vers `/tmp` lorsque `VERCEL` est défini.
  L'application démarre et fonctionne, mais **toute donnée écrite (trajets,
  pleins, entretiens) est perdue** à chaque redémarrage/cold start ; la base
  est recréée avec le compte de démonstration.
- **Production durable (recommandé, solution gratuite)** : configurer
  `DATABASE_URL` vers un PostgreSQL gratuit (Neon, Supabase, Aiven…) au format
  `postgresql://utilisateur:motdepasse@hote/base` **et** ajouter
  `psycopg2-binary` aux dépendances (`pip install psycopg2-binary`, puis
  l'ajouter à `requirements.txt`). Le schéma est créé automatiquement au
  démarrage.
- Autres limites serverless : pas de processus de fond ni de scheduler, cookie
  JWT `Secure` en HTTPS, `SECRET_KEY` identique sur toutes les instances.

## Structure

- `main.py` — FastAPI (auth cookie JWT, vues, actions, API odomètre, montage Dash)
- `database.py` — Settings (pydantic-settings), modèles SQLAlchemy, SQLite WAL
- `services.py` — auth, stats, pagination, CRUD métier
- `dash_app.py` / `dash_route_planner.py` — planificateur Dash + Leaflet
- `templates/app.html` + `templates/icons/*.svg` — UI Jinja2 (icônes incluses côté serveur)
- `static/vendor/` — assets front versionnés (Tailwind, Chart.js, FontAwesome)
- `maj base.py` — utilitaire manuel d'import CSV (`python "maj base.py" base.txt`)
- `setup_offline.py` — (re)téléchargement des assets `static/vendor/`
- `tests/` — tests critiques (stats, odomètre, pagination, routing haversine)
- `pytest.ini` — limite la collecte pytest à `tests/`
- `create.ps1` / `launch.ps1` — installation et lancement locaux (Windows)
