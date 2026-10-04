from pathlib import Path
import sys

# 1. CONFIGURATION
OUTPUT_DIR = Path(r"F:\Dossier\Script\Moto\templates\icons")

# 2. TEMPLATE SVG COMMUN (Garantit stroke="currentColor" et fill="none" sur tous les tracés)
SVG_TEMPLATE = (
    '<svg xmlns="http://www.w3.org/2000/svg" '
    'viewBox="0 0 24 24" '
    'fill="none" '
    'stroke="currentColor" '
    'stroke-width="2" '
    'stroke-linecap="round" '
    'stroke-linejoin="round">\n'
    "{content}\n"
    "</svg>\n"
)

# 3. DÉFINITIONS GRAPHIQUES DES ICÔNES (Tracés homogènes sur grille 24x24)
ICONS = {
    # --- MOTO & NAVIGATION EXISTANTS ---
    # 1. Moto
    "motorcycle.svg": (
        '  <circle cx="5" cy="16" r="3" />\n'
        '  <circle cx="19" cy="16" r="3" />\n'
        '  <path d="M5 16l4-5h4l3-3h2" />\n'
        '  <path d="M14 6h3" />\n'
        '  <path d="M16 6l3 10" />\n'
        '  <path d="M9 16h5l2-5" />'
    ),
    # 2. Tableau de bord
    "dashboard.svg": (
        '  <path d="M4.5 17a8.5 8.5 0 1 1 15 0" />\n'
        '  <path d="M12 13l4-4" />\n'
        '  <circle cx="12" cy="13" r="1.5" />\n'
        '  <path d="M4 19h16" />'
    ),
    # 3. Compteur kilométrique
    "odometer.svg": (
        '  <rect x="2" y="5" width="20" height="14" rx="2" />\n'
        '  <rect x="5" y="8" width="14" height="8" rx="1" />\n'
        '  <line x1="8.5" y1="8" x2="8.5" y2="16" />\n'
        '  <line x1="12" y1="8" x2="12" y2="16" />\n'
        '  <line x1="15.5" y1="8" x2="15.5" y2="16" />'
    ),
    # 4. Trajet
    "route.svg": (
        '  <circle cx="6" cy="18" r="2" />\n'
        '  <path d="M8 18h3a3 3 0 0 0 3-3V9a3 3 0 0 1 3-3h1" />\n'
        '  <path d="M18 2a3 3 0 0 1 3 3c0 2-3 5-3 5s-3-3-3-5a3 3 0 0 1 3-3z" />\n'
        '  <circle cx="18" cy="5" r="1" />'
    ),
    # 5. Position GPS
    "gps.svg": (
        '  <circle cx="12" cy="12" r="7" />\n'
        '  <circle cx="12" cy="12" r="2" />\n'
        '  <line x1="12" y1="2" x2="12" y2="5" />\n'
        '  <line x1="12" y1="19" x2="12" y2="22" />\n'
        '  <line x1="2" y1="12" x2="5" y2="12" />\n'
        '  <line x1="19" y1="12" x2="22" y2="12" />'
    ),
    # 6. Carte
    "map.svg": (
        '  <polygon points="3 6 9 3 15 6 21 3 21 18 15 21 9 18 3 21" />\n'
        '  <line x1="9" y1="3" x2="9" y2="18" />\n'
        '  <line x1="15" y1="6" x2="15" y2="21" />'
    ),

    # --- CARBURANT & ENTRETIEN ---
    # 7. Carburant
    "fuel.svg": (
        '  <rect x="6" y="6" width="12" height="15" rx="2" />\n'
        '  <path d="M9 6V3h6v3" />\n'
        '  <line x1="9" y1="9" x2="15" y2="18" />\n'
        '  <line x1="15" y1="9" x2="9" y2="18" />'
    ),
    # 8. Station-service
    "fuel-station.svg": (
        '  <rect x="3" y="4" width="10" height="17" rx="2" />\n'
        '  <rect x="6" y="7" width="4" height="3" rx="0.5" />\n'
        '  <path d="M13 10h2a2 2 0 0 1 2 2v5a1.5 1.5 0 0 0 3 0v-7.5l-2-2" />\n'
        '  <line x1="2" y1="21" x2="14" y2="21" />'
    ),
    # 9. Consommation
    "consumption.svg": (
        '  <path d="M12 2.5c-3.8 4.2-7 8.2-7 12a7 7 0 0 0 14 0c0-3.8-3.2-7.8-7-12z" />\n'
        '  <path d="M9 15l2-2 2 2 3-4" />\n'
        '  <path d="M14 11h2v2" />'
    ),
    # 10. Portefeuille / Coût
    "wallet.svg": (
        '  <path d="M20 7V5a2 2 0 0 0-2-2H4a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h14a2 2 0 0 0 2-2v-2" />\n'
        '  <path d="M22 10H14a2 2 0 0 0-2 2v2a2 2 0 0 0 2 2h8v-6z" />\n'
        '  <circle cx="16" cy="13" r="1" />'
    ),
    # 11. Entretien
    "maintenance.svg": (
        '  <path d="M14.7 6.3a1 1 0 0 0 0 1.4l1.6 1.6a1 1 0 0 0 1.4 0l3.77-3.77'
        'a6 6 0 0 1-7.94 7.94l-6.91 6.91a2.12 2.12 0 0 1-3-3l6.91-6.91'
        'a6 6 0 0 1 7.94-7.94l-3.77 3.77z" />'
    ),
    # 12. Huile moteur
    "oil.svg": (
        '  <path d="M7 21h10a2 2 0 0 0 2-2V9l-4-5H9L5 9v10a2 2 0 0 0 2 2z" />\n'
        '  <path d="M10 4V2h4v2" />\n'
        '  <path d="M12 11c-1.2 1.5-1.8 2.3-1.8 3.2a1.8 1.8 0 0 0 3.6 0c0-.9-.6-1.7-1.8-3.2z" />\n'
        '  <path d="M19 11h2a1 1 0 0 1 1 1v4a1 1 0 0 1-1 1h-2" />'
    ),
    # 13. Pneu
    "tire.svg": (
        '  <circle cx="12" cy="12" r="9" />\n'
        '  <circle cx="12" cy="12" r="5" />\n'
        '  <circle cx="12" cy="12" r="1.5" />\n'
        '  <line x1="12" y1="3" x2="12" y2="5" />\n'
        '  <line x1="12" y1="19" x2="12" y2="21" />\n'
        '  <line x1="3" y1="12" x2="5" y2="12" />\n'
        '  <line x1="19" y1="12" x2="21" y2="12" />'
    ),
    # 14. Batterie
    "battery.svg": (
        '  <rect x="4" y="6" width="16" height="15" rx="2" />\n'
        '  <line x1="7" y1="3" x2="7" y2="6" />\n'
        '  <line x1="17" y1="3" x2="17" y2="6" />\n'
        '  <line x1="7" y1="10" x2="7" y2="14" />\n'
        '  <line x1="5" y1="12" x2="9" y2="12" />\n'
        '  <line x1="15" y1="12" x2="19" y2="12" />'
    ),
    # 15. Frein
    "brake.svg": (
        '  <circle cx="12" cy="12" r="8.5" />\n'
        '  <circle cx="12" cy="12" r="3.5" />\n'
        '  <line x1="12" y1="6.5" x2="12" y2="7.5" />\n'
        '  <line x1="12" y1="16.5" x2="12" y2="17.5" />\n'
        '  <line x1="6.5" y1="12" x2="7.5" y2="12" />\n'
        '  <line x1="16.5" y1="12" x2="17.5" y2="12" />\n'
        '  <path d="M15 3h4a2 2 0 0 1 2 2v5a2 2 0 0 1-2 2h-1" />'
    ),

    # --- SUIVI & OUTILS ---
    # 16. Historique
    "history.svg": (
        '  <path d="M3 12a9 9 0 1 0 9-9 9.75 9.75 0 0 0-6.74 2.74L3 8" />\n'
        '  <path d="M3 3v5h5" />\n'
        '  <path d="M12 7v5l3 2" />'
    ),
    # 17. Calendrier
    "calendar.svg": (
        '  <rect x="3" y="4" width="18" height="18" rx="2" />\n'
        '  <line x1="16" y1="2" x2="16" y2="6" />\n'
        '  <line x1="8" y1="2" x2="8" y2="6" />\n'
        '  <line x1="3" y1="10" x2="21" y2="10" />\n'
        '  <line x1="8" y1="14" x2="8.01" y2="14" />\n'
        '  <line x1="12" y1="14" x2="12.01" y2="14" />\n'
        '  <line x1="16" y1="14" x2="16.01" y2="14" />\n'
        '  <line x1="8" y1="18" x2="8.01" y2="18" />\n'
        '  <line x1="12" y1="18" x2="12.01" y2="18" />\n'
        '  <line x1="16" y1="18" x2="16.01" y2="18" />'
    ),
    # 18. Statistiques
    "statistics.svg": (
        '  <path d="M3 3v18h18" />\n'
        '  <path d="M7 16l4-5 4 4 5-6" />\n'
        '  <path d="M16 9h4v4" />'
    ),
    # 19. Notification
    "notification.svg": (
        '  <path d="M18 8A6 6 0 0 0 6 8c0 7-3 9-3 9h18s-3-2-3-9" />\n'
        '  <path d="M13.73 21a2 2 0 0 1-3.46 0" />'
    ),
    # 20. Paramètres
    "settings.svg": (
        '  <circle cx="12" cy="12" r="3" />\n'
        '  <path d="M19.4 15a1.65 1.65 0 0 0 .33 1.82l.06.06a2 2 0 0 1 0 2.83 '
        '2 2 0 0 1-2.83 0l-.06-.06a1.65 1.65 0 0 0-1.82-.33 1.65 1.65 0 0 0-1 1.51V21'
        'a2 2 0 0 1-2 2 2 2 0 0 1-2-2v-.09A1.65 1.65 0 0 0 9 19.4a1.65 1.65 0 0 0-1.82.33'
        'l-.06.06a2 2 0 0 1-2.83 0 2 2 0 0 1 0-2.83l.06-.06a1.65 1.65 0 0 0 .33-1.82'
        '1.65 1.65 0 0 0-1.51-1H3a2 2 0 0 1-2-2 2 2 0 0 1 2-2h.09A1.65 1.65 0 0 0 4.6 9'
        'a1.65 1.65 0 0 0-.33-1.82l-.06-.06a2 2 0 0 1 0-2.83 2 2 0 0 1 2.83 0l.06.06'
        'a1.65 1.65 0 0 0 1.82.33H9a1.65 1.65 0 0 0 1-1.51V3a2 2 0 0 1 2-2 2 2 0 0 1 2 2'
        'v.09a1.65 1.65 0 0 0 1 1.51 1.65 1.65 0 0 0 1.82-.33l.06-.06a2 2 0 0 1 2.83 0'
        '2 2 0 0 1 0 2.83l-.06.06a1.65 1.65 0 0 0-.33 1.82V9a1.65 1.65 0 0 0 1.51 1H21'
        'a2 2 0 0 1 2 2 2 2 0 0 1-2 2h-.09a1.65 1.65 0 0 0-1.51 1z" />'
    ),

    # --- NOUVELLES ICÔNES (Actions & UI) ---
    # 21. ✏️ Modifier un trajet / Édition
    "edit.svg": (
        '  <path d="M11 4H4a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h14a2 2 0 0 0 2-2v-7" />\n'
        '  <path d="M18.5 2.5a2.121 2.121 0 0 1 3 3L12 15l-4 1 1-4 9.5-9.5z" />'
    ),
    # 22. 🗑️ Supprimer trajet, plein ou entretien
    "trash.svg": (
        '  <polyline points="3 6 5 6 21 6" />\n'
        '  <path d="M19 6v14a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V6m3 0V4a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2" />\n'
        '  <line x1="10" y1="11" x2="10" y2="17" />\n'
        '  <line x1="14" y1="11" x2="14" y2="17" />'
    ),
    # 23. ✍️ Saisie manuelle / Stylo plume
    "pen-tool.svg": (
        '  <path d="M12 19l7-7 3 3-7 7-3-3z" />\n'
        '  <path d="M18 13l-1.5-7.5L2 2l3.5 14.5L13 18l5-5z" />\n'
        '  <path d="M2 2l7.586 7.586" />\n'
        '  <circle cx="11" cy="11" r="2" />'
    ),
    # 24. 🌙 Thème Sombre / Lune
    "moon.svg": (
        '  <path d="M21 12.79A9 9 0 1 1 11.21 3 7 7 0 0 0 21 12.79z" />'
    ),
    # 25. ☀️ Thème Clair / Soleil
    "sun.svg": (
        '  <circle cx="12" cy="12" r="5" />\n'
        '  <line x1="12" y1="1" x2="12" y2="3" />\n'
        '  <line x1="12" y1="21" x2="12" y2="23" />\n'
        '  <line x1="4.22" y1="4.22" x2="5.64" y2="5.64" />\n'
        '  <line x1="18.36" y1="18.36" x2="19.78" y2="19.78" />\n'
        '  <line x1="1" y1="12" x2="3" y2="12" />\n'
        '  <line x1="21" y1="12" x2="23" y2="12" />\n'
        '  <line x1="4.22" y1="19.78" x2="5.64" y2="18.36" />\n'
        '  <line x1="18.36" y1="5.64" x2="19.78" y2="4.22" />'
    ),
    # 26. 🔍 Recherche textuelle / Loupe
    "search.svg": (
        '  <circle cx="11" cy="11" r="8" />\n'
        '  <line x1="21" y1="21" x2="16.65" y2="16.65" />'
    ),
    # 27. ⏻ Bouton Déconnexion (Symbole Power)
    "power.svg": (
        '  <path d="M18.36 6.64a9 9 0 1 1-12.73 0" />\n'
        '  <line x1="12" y1="2" x2="12" y2="12" />'
    ),
    # 28. Porte de sortie / Log out (alternative courante pour déconnexion)
    "logout.svg": (
        '  <path d="M9 21H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h4" />\n'
        '  <polyline points="16 17 21 12 16 7" />\n'
        '  <line x1="21" y1="12" x2="9" y2="12" />'
    ),
    # 29. ✓ Checkmark simple
    "check.svg": (
        '  <polyline points="20 6 9 17 4 12" />'
    ),
    # 30. ✓ Toast de confirmation / Succès entouré
    "check-circle.svg": (
        '  <path d="M22 11.08V12a10 10 0 1 1-5.93-9.14" />\n'
        '  <polyline points="22 4 12 14.01 9 11.01" />'
    ),
}


# 4. FONCTION RÉUTILISABLE DE GÉNÉRATION
def build_svg_document(inner_content: str) -> str:
    """Insère le balisage vectoriel dans le gabarit standardisé."""
    return SVG_TEMPLATE.format(content=inner_content)


# 5. PROCÉDURE PRINCIPALE D'ÉCRITURE ET VALIDATION
def main() -> None:
    print(f"[*] Dossier de destination : {OUTPUT_DIR}")

    # Création récursive du dossier si nécessaire
    try:
        OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    except OSError as err:
        sys.exit(f"[!] Échec de la création du dossier {OUTPUT_DIR} : {err}")

    generated_files = []

    # Génération et écriture des fichiers
    for filename, vector_data in ICONS.items():
        file_path = OUTPUT_DIR / filename
        svg_content = build_svg_document(vector_data)

        try:
            file_path.write_text(svg_content, encoding="utf-8")
            generated_files.append(file_path)
            print(f"  [+] Créé : {filename}")
        except OSError as err:
            print(f"  [!] Erreur lors de l'écriture de {filename} : {err}", file=sys.stderr)

    # 6. VALIDATION DE CONFORMITÉ
    print("\n[*] Vérification de la conformité du pack...")
    errors_detected = 0

    if len(generated_files) != len(ICONS):
        print(f"  [!] Anomalie : {len(generated_files)}/{len(ICONS)} fichiers écrits.")
        errors_detected += 1

    for path in generated_files:
        if not path.is_file():
            print(f"  [!] Fichier manquant : {path.name}")
            errors_detected += 1
            continue

        raw = path.read_text(encoding="utf-8")

        if len(raw.strip()) == 0:
            print(f"  [!] Fichier vide : {path.name}")
            errors_detected += 1

        if "<svg" not in raw or "</svg>" not in raw:
            print(f"  [!] Balise <svg> incomplète : {path.name}")
            errors_detected += 1

        if 'viewBox="0 0 24 24"' not in raw:
            print(f"  [!] Attribut viewBox non conforme : {path.name}")
            errors_detected += 1

        if 'stroke="currentColor"' not in raw:
            print(f"  [!] stroke='currentColor' manquant : {path.name}")
            errors_detected += 1

    # 7. RÉSUMÉ FINAL
    print("\n" + "=" * 50)
    if errors_detected == 0:
        print(f"[OK] Succès : {len(generated_files)} icônes SVG générées et conformes.")
    else:
        print(f"[ALERTE] Terminé avec {errors_detected} anomalie(s) détectée(s).")
    print("=" * 50)


if __name__ == "__main__":
    main()