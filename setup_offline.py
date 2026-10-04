"""Télécharge les assets front-end (CSS, polices, librairies) pour usage hors-ligne.

Usage initial (avec Internet) :
    python setup_offline.py

Les fichiers sont stockés sous ``static/vendor/`` et servis par FastAPI
(``/static/...``). Les requêtes API (``/api/...``, géocodage/routage,
tuiles carte) restent en ligne et ne sont pas modifiées.
"""

import logging
import re
import urllib.error
import urllib.request
from pathlib import Path

logging.basicConfig(level=logging.INFO, format="[%(levelname)s] %(message)s")
logger = logging.getLogger("MotoTracker.OfflineAssets")

BASE_DIR = Path(__file__).resolve().parent
STATIC_DIR = BASE_DIR / "static" / "vendor"
CSS_DIR = STATIC_DIR / "css"
FONTS_DIR = STATIC_DIR / "webfonts"  # ../webfonts requis par all.min.css
GOOGLE_FONTS_DIR = STATIC_DIR / "fonts"
FONTS_CSS = CSS_DIR / "fonts.css"

TAILWIND_URL = "https://cdn.tailwindcss.com"
# Build UMD fige : expose le global ``Chart`` (l'URL generique renvoie du HTML).
CHART_URL = "https://cdn.jsdelivr.net/npm/chart.js@4.4.1/dist/chart.umd.min.js"

FONTAWESOME_CSS_URL = "https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.5.1/css/all.min.css"
FONTAWESOME_BASE = "https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.5.1/"
GOOGLE_FONTS_URL = (
    "https://fonts.googleapis.com/css2"
    "?family=Plus+Jakarta+Sans:wght@400;500;600;700;800"
    "&family=JetBrains+Mono:wght@500;700&display=swap"
)

# Cible -> (URL, taille mini, marqueur). Le marqueur evite de valider une page d'erreur HTML.
VENDOR_FILES = {
    str(STATIC_DIR / "tailwind.js"): (TAILWIND_URL, 50000, b"tailwind"),
    str(STATIC_DIR / "chart.min.js"): (CHART_URL, 100000, b"Chart"),
    str(CSS_DIR / "all.min.css"): (FONTAWESOME_CSS_URL, 50000, b".fa-"),
}

FONTAWESOME_FONTS = {
    str(FONTS_DIR / "fa-solid-900.woff2"): FONTAWESOME_BASE + "webfonts/fa-solid-900.woff2",
    str(FONTS_DIR / "fa-solid-900.ttf"): FONTAWESOME_BASE + "webfonts/fa-solid-900.ttf",
    str(FONTS_DIR / "fa-regular-400.woff2"): FONTAWESOME_BASE + "webfonts/fa-regular-400.woff2",
    str(FONTS_DIR / "fa-regular-400.ttf"): FONTAWESOME_BASE + "webfonts/fa-regular-400.ttf",
    str(FONTS_DIR / "fa-brands-400.woff2"): FONTAWESOME_BASE + "webfonts/fa-brands-400.woff2",
    str(FONTS_DIR / "fa-brands-400.ttf"): FONTAWESOME_BASE + "webfonts/fa-brands-400.ttf",
}

_HEADERS = {
    # UA navigateur moderne : Google Fonts renvoie alors du woff2
    # (avec un UA generique, il renvoie du ttf).
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0 Safari/537.36"
}
_URL_RE = re.compile(rb"url\(\s*['\"]?([^)'\"]+)['\"]?\s*\)", re.IGNORECASE)


def _ensure_dirs() -> None:
    STATIC_DIR.mkdir(parents=True, exist_ok=True)
    CSS_DIR.mkdir(parents=True, exist_ok=True)
    FONTS_DIR.mkdir(parents=True, exist_ok=True)
    GOOGLE_FONTS_DIR.mkdir(parents=True, exist_ok=True)


def _looks_like_html(data: bytes) -> bool:
    head = data.lstrip()[:20].lower()
    return head.startswith(b"<!doctype") or head.startswith(b"<html")


def _is_valid_existing(path: Path, min_size: int, marker=None) -> bool:
    try:
        if not path.is_file() or path.stat().st_size < min_size:
            return False
        if path.suffix in {".js", ".css"}:
            data = path.read_bytes()
            if len(data) < min_size or _looks_like_html(data):
                return False
            if marker and marker not in data:
                return False
        return True
    except OSError:
        return False


def _fetch_bytes(url: str, timeout: int) -> bytes:
    req = urllib.request.Request(url, headers=_HEADERS)
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        try:
            status = resp.getcode()
        except Exception:
            status = 200
        if status != 200:
            raise urllib.error.URLError("HTTP %s pour %s" % (status, url))
        data = resp.read()
    if not data:
        raise urllib.error.URLError("reponse vide pour %s" % url)
    return data


def _atomic_write(path: Path, data: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(path.name + ".tmp")
    try:
        with open(tmp, "wb") as f:
            f.write(data)
        tmp.replace(path)
    finally:
        try:
            if tmp.exists():
                tmp.unlink()
        except OSError:
            pass

def _download_one(path_str: str, url: str, min_size: int, marker, timeout: int) -> bool:
    target = Path(path_str)
    if _is_valid_existing(target, min_size, marker):
        logging.info("Fichier deja pret : %s", target.name)
        return True
    logging.info("Telechargement : %s...", target.name)
    try:
        data = _fetch_bytes(url, timeout=timeout)
        if len(data) < min_size:
            raise urllib.error.URLError("telechargement incomplet (%d octets)" % len(data))
        if target.suffix in {".js", ".css"} and _looks_like_html(data):
            raise urllib.error.URLError("contenu HTML inattendu (page d'erreur ?)")
        if marker and marker not in data:
            raise urllib.error.URLError("contenu inattendu (marqueur absent)")
        _atomic_write(target, data)
        return True
    except (urllib.error.URLError, TimeoutError, OSError) as e:
        logging.warning("Impossible de telecharger %s: %s", url, e)
        return False


def _install_google_fonts(timeout: int) -> bool:
    _ensure_dirs()
    try:
        has_font = any(GOOGLE_FONTS_DIR.glob("*.woff2")) or any(GOOGLE_FONTS_DIR.glob("*.ttf"))
    except OSError:
        has_font = False
    if _is_valid_existing(FONTS_CSS, 1000, b"@font-face") and has_font:
        logging.info("Fichier deja pret : %s", FONTS_CSS.name)
        return True
    logging.info("Telechargement : %s...", FONTS_CSS.name)
    try:
        css = _fetch_bytes(GOOGLE_FONTS_URL, timeout=timeout)
        if _looks_like_html(css) or b"@font-face" not in css:
            raise urllib.error.URLError("CSS Google Fonts inattendu")
        urls = sorted({m.decode("ascii", "ignore") for m in _URL_RE.findall(css)})
        font_urls = [u for u in urls if u.startswith("https://fonts.gstatic.com/")]
        if not font_urls:
            raise urllib.error.URLError("aucune police trouvee")
        local_map = {}
        for wurl in font_urls:
            fname = wurl.split("/")[-1].split("?")[0] or "font.woff2"
            dest = GOOGLE_FONTS_DIR / fname
            ok = _download_one(str(dest), wurl, 1000, None, timeout)
            if not ok:
                raise urllib.error.URLError("police manquante : %s" % fname)
            local_map[wurl] = "../fonts/" + fname
        css_text = css.decode("utf-8", "replace")
        for src, local in local_map.items():
            css_text = css_text.replace(src, local)
        rewritten = css_text.encode("utf-8")
        if b"@font-face" not in rewritten or len(rewritten) < 1000:
            raise urllib.error.URLError("CSS local invalide apres reecriture")
        _atomic_write(FONTS_CSS, rewritten)
        return True
    except (urllib.error.URLError, TimeoutError, OSError) as e:
        logging.warning("Impossible de telecharger les polices Google: %s", e)
        return False


def _install_fontawesome_extra(timeout: int) -> bool:
    css_path = CSS_DIR / "all.min.css"
    try:
        css = css_path.read_bytes()
    except OSError as e:
        logging.warning("CSS FontAwesome illisible : %s", e)
        return False
    ok = True
    seen = set()
    for raw in sorted(set(_URL_RE.findall(css))):
        ref = raw.decode("ascii", "ignore").strip()
        if not ref or ref.startswith("data:"):
            continue
        if "webfonts/" not in ref:
            continue
        fname = ref.split("webfonts/")[-1].split("?")[0].split("#")[0]
        if not fname or "/" in fname or "\\" in fname:
            continue
        if fname in seen:
            continue
        seen.add(fname)
        dest = FONTS_DIR / fname
        if _is_valid_existing(dest, 1000):
            continue
        url = FONTAWESOME_BASE + "webfonts/" + fname
        if not _download_one(str(dest), url, 1000, None, timeout):
            ok = False
    return ok


def install_offline_assets(timeout: int = 15) -> bool:
    logging.info("Verification et installation des assets hors-ligne...")
    _ensure_dirs()
    ok = True
    for path, (url, min_size, marker) in VENDOR_FILES.items():
        if not _download_one(path, url, min_size, marker, timeout):
            ok = False
    for path, url in FONTAWESOME_FONTS.items():
        if not _download_one(path, url, 1000, None, timeout):
            ok = False
    css_ok = _is_valid_existing(CSS_DIR / "all.min.css", 50000, b".fa-")
    if css_ok and not _install_fontawesome_extra(timeout):
        ok = False
    if not _install_google_fonts(timeout):
        ok = False
    if ok:
        logging.info("Assets hors-ligne installes avec succes dans 'static/vendor/' !")
    else:
        logging.warning(
            "Certains assets sont manquants. Executez 'python setup_offline.py' "
            "avec une connexion Internet, puis relancez l'application."
        )
    return ok


if __name__ == "__main__":
    raise SystemExit(0 if install_offline_assets() else 1)
