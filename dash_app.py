"""
dash_app.py
-----------
Application Dash intégrée : Détection automatique des lieux réels, liaison
stricte à l'utilisateur connecté, bascule Départ/Arrivée, support complet
Light/Dark mode et carte 100% claire sans clé API.
"""

from datetime import date
import logging
import time
from flask import request as flask_request
import dash
from dash import dcc, html, Input, Output, State, no_update
import dash_leaflet as dl

from dash_route_planner import RouteEngine, MAP_THEMES
from database import SessionLocal, Trip
from services import get_authenticated_session_from_cookie, parse_date_safe

logger = logging.getLogger("MotoTracker.DashApp")

CLASS_START_ACTIVE = "py-1.5 px-3 rounded-xl text-xs font-bold border transition-all text-white bg-emerald-600 border-emerald-500 shadow-sm"
CLASS_START_INACTIVE = "py-1.5 px-3 rounded-xl text-xs font-semibold border transition-all text-slate-700 dark:text-slate-300 bg-slate-100 dark:bg-slate-900 border-slate-300 dark:border-slate-800 hover:border-slate-400 dark:hover:border-slate-700"

CLASS_DEST_ACTIVE = "py-1.5 px-3 rounded-xl text-xs font-bold border transition-all text-white bg-rose-600 border-rose-500 shadow-sm"
CLASS_DEST_INACTIVE = "py-1.5 px-3 rounded-xl text-xs font-semibold border transition-all text-slate-700 dark:text-slate-300 bg-slate-100 dark:bg-slate-900 border-slate-300 dark:border-slate-800 hover:border-slate-400 dark:hover:border-slate-700"


def create_dash_app(requests_pathname_prefix: str = "/planner/") -> dash.Dash:
    app = dash.Dash(
        __name__,
        requests_pathname_prefix=requests_pathname_prefix,
        meta_tags=[{"name": "viewport", "content": "width=device-width, initial-scale=1.0"}],
    )

    engine = RouteEngine()
    initial_start = {"lat": -18.9333, "lon": 47.4333, "name": "Fenoarivo"}
    initial_dest = {"lat": -18.9550, "lon": 47.4750, "name": "Ambohimangidy"}

    app.layout = html.Div(
        className="w-full h-screen max-h-screen overflow-hidden flex flex-col md:flex-row bg-slate-100 dark:bg-slate-900 text-slate-800 dark:text-slate-100 font-sans p-2 gap-2 select-none transition-colors",
        children=[
            dcc.Store(id="store-start", data=initial_start),
            dcc.Store(id="store-dest", data=initial_dest),
            dcc.Store(id="store-route", data=None),
            dcc.Store(id="store-click-target", data="start"),
            dcc.Store(id="store-save-trigger", data=None),
            html.Div(id="dummy-output", style={"display": "none"}),

            # PANNEAU DE CONTRÔLE GAUCHE
            html.Div(
                className="w-full md:w-80 lg:w-96 flex-shrink-0 flex flex-col justify-between bg-white dark:bg-slate-950 border border-slate-200 dark:border-slate-800 rounded-2xl p-3 shadow-md h-full overflow-hidden transition-colors",
                children=[
                    html.Div(
                        className="space-y-2.5",
                        children=[
                            html.Div([
                                html.Span("CIBLE DU CLIC CARTE :", className="block text-[10px] font-black tracking-wider text-slate-500 dark:text-slate-400 mb-1.5"),
                                html.Div(
                                    className="grid grid-cols-2 gap-2",
                                    children=[
                                        html.Button(
                                            [html.Span("●", className="text-emerald-500 mr-1.5"), "Départ"],
                                            id="pill-target-start",
                                            type="button",
                                            className=CLASS_START_ACTIVE,
                                        ),
                                        html.Button(
                                            [html.Span("●", className="text-rose-500 mr-1.5"), "Arrivée"],
                                            id="pill-target-dest",
                                            type="button",
                                            className=CLASS_DEST_INACTIVE,
                                        ),
                                    ],
                                ),
                            ]),

                            # Départ
                            html.Div([
                                html.Div(
                                    className="flex items-center gap-1.5",
                                    children=[
                                        dcc.Input(
                                            id="input-start",
                                            type="text",
                                            value=initial_start["name"],
                                            placeholder="Lieu de départ...",
                                            className="flex-1 bg-slate-50 dark:bg-slate-900 border border-slate-300 dark:border-slate-700 text-slate-900 dark:text-white placeholder-slate-400 dark:placeholder-slate-500 rounded-xl px-2.5 py-1.5 text-xs focus:outline-none focus:border-brand-500 transition-colors",
                                        ),
                                        html.Button(
                                            "Chercher",
                                            id="btn-search-start",
                                            className="px-2.5 py-1.5 bg-slate-100 dark:bg-slate-800 hover:bg-slate-200 dark:hover:bg-slate-700 text-slate-700 dark:text-slate-200 text-xs font-semibold rounded-xl border border-slate-300 dark:border-slate-700 transition-colors",
                                        ),
                                    ],
                                ),
                                html.Div(id="badge-start-coords", className="text-[10px] text-emerald-600 dark:text-emerald-400 font-mono mt-0.5 truncate pl-1"),
                            ]),

                            # Arrivée
                            html.Div([
                                html.Div(
                                    className="flex items-center gap-1.5",
                                    children=[
                                        dcc.Input(
                                            id="input-dest",
                                            type="text",
                                            value=initial_dest["name"],
                                            placeholder="Lieu de destination...",
                                            className="flex-1 bg-slate-50 dark:bg-slate-900 border border-slate-300 dark:border-slate-700 text-slate-900 dark:text-white placeholder-slate-400 dark:placeholder-slate-500 rounded-xl px-2.5 py-1.5 text-xs focus:outline-none focus:border-brand-500 transition-colors",
                                        ),
                                        html.Button(
                                            "Chercher",
                                            id="btn-search-dest",
                                            className="px-2.5 py-1.5 bg-slate-100 dark:bg-slate-800 hover:bg-slate-200 dark:hover:bg-slate-700 text-slate-700 dark:text-slate-200 text-xs font-semibold rounded-xl border border-slate-300 dark:border-slate-700 transition-colors",
                                        ),
                                    ],
                                ),
                                html.Div(id="badge-dest-coords", className="text-[10px] text-rose-600 dark:text-rose-400 font-mono mt-0.5 truncate pl-1"),
                            ]),

                            # Profil & Calcul
                            html.Div(
                                className="grid grid-cols-5 gap-1.5 items-center",
                                children=[
                                    dcc.Dropdown(
                                        id="select-profile",
                                        options=[
                                            {"label": "🏍️ Moto", "value": "car"},
                                            {"label": "🚲 Vélo", "value": "bike"},
                                            {"label": "🚶 Piéton", "value": "foot"},
                                        ],
                                        value="car",
                                        clearable=False,
                                        className="col-span-2 text-xs",
                                    ),
                                    html.Button(
                                        "⚡ Calculer le tracé",
                                        id="btn-calculate",
                                        className="col-span-3 py-2 bg-gradient-to-r from-orange-600 to-amber-600 hover:from-orange-500 text-white font-bold rounded-xl text-xs shadow-md transition-all cursor-pointer",
                                    ),
                                ],
                            ),

                            html.Div(id="metrics-panel"),
                        ],
                    ),

                    # Enregistrement
                    html.Div(
                        className="pt-2 border-t border-slate-200 dark:border-slate-800/80 space-y-2",
                        children=[
                            html.Div(
                                className="flex items-center justify-between gap-2 text-xs",
                                children=[
                                    dcc.Input(
                                        id="input-trip-date",
                                        type="text",
                                        value=date.today().strftime("%Y-%m-%d"),
                                        className="w-28 bg-slate-50 dark:bg-slate-900 border border-slate-300 dark:border-slate-700 rounded-lg px-2 py-1 text-center font-mono text-xs text-slate-900 dark:text-white focus:outline-none focus:border-brand-500",
                                    ),
                                    dcc.RadioItems(
                                        id="radio-trip-round",
                                        options=[
                                            {"label": " Aller Simple", "value": "single"},
                                            {"label": " Aller-Retour (x2)", "value": "round"},
                                        ],
                                        value="round",
                                        inline=True,
                                        className="flex gap-2 text-[11px] text-slate-700 dark:text-slate-300 font-medium",
                                        inputClassName="accent-orange-500 mr-1",
                                    ),
                                ],
                            ),
                            html.Button(
                                "✓ Enregistrer dans le carnet",
                                id="btn-save-trip",
                                className="w-full py-2.5 bg-emerald-600 hover:bg-emerald-500 text-white font-bold rounded-xl text-xs shadow-lg transition-all flex items-center justify-center gap-1.5 cursor-pointer",
                            ),
                            html.Div(id="save-trip-feedback", className="text-center text-xs min-h-[22px]"),
                        ],
                    ),
                ],
            ),

            # CARTE LEAFLET (Carte claire / Satellite)
            html.Div(
                className="flex-1 h-full relative rounded-2xl overflow-hidden border border-slate-200 dark:border-slate-800 shadow-md",
                children=[
                    html.Div(
                        className="absolute top-3 right-3 z-[1000] bg-white/90 dark:bg-slate-900/90 backdrop-blur border border-slate-200 dark:border-slate-700 rounded-xl p-1 shadow-md",
                        children=[
                            dcc.RadioItems(
                                id="radio-map-theme",
                                options=[
                                    {"label": " Carte", "value": "simple"},
                                    {"label": " Satellite", "value": "satellite"},
                                ],
                                value="simple",
                                inline=True,
                                className="text-xs text-slate-700 dark:text-slate-200 px-2 py-0.5 font-medium flex gap-2.5 items-center",
                                inputClassName="accent-orange-500 mr-1",
                            )
                        ],
                    ),
                    dl.Map(
                        id="leaflet-map",
                        center=[initial_start["lat"], initial_start["lon"]],
                        zoom=13,
                        style={"width": "100%", "height": "100%"},
                        children=[
                            dl.TileLayer(id="tile-layer", url=MAP_THEMES["simple"]["url"], attribution=MAP_THEMES["simple"]["attribution"]),
                            dl.LayerGroup(id="layer-route"),
                            dl.LayerGroup(id="layer-markers"),
                        ],
                    ),
                ],
            ),
        ],
    )

    # CLIENTSIDE CALLBACK : REDIRECTION INSTANTANÉE
    app.clientside_callback(
        """
        function(triggerData) {
            if (triggerData && triggerData.saved) {
                setTimeout(function() {
                    try {
                        window.top.location.href = '/?tab=trajets&msg=trip_added';
                    } catch(e) {
                        try {
                            window.top.postMessage({ type: 'ODOMI_TRIP_RECORDED' }, '*');
                        } catch(err) {}
                    }
                }, 700);
            }
            return window.dash_clientside.no_update;
        }
        """,
        Output("dummy-output", "children"),
        Input("store-save-trigger", "data"),
        prevent_initial_call=True,
    )

    # CALLBACK UNIFIÉ
    @app.callback(
        [
            Output("store-start", "data"),
            Output("store-dest", "data"),
            Output("input-start", "value"),
            Output("input-dest", "value"),
            Output("badge-start-coords", "children"),
            Output("badge-dest-coords", "children"),
            Output("store-click-target", "data"),
            Output("pill-target-start", "className"),
            Output("pill-target-dest", "className"),
        ],
        [
            Input("pill-target-start", "n_clicks"),
            Input("pill-target-dest", "n_clicks"),
            Input("leaflet-map", "clickData"),
            Input("btn-search-start", "n_clicks"),
            Input("btn-search-dest", "n_clicks"),
        ],
        [
            State("store-click-target", "data"),
            State("input-start", "value"),
            State("input-dest", "value"),
            State("store-start", "data"),
            State("store-dest", "data"),
        ],
    )
    def _handle_points_and_targets(n_start_pill, n_dest_pill, click_data, n_s_search, n_d_search, cur_target, in_s, in_d, cur_s, cur_d):
        cur_s = cur_s or initial_start
        cur_d = cur_d or initial_dest
        target = cur_target or "start"
        trig = dash.ctx.triggered_id

        if trig == "pill-target-start":
            target = "start"

        elif trig == "pill-target-dest":
            target = "dest"

        elif trig == "leaflet-map" and click_data:
            lat, lon = engine.extract_lat_lon(click_data)
            if lat is not None and lon is not None:
                resolved_name = engine.reverse_geocode(lat, lon)
                if target == "start":
                    cur_s = {"lat": lat, "lon": lon, "name": resolved_name}
                    target = "dest"
                else:
                    cur_d = {"lat": lat, "lon": lon, "name": resolved_name}

        elif trig == "btn-search-start" and in_s:
            res = engine.geocode(in_s)
            if res.get("success"):
                cur_s = {"lat": res["lat"], "lon": res["lon"], "name": res["name"]}

        elif trig == "btn-search-dest" and in_d:
            res = engine.geocode(in_d)
            if res.get("success"):
                cur_d = {"lat": res["lat"], "lon": res["lon"], "name": res["name"]}

        start_class = CLASS_START_ACTIVE if target == "start" else CLASS_START_INACTIVE
        dest_class = CLASS_DEST_ACTIVE if target == "dest" else CLASS_DEST_INACTIVE

        s_badge = f"{cur_s['lat']:.4f}, {cur_s['lon']:.4f}"
        d_badge = f"{cur_d['lat']:.4f}, {cur_d['lon']:.4f}"

        return cur_s, cur_d, cur_s.get("name", ""), cur_d.get("name", ""), s_badge, d_badge, target, start_class, dest_class

    # CALCUL ITINÉRAIRE
    @app.callback(
        [
            Output("store-route", "data"),
            Output("leaflet-map", "bounds"),
            Output("metrics-panel", "children"),
        ],
        Input("btn-calculate", "n_clicks"),
        [
            State("store-start", "data"),
            State("store-dest", "data"),
            State("select-profile", "value"),
        ],
        prevent_initial_call=True,
    )
    def _calc_route(n_clicks, start_data, dest_data, profile):
        if not start_data or not dest_data:
            return None, no_update, html.Div("Veuillez définir départ et arrivée.", className="text-xs text-rose-500 dark:text-rose-400 mt-2")

        res = engine.calculate_route(
            start_lat=start_data["lat"],
            start_lon=start_data["lon"],
            dest_lat=dest_data["lat"],
            dest_lon=dest_data["lon"],
            profile=profile or "car",
        )

        if not res.get("success"):
            return None, no_update, html.Div(res.get("error_message"), className="text-xs text-rose-600 dark:text-rose-400 p-2 bg-rose-50 dark:bg-rose-950/40 rounded-xl mt-1")

        km = res["distance_km"]
        mins = res["duration_min"]
        coords = res.get("coordinates", [])

        bounds = no_update
        if coords:
            lats = [pt[0] for pt in coords]
            lons = [pt[1] for pt in coords]
            bounds = [[min(lats), min(lons)], [max(lats), max(lons)]]

        metrics = html.Div(
            className="grid grid-cols-2 gap-2 mt-2 p-2 bg-slate-50 dark:bg-slate-900 border border-slate-200 dark:border-slate-800 rounded-xl text-center",
            children=[
                html.Div([
                    html.Span("Distance aller", className="block text-[10px] text-slate-500 dark:text-slate-400"),
                    html.Span(f"{km} km", className="text-sm font-black text-brand-600 dark:text-brand-400 font-mono"),
                ]),
                html.Div([
                    html.Span("Durée estimée", className="block text-[10px] text-slate-500 dark:text-slate-400"),
                    html.Span(f"{int(mins)} min", className="text-sm font-black text-slate-800 dark:text-white font-mono"),
                ]),
            ],
        )
        return res, bounds, metrics

    # TRACÉ
    @app.callback(
        [Output("layer-markers", "children"), Output("layer-route", "children")],
        [Input("store-start", "data"), Input("store-dest", "data"), Input("store-route", "data")],
    )
    def _render_map(s, d, r):
        markers = []
        if s and "lat" in s:
            markers.append(dl.Marker(position=[s["lat"], s["lon"]], children=[dl.Tooltip(f"🟢 {s.get('name', 'Départ')}", permanent=True, direction="top")]))
        if d and "lat" in d:
            markers.append(dl.Marker(position=[d["lat"], d["lon"]], children=[dl.Tooltip(f"🔴 {d.get('name', 'Arrivée')}", permanent=True, direction="top")]))

        routes = []
        if r and r.get("success") and r.get("coordinates"):
            routes.append(dl.Polyline(positions=r["coordinates"], color="#f97316", weight=5, opacity=0.9))

        return markers, routes

    # THÈME CARTE (Carte claire ou Satellite)
    @app.callback(
        [Output("tile-layer", "url"), Output("tile-layer", "attribution")],
        Input("radio-map-theme", "value"),
    )
    def _switch_tiles(theme):
        cfg = MAP_THEMES.get(theme, MAP_THEMES["simple"])
        return cfg["url"], cfg["attribution"]

    # ENREGISTREMENT
    @app.callback(
        [
            Output("save-trip-feedback", "children"),
            Output("store-save-trigger", "data"),
        ],
        Input("btn-save-trip", "n_clicks"),
        [
            State("store-route", "data"),
            State("store-start", "data"),
            State("store-dest", "data"),
            State("input-trip-date", "value"),
            State("radio-trip-round", "value"),
        ],
        prevent_initial_call=True,
    )
    def _save_trip(n_clicks, route_data, s_data, d_data, trip_date, round_mode):
        if not route_data or not route_data.get("success"):
            return html.Span("Calculez d'abord un itinéraire.", className="text-amber-500 font-bold"), no_update

        dist_one_way = float(route_data.get("distance_km", 0.0))
        is_round = round_mode == "round"
        aller = dist_one_way
        retour = dist_one_way if is_round else 0.0
        total = round(aller + retour, 2)

        cookie_token = flask_request.cookies.get("access_token")

        with SessionLocal() as db:
            _user, active_moto, _err = get_authenticated_session_from_cookie(cookie_token, db)
            if not active_moto:
                logger.warning("Sauvegarde trajet Dash refusée: utilisateur non authentifié.")
                return html.Span("Session expirée. Reconnectez-vous.", className="text-rose-500"), no_update

            t_date = parse_date_safe(trip_date, default=date.today())

            dep_name = (s_data.get("name") or "Départ").strip()
            arr_name = (d_data.get("name") or "Arrivée").strip()

            new_trip = Trip(
                moto_id=active_moto.id,
                date=t_date,
                depart=dep_name,
                destination=arr_name,
                aller=aller,
                retour=retour,
                total=total,
            )
            db.add(new_trip)
            db.commit()

        feedback_content = html.Div(
            className="flex flex-col items-center justify-center gap-0.5",
            children=[
                html.Span(f"✓ Trajet enregistré ({total} km) !", className="text-emerald-600 dark:text-emerald-400 font-bold"),
                html.A(
                    "Affichage en cours...",
                    href="/?tab=trajets&msg=trip_added",
                    target="_top",
                    className="text-[10px] text-slate-500 dark:text-slate-400 hover:underline cursor-pointer",
                ),
            ],
        )

        trigger_payload = {"saved": True, "timestamp": time.time()}
        return feedback_content, trigger_payload

    return app