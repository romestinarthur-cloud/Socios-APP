"""
Stockage distant (PostgreSQL via Supabase) de l'historique des saisies
utilisateur : pour un club donné, à une date donnée, combien de tokens
détenus et combien de points de récompense par jour cela a rapporté.

La chaîne de connexion vient de st.secrets["DATABASE_URL"] (configurée dans
les "Secrets" de Streamlit Cloud, jamais commitée dans le code / GitHub).
"""

import streamlit as st
import psycopg2
import psycopg2.extras
from datetime import datetime

MAPPING_TABLE = "club_token_mapping"
ENTRIES_TABLE = "entries"
MANUAL_PRICE_TABLE = "manual_prices"
NO_TOKEN_TABLE = "no_token_flags"


def get_conn():
    return psycopg2.connect(st.secrets["DATABASE_URL"])


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
    conn.commit()
    cur.close()
    conn.close()


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
    conn.close()


def get_all_entries() -> list[dict]:
    conn = get_conn()
    cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
    cur.execute(f"SELECT * FROM {ENTRIES_TABLE} ORDER BY entry_date ASC, id ASC")
    rows = cur.fetchall()
    cur.close()
    conn.close()
    return rows


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
    conn.close()
    return {r["club"]: r for r in rows}


def delete_entry(entry_id: int):
    conn = get_conn()
    cur = conn.cursor()
    cur.execute(f"DELETE FROM {ENTRIES_TABLE} WHERE id = %s", (entry_id,))
    conn.commit()
    cur.close()
    conn.close()


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
    conn.close()


def get_manual_prices() -> dict:
    """dict club -> {"price": float, "currency": str|None}."""
    conn = get_conn()
    cur = conn.cursor()
    cur.execute(f"SELECT club, price, currency FROM {MANUAL_PRICE_TABLE}")
    rows = cur.fetchall()
    cur.close()
    conn.close()
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
    conn.close()


def get_no_token_flags() -> set:
    conn = get_conn()
    cur = conn.cursor()
    cur.execute(f"SELECT club FROM {NO_TOKEN_TABLE}")
    rows = cur.fetchall()
    cur.close()
    conn.close()
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
    conn.close()


def get_saved_mappings() -> dict:
    conn = get_conn()
    cur = conn.cursor()
    cur.execute(f"SELECT club, token_id FROM {MAPPING_TABLE}")
    rows = cur.fetchall()
    cur.close()
    conn.close()
    return {r[0]: r[1] for r in rows}
