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
from datetime import datetime

MAPPING_TABLE = "club_token_mapping"
ENTRIES_TABLE = "entries"
MANUAL_PRICE_TABLE = "manual_prices"
NO_TOKEN_TABLE = "no_token_flags"
RANK_SNAPSHOT_TABLE = "rank_snapshot"
CLUB_LINKS_TABLE = "club_links"
EXTRA_CLUBS_TABLE = "extra_clubs"


@st.cache_resource(show_spinner=False)
def _get_conn():
    conn = psycopg2.connect(st.secrets["DATABASE_URL"])
    conn.autocommit = False
    return conn


def get_conn():
    """Réutilise une connexion existante ; la reconnecte si elle a expiré
    (Supabase peut fermer une connexion inactive après un moment)."""
    conn = _get_conn()
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
            currency TEXT
        )
        """
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


def save_manual_price(club: str, price: float | None, currency: str | None = None):
    """Enregistre un prix saisi à la main pour un club, avec la devise dans laquelle
    il a été tapé (essentiel : un prix EUR affiché tel quel après passage en USD
    serait faux). Passer price=None supprime la saisie manuelle."""
    conn = get_conn()
    cur = conn.cursor()
    if price is None:
        cur.execute(f"DELETE FROM {MANUAL_PRICE_TABLE} WHERE club = %s", (club,))
    else:
        cur.execute(
            f"""INSERT INTO {MANUAL_PRICE_TABLE} (club, price, currency) VALUES (%s, %s, %s)
                ON CONFLICT (club) DO UPDATE SET price = EXCLUDED.price, currency = EXCLUDED.currency""",
            (club, price, currency),
        )
    conn.commit()
    cur.close()


def get_manual_prices() -> dict:
    """dict club -> {"price": float, "currency": str|None}."""
    conn = get_conn()
    cur = conn.cursor()
    cur.execute(f"SELECT club, price, currency FROM {MANUAL_PRICE_TABLE}")
    rows = cur.fetchall()
    cur.close()
    return {r[0]: {"price": r[1], "currency": r[2]} for r in rows}


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


def delete_extra_club(club: str):
    conn = get_conn()
    cur = conn.cursor()
    cur.execute(f"DELETE FROM {EXTRA_CLUBS_TABLE} WHERE club = %s", (club,))
    conn.commit()
    cur.close()
