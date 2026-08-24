"""
Stockage distant (PostgreSQL via Supabase) de l'historique des saisies
utilisateur : pour un club donné, à une date donnée, combien de tokens
détenus et combien de points de récompense par jour cela a rapporté.

La chaîne de connexion vient de st.secrets["DATABASE_URL"] (configurée dans
les "Secrets" de Streamlit Cloud, jamais commitée dans le code / GitHub).

Optimisation importante : une seule connexion réseau est ouverte et
réutilisée (via st.cache_resource) au lieu d'en ouvrir/fermer une à chaque
appel, ce qui évite plusieurs secondes de latence à chaque interaction.
"""

import streamlit as st
import psycopg2
import psycopg2.extras
import hashlib
import hmac
import os
import time
from datetime import datetime

MAPPING_TABLE = "club_token_mapping"
ENTRIES_TABLE = "entries"
MANUAL_PRICE_TABLE = "manual_prices"
NO_TOKEN_TABLE = "no_token_flags"
RANK_SNAPSHOT_TABLE = "rank_snapshot"
CLUB_LINKS_TABLE = "club_links"
EXTRA_CLUBS_TABLE = "extra_clubs"
APP_USERS_TABLE = "app_users"
PORTFOLIO_TABLE = "portfolio_holdings"
PORTFOLIO_HISTORY_TABLE = "portfolio_history"


@st.cache_resource(show_spinner=False)
def _get_conn():
    conn = psycopg2.connect(st.secrets["DATABASE_URL"])
    conn.autocommit = False
    return conn


# Horodatage du dernier "ping" de santé de la connexion, en dehors de toute
# fonction pour survivre aux reruns Streamlit (le process reste le même).
_last_conn_check = {"t": 0.0}
_CONN_CHECK_INTERVAL = 30  # secondes


def get_conn():
    """Réutilise une connexion existante ; la reconnecte si elle a expiré
    (Supabase peut fermer une connexion inactive après un moment).

    Le test de santé ("SELECT 1") ne coûtait rien en soi, mais comme il
    tournait AVANT CHAQUE requête (get_conn est appelé par toutes les
    fonctions de ce fichier), une page qui fait 15 requêtes faisait en
    réalité 30 allers-retours réseau vers Supabase. On ne le fait donc plus
    qu'au maximum une fois toutes les 30 secondes."""
    conn = _get_conn()
    now = time.monotonic()
    if now - _last_conn_check["t"] < _CONN_CHECK_INTERVAL:
        return conn
    try:
        cur = conn.cursor()
        cur.execute("SELECT 1")
        cur.close()
        conn.rollback()
    except Exception:
        _get_conn.clear()
        conn = _get_conn()
    return conn


def init_db():
    conn = get_conn()
    cur = conn.cursor()
    cur.execute(
        f"""
        CREATE TABLE IF NOT EXISTS {ENTRIES_TABLE} (
            id SERIAL PRIMARY KEY,
            club TEXT NOT NULL,
            entry_date TEXT NOT NULL,
            tokens_qty REAL NOT NULL,
            points_per_day REAL NOT NULL,
            price_at_entry REAL,
            created_at TEXT NOT NULL
        )
        """
    )
    cur.execute(
        f"""
        CREATE TABLE IF NOT EXISTS {MAPPING_TABLE} (
            club TEXT PRIMARY KEY,
            token_id TEXT
        )
        """
    )
    cur.execute(
        f"""
        CREATE TABLE IF NOT EXISTS {MANUAL_PRICE_TABLE} (
            club TEXT PRIMARY KEY,
            price REAL,
            currency TEXT,
            is_fallback BOOLEAN NOT NULL DEFAULT FALSE
        )
        """
    )
    # Ajoute la colonne si la table existait déjà avant cette version
    # (bases existantes créées avant l'ajout de is_fallback).
    cur.execute(
        f"ALTER TABLE {MANUAL_PRICE_TABLE} ADD COLUMN IF NOT EXISTS is_fallback BOOLEAN NOT NULL DEFAULT FALSE"
    )
    cur.execute(
        f"""
        CREATE TABLE IF NOT EXISTS {NO_TOKEN_TABLE} (
            club TEXT PRIMARY KEY
        )
        """
    )
    cur.execute(
        f"""
        CREATE TABLE IF NOT EXISTS {RANK_SNAPSHOT_TABLE} (
            club TEXT PRIMARY KEY,
            position INTEGER NOT NULL,
            snapshot_date TEXT NOT NULL
        )
        """
    )
    cur.execute(
        f"""
        CREATE TABLE IF NOT EXISTS {CLUB_LINKS_TABLE} (
            club TEXT PRIMARY KEY,
            url TEXT
        )
        """
    )
    cur.execute(
        f"""
        CREATE TABLE IF NOT EXISTS {EXTRA_CLUBS_TABLE} (
            club TEXT PRIMARY KEY,
            logo TEXT NOT NULL
        )
        """
    )
    cur.execute(
        f"""
        CREATE TABLE IF NOT EXISTS {APP_USERS_TABLE} (
            username TEXT PRIMARY KEY,
            password_hash TEXT NOT NULL,
            salt TEXT NOT NULL,
            is_admin BOOLEAN NOT NULL DEFAULT FALSE,
            created_at TEXT NOT NULL
        )
        """
    )
    conn.commit()
    cur.close()

    _ensure_bootstrap_admin()


# ---------------------------------------------------------------------------
# Authentification
# ---------------------------------------------------------------------------

def _hash_password(password: str, salt: str) -> str:
    return hashlib.pbkdf2_hmac(
        "sha256", password.encode("utf-8"), salt.encode("utf-8"), 200_000
    ).hex()


def _ensure_bootstrap_admin():
    """Crée le compte super admin au premier lancement, à partir des
    identifiants définis dans les Secrets Streamlit (ADMIN_USERNAME /
    ADMIN_PASSWORD). Ne fait rien si un utilisateur existe déjà, ou si les
    secrets ne sont pas configurés."""
    conn = get_conn()
    cur = conn.cursor()
    cur.execute(f"SELECT COUNT(*) FROM {APP_USERS_TABLE}")
    (count,) = cur.fetchone()
    cur.close()
    if count > 0:
        return

    admin_user = st.secrets.get("ADMIN_USERNAME")
    admin_pass = st.secrets.get("ADMIN_PASSWORD")
    if not admin_user or not admin_pass:
        return
    create_user(admin_user, admin_pass, is_admin=True)


def create_user(username: str, password: str, is_admin: bool = False):
    salt = os.urandom(16).hex()
    pw_hash = _hash_password(password, salt)
    conn = get_conn()
    cur = conn.cursor()
    cur.execute(
        f"""INSERT INTO {APP_USERS_TABLE} (username, password_hash, salt, is_admin, created_at)
            VALUES (%s, %s, %s, %s, %s)
            ON CONFLICT (username) DO UPDATE SET
                password_hash = EXCLUDED.password_hash,
                salt = EXCLUDED.salt,
                is_admin = EXCLUDED.is_admin""",
        (username.strip(), pw_hash, salt, is_admin, datetime.utcnow().isoformat()),
    )
    conn.commit()
    cur.close()


def verify_user(username: str, password: str):
    """Retourne {"username": ..., "is_admin": ...} si les identifiants sont
    corrects, sinon None."""
    conn = get_conn()
    cur = conn.cursor()
    cur.execute(
        f"SELECT password_hash, salt, is_admin FROM {APP_USERS_TABLE} WHERE username = %s",
        (username.strip(),),
    )
    row = cur.fetchone()
    cur.close()
    if not row:
        return None
    stored_hash, salt, is_admin = row
    candidate_hash = _hash_password(password, salt)
    if hmac.compare_digest(candidate_hash, stored_hash):
        return {"username": username.strip(), "is_admin": bool(is_admin)}
    return None


def list_users():
    conn = get_conn()
    cur = conn.cursor()
    cur.execute(
        f"SELECT username, is_admin, created_at FROM {APP_USERS_TABLE} ORDER BY created_at"
    )
    rows = cur.fetchall()
    cur.close()
    return [{"username": r[0], "is_admin": bool(r[1]), "created_at": r[2]} for r in rows]


def delete_user(username: str):
    conn = get_conn()
    cur = conn.cursor()
    cur.execute(f"DELETE FROM {APP_USERS_TABLE} WHERE username = %s", (username.strip(),))
    conn.commit()
    cur.close()


def add_entry(club: str, tokens_qty: float, points_per_day: float, price_at_entry: float | None,
              entry_date: str | None = None):
    conn = get_conn()
    cur = conn.cursor()
    cur.execute(
        f"""INSERT INTO {ENTRIES_TABLE} (club, entry_date, tokens_qty, points_per_day, price_at_entry, created_at)
            VALUES (%s, %s, %s, %s, %s, %s)""",
        (
            club,
            entry_date or datetime.now().strftime("%Y-%m-%d"),
            tokens_qty,
            points_per_day,
            price_at_entry,
            datetime.now().isoformat(timespec="seconds"),
        ),
    )
    conn.commit()
    cur.close()


def add_entries_bulk(entries: list[dict]):
    """Enregistre plusieurs saisies en une seule transaction (une seule
    connexion réseau utilisée) au lieu d'un aller-retour par club — bien plus
    rapide quand on saisit beaucoup de clubs d'un coup.
    Chaque dict : {club, tokens_qty, points_per_day, price_at_entry, entry_date?}"""
    if not entries:
        return
    conn = get_conn()
    cur = conn.cursor()
    now = datetime.now()
    values = [
        (
            e["club"],
            e.get("entry_date") or now.strftime("%Y-%m-%d"),
            e["tokens_qty"],
            e["points_per_day"],
            e.get("price_at_entry"),
            now.isoformat(timespec="seconds"),
        )
        for e in entries
    ]
    psycopg2.extras.execute_values(
        cur,
        f"""INSERT INTO {ENTRIES_TABLE} (club, entry_date, tokens_qty, points_per_day, price_at_entry, created_at)
            VALUES %s""",
        values,
    )
    conn.commit()
    cur.close()


def get_all_entries() -> list[dict]:
    conn = get_conn()
    cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
    cur.execute(f"SELECT * FROM {ENTRIES_TABLE} ORDER BY entry_date ASC, id ASC")
    rows = cur.fetchall()
    cur.close()
    return [dict(r) for r in rows]


def get_latest_entry_per_club() -> dict:
    """dict club -> dernière ligne (dict) saisie."""
    conn = get_conn()
    cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
    cur.execute(
        f"""
        SELECT e.* FROM {ENTRIES_TABLE} e
        INNER JOIN (
            SELECT club, MAX(id) AS max_id FROM {ENTRIES_TABLE} GROUP BY club
        ) latest ON e.club = latest.club AND e.id = latest.max_id
        """
    )
    rows = cur.fetchall()
    cur.close()
    return {r["club"]: dict(r) for r in rows}


def update_entry(entry_id: int, tokens_qty: float, points_per_day: float, entry_date: str):
    """Corrige une saisie passée (ex : erreur de frappe sur les points/jour)."""
    conn = get_conn()
    cur = conn.cursor()
    cur.execute(
        f"""UPDATE {ENTRIES_TABLE} SET tokens_qty = %s, points_per_day = %s, entry_date = %s
            WHERE id = %s""",
        (tokens_qty, points_per_day, entry_date, entry_id),
    )
    conn.commit()
    cur.close()


def delete_entry(entry_id: int):
    conn = get_conn()
    cur = conn.cursor()
    cur.execute(f"DELETE FROM {ENTRIES_TABLE} WHERE id = %s", (entry_id,))
    conn.commit()
    cur.close()


def save_manual_price(club: str, price: float | None, currency: str | None = None, is_fallback: bool = False):
    """Enregistre un prix saisi à la main pour un club, avec la devise dans laquelle
    il a été tapé (essentiel : un prix EUR affiché tel quel après passage en USD
    serait faux). Passer price=None supprime la saisie manuelle.

    is_fallback distingue deux usages très différents du même mécanisme :
    - is_fallback=True  : prix de secours tapé parce qu'aucun prix automatique
      n'était disponible (zone "clubs sans prix"). Doit céder la place dès
      qu'un prix automatique redevient disponible pour ce club (cf.
      build_dataframe dans app.py) — sinon il resterait affiché pour
      toujours même une fois le vrai prix retrouvé.
    - is_fallback=False (défaut) : correction volontaire d'un prix automatique
      que l'utilisateur sait faux (bouton "Enregistrer prix corrigés").
      Doit rester prioritaire indéfiniment, l'utilisateur a fait ce choix
      en connaissance de cause."""
    conn = get_conn()
    cur = conn.cursor()
    if price is None:
        cur.execute(f"DELETE FROM {MANUAL_PRICE_TABLE} WHERE club = %s", (club,))
    else:
        cur.execute(
            f"""INSERT INTO {MANUAL_PRICE_TABLE} (club, price, currency, is_fallback) VALUES (%s, %s, %s, %s)
                ON CONFLICT (club) DO UPDATE SET price = EXCLUDED.price, currency = EXCLUDED.currency,
                    is_fallback = EXCLUDED.is_fallback""",
            (club, price, currency, is_fallback),
        )
    conn.commit()
    cur.close()


def get_manual_prices() -> dict:
    """dict club -> {"price": float, "currency": str|None, "is_fallback": bool}."""
    conn = get_conn()
    cur = conn.cursor()
    cur.execute(f"SELECT club, price, currency, is_fallback FROM {MANUAL_PRICE_TABLE}")
    rows = cur.fetchall()
    cur.close()
    return {r[0]: {"price": r[1], "currency": r[2], "is_fallback": r[3]} for r in rows}


def save_no_token_flag(club: str, flagged: bool):
    """Mémorise que ce club n'a (volontairement) pas de token — indépendamment
    du fait qu'un prix ait déjà été tapé ou non. Persiste entre les sessions et
    entre deux rafraîchissements."""
    conn = get_conn()
    cur = conn.cursor()
    if flagged:
        cur.execute(
            f"INSERT INTO {NO_TOKEN_TABLE} (club) VALUES (%s) ON CONFLICT (club) DO NOTHING",
            (club,),
        )
    else:
        cur.execute(f"DELETE FROM {NO_TOKEN_TABLE} WHERE club = %s", (club,))
    conn.commit()
    cur.close()


def get_no_token_flags() -> set:
    conn = get_conn()
    cur = conn.cursor()
    cur.execute(f"SELECT club FROM {NO_TOKEN_TABLE}")
    rows = cur.fetchall()
    cur.close()
    return {r[0] for r in rows}


def save_mapping(club: str, token_id: str | None):
    conn = get_conn()
    cur = conn.cursor()
    cur.execute(
        f"""INSERT INTO {MAPPING_TABLE} (club, token_id) VALUES (%s, %s)
            ON CONFLICT (club) DO UPDATE SET token_id = EXCLUDED.token_id""",
        (club, token_id),
    )
    conn.commit()
    cur.close()


def get_saved_mappings() -> dict:
    conn = get_conn()
    cur = conn.cursor()
    cur.execute(f"SELECT club, token_id FROM {MAPPING_TABLE}")
    rows = cur.fetchall()
    cur.close()
    return {r[0]: r[1] for r in rows}


def get_rank_snapshot() -> dict:
    """dict club -> {"position": int, "date": str} — dernier classement connu,
    pour comparer et afficher les mouvements (▲/▼) dans le classement actuel."""
    conn = get_conn()
    cur = conn.cursor()
    cur.execute(f"SELECT club, position, snapshot_date FROM {RANK_SNAPSHOT_TABLE}")
    rows = cur.fetchall()
    cur.close()
    return {r[0]: {"position": r[1], "date": r[2]} for r in rows}


def save_rank_snapshot(positions: dict, snapshot_date: str):
    """Remplace le snapshot de classement stocké par les positions actuelles,
    pour servir de référence de comparaison la prochaine fois."""
    conn = get_conn()
    cur = conn.cursor()
    cur.execute(f"DELETE FROM {RANK_SNAPSHOT_TABLE}")
    if positions:
        psycopg2.extras.execute_values(
            cur,
            f"INSERT INTO {RANK_SNAPSHOT_TABLE} (club, position, snapshot_date) VALUES %s",
            [(club, pos, snapshot_date) for club, pos in positions.items()],
        )
    conn.commit()
    cur.close()


def save_club_link(club: str, url: str | None):
    """Enregistre le lien direct vers la page Socios de ce club (pour un accès
    rapide depuis l'onglet Saisie). url=None ou vide supprime le lien."""
    conn = get_conn()
    cur = conn.cursor()
    if not url:
        cur.execute(f"DELETE FROM {CLUB_LINKS_TABLE} WHERE club = %s", (club,))
    else:
        cur.execute(
            f"""INSERT INTO {CLUB_LINKS_TABLE} (club, url) VALUES (%s, %s)
                ON CONFLICT (club) DO UPDATE SET url = EXCLUDED.url""",
            (club, url),
        )
    conn.commit()
    cur.close()


def get_club_links() -> dict:
    """dict club -> url"""
    conn = get_conn()
    cur = conn.cursor()
    cur.execute(f"SELECT club, url FROM {CLUB_LINKS_TABLE}")
    rows = cur.fetchall()
    cur.close()
    return {r[0]: r[1] for r in rows}


def save_extra_club(club: str, logo: str):
    """Ajoute un club manqué par le scraping de socios.com, saisi à la main
    (nom + logo) depuis l'onglet Correspondances."""
    conn = get_conn()
    cur = conn.cursor()
    cur.execute(
        f"""INSERT INTO {EXTRA_CLUBS_TABLE} (club, logo) VALUES (%s, %s)
            ON CONFLICT (club) DO UPDATE SET logo = EXCLUDED.logo""",
        (club, logo),
    )
    conn.commit()
    cur.close()


def get_extra_clubs() -> dict:
    """dict club -> logo, pour les clubs ajoutés à la main."""
    conn = get_conn()
    cur = conn.cursor()
    cur.execute(f"SELECT club, logo FROM {EXTRA_CLUBS_TABLE}")
    rows = cur.fetchall()
    cur.close()
    return {r[0]: r[1] for r in rows}


def confirm_verification(club: str, slug: str, logo: str | None):
    """Enregistre tout ce que confirme un "Vérifier" réussi (onglet
    Correspondances) en UNE SEULE transaction/commit au lieu de 3-4 allers-
    retours réseau séparés (save_mapping + save_no_token_flag +
    save_manual_price(None) + save_extra_club) : mapping club -> slug, levée
    du flag "aucun token", suppression d'un éventuel prix de secours saisi à
    la main, et logo trouvé sur fantokens.com s'il y en a un."""
    conn = get_conn()
    cur = conn.cursor()
    cur.execute(
        f"""INSERT INTO {MAPPING_TABLE} (club, token_id) VALUES (%s, %s)
            ON CONFLICT (club) DO UPDATE SET token_id = EXCLUDED.token_id""",
        (club, slug),
    )
    cur.execute(f"DELETE FROM {NO_TOKEN_TABLE} WHERE club = %s", (club,))
    cur.execute(f"DELETE FROM {MANUAL_PRICE_TABLE} WHERE club = %s", (club,))
    if logo:
        cur.execute(
            f"""INSERT INTO {EXTRA_CLUBS_TABLE} (club, logo) VALUES (%s, %s)
                ON CONFLICT (club) DO UPDATE SET logo = EXCLUDED.logo""",
            (club, logo),
        )
    conn.commit()
    cur.close()


def add_manual_club(name: str, slug: str, logo: str):
    """Ajoute un club manqué par le scraping + son mapping de slug, en une
    seule transaction (un seul commit) au lieu de deux appels séparés."""
    conn = get_conn()
    cur = conn.cursor()
    cur.execute(
        f"""INSERT INTO {EXTRA_CLUBS_TABLE} (club, logo) VALUES (%s, %s)
            ON CONFLICT (club) DO UPDATE SET logo = EXCLUDED.logo""",
        (name, logo),
    )
    cur.execute(
        f"""INSERT INTO {MAPPING_TABLE} (club, token_id) VALUES (%s, %s)
            ON CONFLICT (club) DO UPDATE SET token_id = EXCLUDED.token_id""",
        (name, slug),
    )
    conn.commit()
    cur.close()


def delete_extra_club(club: str):
    conn = get_conn()
    cur = conn.cursor()
    cur.execute(f"DELETE FROM {EXTRA_CLUBS_TABLE} WHERE club = %s", (club,))
    conn.commit()
    cur.close()
