"""
Récupère les prix des Fan Tokens directement depuis fantokens.com.

Pourquoi fantokens.com et pas l'API "markets" de CoinGecko comme avant :
fantokens.com liste TOUS les tokens officiels Socios (le tableau d'accueil
du site, lui, est rendu en JavaScript et n'est pas scrapable simplement),
alors que la catégorie "fan-token" de CoinGecko en couvre nettement moins.

La bonne nouvelle : chaque token a une page individuelle
    https://www.fantokens.com/fr/trade/<slug>
et CETTE page-là est rendue côté serveur (le prix est déjà dans le HTML
brut, pas besoin d'exécuter du JavaScript) — on peut donc la scraper
normalement avec requests + BeautifulSoup.

Le <slug> correspond quasiment toujours à l'id CoinGecko du token
(ex: "paris-saint-germain-fan-token", "fc-barcelona-fan-token"). On le
devine à partir du nom du club (guess_slug), et pour les clubs où la
déduction automatique échoue (sigles, accents, "de"/"the" qui sautent...),
une correspondance manuelle club -> slug est enregistrée en base (même
mécanisme que l'ancien mapping vers un id CoinGecko, réutilisé tel quel).
"""

import re
import time
import unicodedata
from concurrent.futures import ThreadPoolExecutor, as_completed

import requests
from bs4 import BeautifulSoup

FANTOKENS_TRADE_URL = "https://www.fantokens.com/fr/trade/{slug}"
FX_RATE_URL = "https://api.frankfurter.app/latest"

REQUEST_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml",
    "Accept-Language": "fr-FR,fr;q=0.9",
}

# Seul le "FC" final saute dans le slug fantokens.com/CoinGecko
# ("Manchester City FC" -> "manchester-city-fan-token", "Arsenal FC" ->
# "arsenal-fan-token"). En tête ou au milieu, en revanche, "FC"/"AC"/"AS"/...
# fait PARTIE du slug ("FC Barcelona" -> "fc-barcelona-fan-token", "AC Milan"
# -> "ac-milan-fan-token", "AS Roma" -> "as-roma-fan-token") — donc on ne
# touche qu'au suffixe, jamais au reste du nom. Vérifié à la main sur une
# quinzaine de clubs connus (cf. tests dans le repo / conversation).
_TRAILING_FC_RE = re.compile(r"\s+(FC|F\.C\.)$", re.IGNORECASE)

# Corrections manuelles pour les noms qui ne donnent toujours pas le bon
# slug une fois passés dans guess_slug() (clé = nom exact affiché sur
# socios.com). Liste de départ à corriger/compléter au fil de l'eau depuis
# l'onglet Correspondances de l'appli (bouton "Vérifier" + enregistrement).
MANUAL_SLUG_OVERRIDES = {
    "Atlético de Madrid": "atletico-madrid-fan-token",
    "FC Internazionale Milano": "inter-milan-fan-token",
    "Galatasaray S.K.": "galatasaray-fan-token",
    "İstanbul Başakşehir FK": "istanbul-basaksehir-fan-token",
    "GNK Dinamo Zagreb": "dinamo-zagreb-fan-token",
    "Göztepe S.K.": "goztepe-fan-token",
    "S.C. Internacional": "internacional-fan-token",
    "Levante U.D.": "levante-fan-token",
    "Johor Darul Ta'zim F.C": "johor-darul-tazim-fan-token",
}


def _get_with_retry(url: str, timeout: int = 8, retries: int = 1, params: dict | None = None):
    """GET avec retry. Retourne None sur 404 (page/slug inexistant),
    lève une exception réseau après épuisement des tentatives."""
    last_exc = None
    for attempt in range(retries + 1):
        try:
            r = requests.get(url, headers=REQUEST_HEADERS, timeout=timeout, params=params)
            if r.status_code == 404:
                return None
            if r.status_code == 429:
                time.sleep(2 * (attempt + 1))
                last_exc = ConnectionError("fantokens.com : trop de requêtes (429), réessaie plus tard.")
                continue
            r.raise_for_status()
            return r
        except requests.exceptions.RequestException as e:
            last_exc = e
            time.sleep(1 * (attempt + 1))
    if last_exc:
        raise last_exc
    return None


def guess_slug(club_name: str) -> str:
    """Devine le slug fantokens.com/CoinGecko à partir du nom du club.
    Best effort : marche pour la majorité des clubs, mais certains noms
    (accents rares, sigles non standards) auront besoin d'une correspondance
    manuelle enregistrée via l'onglet Correspondances de l'appli."""
    if club_name in MANUAL_SLUG_OVERRIDES:
        return MANUAL_SLUG_OVERRIDES[club_name]
    name = _TRAILING_FC_RE.sub("", club_name)
    name = unicodedata.normalize("NFKD", name).encode("ascii", "ignore").decode()
    name = re.sub(r"[^a-zA-Z0-9]+", "-", name).strip("-").lower()
    return f"{name}-fan-token"


_PRICE_RE = re.compile(r"\$\s?([\d\s]+[.,]\d+|\d+)")
# Le prix ($X,XX) est immédiatement suivi, sur la page fantokens.com, du
# pourcentage de variation sur 24h (ex: "$0,499241 0,20 % (24h) 34,09 CHZ") :
# on prend directement le PREMIER pourcentage qui suit le prix, sans exiger
# le suffixe "(24h)" — plus robuste à une mise en forme qui varie légèrement
# (majuscule, espace, tournure différente) tant que c'est bien le premier %
# de la page après le prix.
_CHANGE_RE = re.compile(r"([\-\u2212+]?\s?\d+[.,]\d+)\s*%")
# Source BEAUCOUP plus fiable que le texte visible de la page (qui peut être
# injecté par JavaScript et donc absent du HTML brut reçu par `requests`) :
# la balise <meta name="description"> est générée côté serveur pour le SEO,
# donc TOUJOURS présente dans le HTML brut, et contient prix + variation
# dans une phrase fixe, ex (page /fr/trade/...) :
# "Le prix du Fan Token Paris Saint-Germain est aujourd'hui de $0,87259,
#  avec un volume de trading sur 24 heures de $2.27M. Le prix du PSG a
#  varié de 0.61484% au cours des dernières 24 heures."
_META_CHANGE_RE = re.compile(r"varié\s+de\s*([\-\u2212+]?\s?\d+[.,]?\d*)\s*%")


# Sur fantokens.com, la hausse/baisse n'est JAMAIS écrite dans le texte (ni
# dans le texte visible, ni dans la meta description) : elle n'est indiquée
# QUE par la couleur (vert/rouge, classes CSS type Tailwind) de l'élément
# affichant le pourcentage. Sans regarder la classe CSS, impossible de
# distinguer +2% de -2% à partir du texte seul.
_NEGATIVE_CLASS_HINTS = ("red", "danger", "negative", "loss", "down", "decrease", "fall")
_POSITIVE_CLASS_HINTS = ("green", "success", "positive", "gain", "up", "increase", "rise")


def _detect_change_sign(soup) -> bool | None:
    """True si baisse (rouge), False si hausse (vert), None si indétectable
    (dans ce cas on affichera le pourcentage sans signe, comme avant)."""
    node = soup.find(string=re.compile(r"%\s*\(24h\)"))
    if node is None:
        return None
    el = node.parent
    for _ in range(5):
        if el is None:
            break
        classes = " ".join(el.get("class", [])).lower() if el.get("class") else ""
        if any(hint in classes for hint in _NEGATIVE_CLASS_HINTS):
            return True
        if any(hint in classes for hint in _POSITIVE_CLASS_HINTS):
            return False
        el = el.parent
    return None


def _parse_fr_number(raw: str) -> float:
    """'0,486116' ou '1 234,56' -> float. Les pages fantokens.com sont en
    français : virgule décimale, espace comme séparateur de milliers."""
    cleaned = raw.replace("\u2212", "-").replace(" ", "").replace("\xa0", "").replace(",", ".")
    return float(cleaned)


def fetch_fantoken_page(slug: str, timeout: int = 8):
    """Scrape https://www.fantokens.com/fr/trade/<slug>.
    Retourne {"price_usd": float, "change_24h": float|None, "name": str,
    "logo": str|None} ou None si le slug n'existe pas (page 404) ou si le
    prix n'a pas pu être trouvé dans la page.

    Le logo est extrait de la MÊME page (pas de requête en plus) via
    plusieurs stratégies, dans l'ordre :
    1. balise <meta property="og:image"> (image de partage, en général le
       logo/icône du token) — la plus fiable si présente.
    2. la première <img> qui suit le <h1> du titre dans le HTML (logo
       affiché à côté du nom sur la page).
    3. la première <img> dont l'alt contient le nom du club ou le mot
       "logo"/"token".
    À adapter si la structure réelle de fantokens.com diverge (cf. tests
    à faire une fois en prod, cf. onglet Correspondances -> Vérifier)."""
    url = FANTOKENS_TRADE_URL.format(slug=slug)
    r = _get_with_retry(url, timeout=timeout)
    if r is None:
        return None

    soup = BeautifulSoup(r.text, "lxml")
    text = soup.get_text(" ", strip=True)

    price_match = _PRICE_RE.search(text)
    if not price_match:
        return None
    try:
        price_usd = _parse_fr_number(price_match.group(1))
    except ValueError:
        return None

    change_24h = None
    # 1. Balise meta description (SEO, toujours dans le HTML brut serveur —
    #    contrairement au texte visible, qui peut être injecté par JS et donc
    #    absent de ce que `requests` reçoit).
    meta_tag = soup.find("meta", attrs={"name": "description"})
    meta_content = meta_tag.get("content") if meta_tag else None
    if meta_content:
        meta_match = _META_CHANGE_RE.search(meta_content)
        if meta_match:
            try:
                change_24h = _parse_fr_number(meta_match.group(1))
            except ValueError:
                change_24h = None
    # 2. Sinon, filet de sécurité : premier pourcentage après le prix dans le
    #    texte visible de la page (fonctionnait déjà pour certains clubs).
    if change_24h is None:
        change_match = _CHANGE_RE.search(text, price_match.end())
        if change_match:
            try:
                change_24h = _parse_fr_number(change_match.group(1))
            except ValueError:
                change_24h = None

    # Le signe n'est jamais dans le texte (ni meta, ni visible) sur ce site —
    # seulement dans la couleur CSS. On applique cette détection par-dessus
    # la magnitude trouvée ci-dessus (toujours positive jusqu'ici).
    if change_24h is not None:
        change_24h = abs(change_24h)
        is_negative = _detect_change_sign(soup)
        if is_negative:
            change_24h = -change_24h

    title_tag = soup.find("h1")
    name = title_tag.get_text(strip=True) if title_tag else slug

    logo = _extract_logo(soup, title_tag, name)

    return {"price_usd": price_usd, "change_24h": change_24h, "name": name, "logo": logo}


def _extract_logo(soup: BeautifulSoup, title_tag, name: str) -> str | None:
    """Best-effort : voir la docstring de fetch_fantoken_page pour l'ordre
    des stratégies essayées."""
    # 1. og:image (méta de partage réseaux sociaux, quasi toujours présente
    # et pointe vers le logo/icône du token sur ce type de site).
    og_image = soup.find("meta", attrs={"property": "og:image"})
    if og_image and og_image.get("content"):
        return og_image["content"]

    # 2. Première image après le <h1> (logo affiché à côté du titre).
    if title_tag:
        img = title_tag.find_next("img")
        if img and (img.get("src") or img.get("data-src")):
            return img.get("src") or img.get("data-src")

    # 3. Image dont l'alt correspond au nom du club/token.
    name_lower = name.lower()
    for img in soup.find_all("img"):
        alt = (img.get("alt") or "").strip().lower()
        if not alt:
            continue
        if alt in name_lower or name_lower in alt or "logo" in alt or "token" in alt:
            src = img.get("src") or img.get("data-src")
            if src:
                return src

    return None


def fetch_usd_to_eur_rate(timeout: int = 10) -> float:
    """Taux de change USD -> EUR actuel (API gratuite Frankfurter, sans clé,
    données BCE). Lève une exception si indisponible — pas de valeur bidon
    en repli, mieux vaut afficher une erreur qu'un prix silencieusement faux."""
    r = _get_with_retry(FX_RATE_URL, timeout=timeout, params={"from": "USD", "to": "EUR"})
    if r is None:
        raise ConnectionError("Impossible de récupérer le taux de change USD/EUR.")
    data = r.json()
    rate = data.get("rates", {}).get("EUR")
    if not rate:
        raise ConnectionError("Réponse inattendue de l'API de taux de change (pas de taux EUR).")
    return float(rate)


def fetch_all_prices(
    club_slugs: dict, vs_currency: str = "eur", timeout: int = 15, max_workers: int = 12
) -> dict:
    """club_slugs : dict {club_name: slug}. Récupère le prix de chaque club
    (fantokens.com n'a pas d'endpoint qui renvoie tout d'un coup), EN
    PARALLÈLE via un ThreadPoolExecutor — vu que chaque requête passe le
    plus clair de son temps à attendre le réseau, les paralléliser divise
    le temps total par ~max_workers au lieu de faire la somme de toutes
    les requêtes une par une. Convertit en EUR si besoin, et renvoie
    {club_name: {"price": float, "change_24h": float|None}} — les clubs
    dont le slug ne correspond à aucune page sont absents du résultat
    (ils resteront donc en zone de saisie manuelle côté app.py)."""
    fx_rate = 1.0
    if vs_currency == "eur":
        fx_rate = fetch_usd_to_eur_rate(timeout=timeout)

    items = [(club, slug) for club, slug in club_slugs.items() if slug]
    results = {}
    if not items:
        return results

    with ThreadPoolExecutor(max_workers=min(max_workers, len(items))) as executor:
        future_to_club = {
            executor.submit(fetch_fantoken_page, slug, timeout): club for club, slug in items
        }
        for future in as_completed(future_to_club):
            club = future_to_club[future]
            try:
                page = future.result()
            except Exception:
                continue
            if not page:
                continue
            price = page["price_usd"] * fx_rate if vs_currency == "eur" else page["price_usd"]
            results[club] = {"price": price, "change_24h": page["change_24h"]}
    return results
