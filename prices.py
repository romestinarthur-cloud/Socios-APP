"""
Récupère les prix live des Fan Tokens Socios/Chiliz via l'API publique CoinGecko
(pas de clé requise) et fait correspondre chaque club scrapé sur socios.com
à son token sur CoinGecko (par similarité de nom, avec table de correction manuelle).
"""

import time
import requests
from rapidfuzz import fuzz, process

COINGECKO_MARKETS_URL = "https://api.coingecko.com/api/v3/coins/markets"

# Catégorie CoinGecko confirmée existante : https://www.coingecko.com/en/categories/fan-token
CATEGORY_SLUGS_TO_TRY = ["fan-token"]

# CoinGecko (derrière Cloudflare) bloque parfois les requêtes sans en-tête
# "navigateur" plausible, ou renvoie 429 sur l'API gratuite publique en cas
# de trop de requêtes. On met un User-Agent et on retry une fois en cas de 429.
REQUEST_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept": "application/json",
}


def _get_with_retry(url: str, params: dict, timeout: int, retries: int = 2):
    last_exc = None
    for attempt in range(retries + 1):
        try:
            r = requests.get(url, params=params, headers=REQUEST_HEADERS, timeout=timeout)
            if r.status_code == 429:
                time.sleep(2 * (attempt + 1))
                last_exc = ConnectionError("CoinGecko: trop de requêtes (429), réessaie plus tard.")
                continue
            r.raise_for_status()
            return r
        except requests.exceptions.RequestException as e:
            last_exc = e
            time.sleep(1 * (attempt + 1))
    raise last_exc


def search_coingecko(query: str, timeout: int = 15) -> list[dict]:
    """Recherche libre de tokens sur CoinGecko (pas limité à la catégorie fan-token)."""
    if not query or not query.strip():
        return []
    r = _get_with_retry("https://api.coingecko.com/api/v3/search", {"query": query.strip()}, timeout)
    return r.json().get("coins", [])


def fetch_prices_by_ids(ids: list[str], vs_currency: str = "eur", timeout: int = 20) -> list[dict]:
    """Récupère les prix pour une liste précise d'ids CoinGecko (ex: ceux choisis
    manuellement via search_coingecko et pas forcément dans la catégorie fan-token)."""
    ids = [i for i in dict.fromkeys(ids) if i]
    if not ids:
        return []
    params = {
        "vs_currency": vs_currency,
        "ids": ",".join(ids),
        "per_page": len(ids),
        "page": 1,
        "sparkline": "false",
        "price_change_percentage": "24h",
    }
    r = _get_with_retry(COINGECKO_MARKETS_URL, params, timeout)
    return r.json()


def fetch_all_candidate_tokens(vs_currency: str = "eur", timeout: int = 20) -> list[dict]:
    """Récupère les tokens de la catégorie fan-token sur CoinGecko."""
    results = {}
    errors = []

    for cat in CATEGORY_SLUGS_TO_TRY:
        try:
            params = {
                "vs_currency": vs_currency,
                "category": cat,
                "order": "market_cap_desc",
                "per_page": 250,
                "page": 1,
                "sparkline": "false",
                "price_change_percentage": "24h",
            }
            r = _get_with_retry(COINGECKO_MARKETS_URL, params, timeout)
            for coin in r.json():
                results[coin["id"]] = coin
        except Exception as e:
            errors.append(f"{cat}: {e}")

    if not results:
        detail = " | ".join(errors) if errors else "raison inconnue"
        raise ConnectionError(f"Impossible de contacter l'API CoinGecko ({detail}).")

    return list(results.values())


# Corrections manuelles pour les noms qui ne matchent pas bien automatiquement.
# clé = nom exact tel qu'affiché sur socios.com -> valeur = id CoinGecko
MANUAL_OVERRIDES = {
    "FC Barcelona": "fc-barcelona-fan-token",
    "FC Internazionale Milano": "inter-milan-fan-token",
    "AC Milan": "ac-milan-fan-token",
    "AS Roma": "as-roma-fan-token",
    "Atlético de Madrid": "atletico-madrid-fan-token",
    "Paris Saint-Germain": "paris-saint-germain-fan-token",
    "Manchester City FC": "manchester-city-fan-token",
    "Arsenal FC": "arsenal-fan-token",
    "Tottenham Hotspur": "tottenham-hotspur-fan-token",
    "Juventus": "juventus-fan-token",
    "Galatasaray S.K.": "galatasaray-fan-token",
    "SL Benfica": "sl-benfica-fan-token",
    "Valencia CF": "valencia-cf-fan-token",
    "Napoli": "napoli-fan-token",
}


def best_match(team_name: str, candidates: list[dict], score_cutoff: int = 70):
    """Trouve le token CoinGecko le plus proche du nom du club.
    Retourne (coin_dict, score) — score=100 si trouvé via MANUAL_OVERRIDES,
    score=None si rien de suffisamment proche n'a été trouvé."""
    if team_name in MANUAL_OVERRIDES:
        target_id = MANUAL_OVERRIDES[team_name]
        for c in candidates:
            if c["id"] == target_id:
                return c, 100

    # Normalisation : on enlève le mot "Fan Token" côté CoinGecko pour comparer.
    choices = {c["id"]: c["name"].replace("Fan Token", "").strip() for c in candidates}
    match = process.extractOne(
        team_name, choices, scorer=fuzz.WRatio, score_cutoff=score_cutoff
    )
    if not match:
        return None, None
    matched_id = match[2]
    score = match[1]
    for c in candidates:
        if c["id"] == matched_id:
            return c, round(score)
    return None, None


def match_teams_to_tokens(teams: list[dict], candidates: list[dict]) -> list[dict]:
    """Pour chaque équipe {name, logo}, ajoute les infos token si trouvé :
    token_id, token_symbol, price, price_change_24h, matched (bool), match_score."""
    enriched = []
    for team in teams:
        coin, score = best_match(team["name"], candidates)
        row = dict(team)
        if coin:
            row.update(
                {
                    "matched": True,
                    "match_score": score,
                    "token_id": coin["id"],
                    "token_symbol": coin["symbol"].upper(),
                    "price": coin.get("current_price"),
                    "price_change_24h": coin.get("price_change_percentage_24h"),
                }
            )
        else:
            row.update(
                {
                    "matched": False,
                    "match_score": None,
                    "token_id": None,
                    "token_symbol": None,
                    "price": None,
                    "price_change_24h": None,
                }
            )
        enriched.append(row)
    return enriched
