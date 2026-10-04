"""Script utilitaire d'import CSV historique (usage manuel, une fois)."""

import argparse
import csv
import logging
from datetime import datetime
from pathlib import Path
from database import (
    Base,
    engine,
    SessionLocal,
    User,
    Moto,
    Trip,
    Refuel,
    settings,
)

logger = logging.getLogger("MotoTracker.Import")


def parse_float(val: str) -> float:
    """Nettoie et convertit une chaîne en float (ex: '12,7' -> 12.7, '15 000' -> 15000.0)."""
    if not val:
        return 0.0
    cleaned = (
        val.strip()
        .replace(" ", "")
        .replace("\xa0", "")
        .replace("\u202f", "")
        .replace(",", ".")
    )
    if not cleaned or cleaned == "-":
        return 0.0
    try:
        return float(cleaned)
    except ValueError:
        return 0.0


def parse_date(val: str):
    """Convertit une date JJ/MM/AAAA en objet date Python."""
    return datetime.strptime(val.strip(), "%d/%m/%Y").date()


def get_target_moto(db, preferred_email: str | None = None):
    """
    Récupère en priorité l'utilisateur correspondant à preferred_email
    (défaut: compte démo configuré) et sa moto correspondante.
    """
    target_email = (preferred_email or settings.DEMO_EMAIL).strip().lower()
    # 1. Recherche du compte utilisateur connecté à l'interface
    user = db.query(User).filter(User.email == target_email).first()

    if not user:
        # Repli sur le premier utilisateur existant
        user = db.query(User).first()

    if not user:
        logger.info("Création de l'utilisateur par défaut '%s'...", target_email)
        user = User(
            email=target_email,
            name="Pilote",
            hashed_password="imported_default_password",
        )
        db.add(user)
        db.flush()

    # 2. Recherche de la moto active associée à cet utilisateur
    moto = db.query(Moto).filter(Moto.user_id == user.id, Moto.is_active == True).first()

    if not moto:
        moto = db.query(Moto).filter(Moto.user_id == user.id).first()

    if not moto:
        logger.info("Création de la moto 'Ma Moto' (1234-TAB)...")
        moto = Moto(
            user_id=user.id,
            name="Ma Moto",
            license_plate="1234-TAB",
            initial_odometer=0.0,
            is_active=True,
        )
        db.add(moto)
        db.flush()

    return moto


def import_csv_data(file_name: str = "base.txt", email: str | None = None) -> bool:
    # Résolution portable du chemin du fichier texte
    script_dir = Path(__file__).resolve().parent
    file_path = script_dir / file_name

    # Initialisation des tables SQL si nécessaire
    Base.metadata.create_all(bind=engine)

    if not file_path.exists():
        logger.error("Le fichier '%s' n'a pas été trouvé.", file_path)
        return False

    db = SessionLocal()

    try:
        moto = get_target_moto(db, preferred_email=email)
        logger.info("Cible d'importation: moto '%s' (ID: %s), user ID %s", moto.name, moto.id, moto.user_id)

        # Suppression des anciens enregistrements pour cette moto afin d'éviter les doublons de test
        nb_del_trips = db.query(Trip).filter(Trip.moto_id == moto.id).delete()
        nb_del_refuels = db.query(Refuel).filter(Refuel.moto_id == moto.id).delete()
        logger.info("[PURGE] %s trajets et %s pleins précédents supprimés.", nb_del_trips, nb_del_refuels)

        trips_count = 0
        refuels_count = 0

        with open(file_path, mode="r", encoding="utf-8-sig") as f:
            reader = csv.reader(f, delimiter=";")
            header = next(reader, None)

            if not header:
                logger.error("Le fichier d'import est vide.")
                return False

            # Nettoyage des noms de colonnes
            headers = [h.strip().upper() for h in header]

            idx_date = headers.index("DATE")
            idx_aller = headers.index("ALLER")
            idx_retour = headers.index("RETOUR")
            idx_total = headers.index("TOTAL")
            idx_depart = headers.index("DEPART")
            idx_dest = headers.index("DESTINATION")

            # Détection dynamique de la colonne plein/replein
            idx_plein = next(
                (i for i, h in enumerate(headers) if "PLEIN" in h or "REPLEIN" in h),
                None,
            )

            for line_no, row in enumerate(reader, start=2):
                if not row or not any(row):
                    continue

                try:
                    raw_date = row[idx_date].strip()
                    if not raw_date:
                        continue

                    trip_date = parse_date(raw_date)
                    aller = parse_float(row[idx_aller]) if idx_aller < len(row) else 0.0
                    retour = parse_float(row[idx_retour]) if idx_retour < len(row) else 0.0
                    total = parse_float(row[idx_total]) if idx_total < len(row) else 0.0
                    depart = row[idx_depart].strip() if idx_depart < len(row) else ""
                    destination = row[idx_dest].strip() if idx_dest < len(row) else ""

                    # 1. Insertion du Trajet
                    trip = Trip(
                        moto_id=moto.id,
                        date=trip_date,
                        aller=aller,
                        retour=retour,
                        total=total if total > 0 else (aller + retour),
                        depart=depart,
                        destination=destination,
                    )
                    db.add(trip)
                    trips_count += 1

                    # 2. Insertion du Plein (si montant présent)
                    if idx_plein is not None and idx_plein < len(row):
                        amount = parse_float(row[idx_plein])
                        if amount > 0:
                            liters = round(amount / settings.DEFAULT_FUEL_PRICE_PER_LITER, 2)
                            refuel = Refuel(
                                moto_id=moto.id,
                                date=trip_date,
                                amount=amount,
                                liters=liters,
                                notes=f"Importé depuis {file_path.name}",
                            )
                            db.add(refuel)
                            refuels_count += 1

                except (ValueError, IndexError) as row_err:
                    logger.warning("Ligne %s ignorée (%s)", line_no, row_err)

        db.commit()
        logger.info("Importation réussie: %s trajets, %s pleins.", trips_count, refuels_count)
        return True

    except (OSError, ValueError) as e:
        db.rollback()
        logger.error("Erreur critique lors de l'import: %s", e)
        return False
    finally:
        db.close()


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="[%(levelname)s] %(message)s")
    parser = argparse.ArgumentParser(description="Import historique CSV vers la base MotoTracker.")
    parser.add_argument("file", nargs="?", default="base.txt", help="Fichier CSV à importer (défaut: base.txt)")
    parser.add_argument("--email", default=None, help="Email utilisateur cible (défaut: DEMO_EMAIL)")
    args = parser.parse_args()
    raise SystemExit(0 if import_csv_data(args.file, email=args.email) else 1)