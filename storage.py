"""
Stockage local (SQLite) de l'historique des saisies utilisateur :
pour un club donné, à une date donnée, combien de tokens détenus
et combien de points de récompense par jour cela a rapporté.

Le fichier socios_data.db est créé à côté de ce script et persiste
d'un lancement à l'autre de l'application.
"""

import sqlite3
from pathlib import Path
from datetime import datetime

DB_PATH = Path(__file__).parent / "socios_data.db"

# Table de correspondance club -> token CoinGecko, mémorisée une fois
# validée/corrigée manuellement par l'utilisateur dans l'interface.
MAPPING_TABLE = "club_token_mapping"
ENTRIES_TABLE = "entries"
MANUAL_PRICE_TABLE = "manual_prices"
# Table séparée du prix : "ce club n'a pas de token" est une décision qui doit
# être mémorisée même AVANT qu'un prix ait été tapé, et qui doit résister à un
# rafraîchissement (sinon un nouveau matching automatique l'écraserait).
NO_TOKEN_TABLE = "no_token_flags"


def get_conn():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    conn = get_conn()
    conn.execute(
        f"""
        CREATE TABLE IF NOT EXISTS {ENTRIES_TABLE} (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            club TEXT NOT NULL,
            entry_date TEXT NOT NULL,
            tokens_qty REAL NOT NULL,
            points_per_day REAL NOT NULL,
            price_at_entry REAL,
            created_at TEXT NOT NULL
        )
        """
    )
    conn.execute(
        f"""
        CREATE TABLE IF NOT EXISTS {MAPPING_TABLE} (
            club TEXT PRIMARY KEY,
            token_id TEXT
        )
        """
    )
    conn.execute(
        f"""
        CREATE TABLE IF NOT EXISTS {MANUAL_PRICE_TABLE} (
            club TEXT PRIMARY KEY,
            price REAL,
            currency TEXT
        )
        """
    )
    conn.execute(
        f"""
        CREATE TABLE IF NOT EXISTS {NO_TOKEN_TABLE} (
            club TEXT PRIMARY KEY
        )
        """
    )
    # Migration : si la base existait déjà avant l'ajout de la colonne currency,
    # CREATE TABLE IF NOT EXISTS ci-dessus ne l'ajoute pas — on le fait à la main.
    existing_cols = {r["name"] for r in conn.execute(f"PRAGMA table_info({MANUAL_PRICE_TABLE})")}
    if "currency" not in existing_cols:
        conn.execute(f"ALTER TABLE {MANUAL_PRICE_TABLE} ADD COLUMN currency TEXT")
    conn.commit()
    conn.close()


def add_entry(club: str, tokens_qty: float, points_per_day: float, price_at_entry: float | None,
              entry_date: str | None = None):
    conn = get_conn()
    conn.execute(
        f"""INSERT INTO {ENTRIES_TABLE} (club, entry_date, tokens_qty, points_per_day, price_at_entry, created_at)
            VALUES (?, ?, ?, ?, ?, ?)""",
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
    conn.close()


def get_all_entries() -> list[sqlite3.Row]:
    conn = get_conn()
    rows = conn.execute(f"SELECT * FROM {ENTRIES_TABLE} ORDER BY entry_date ASC, id ASC").fetchall()
    conn.close()
    return rows


def get_latest_entry_per_club() -> dict:
    """dict club -> dernière ligne (Row) saisie."""
    conn = get_conn()
    rows = conn.execute(
        f"""
        SELECT e.* FROM {ENTRIES_TABLE} e
        INNER JOIN (
            SELECT club, MAX(id) AS max_id FROM {ENTRIES_TABLE} GROUP BY club
        ) latest ON e.club = latest.club AND e.id = latest.max_id
        """
    ).fetchall()
    conn.close()
    return {r["club"]: r for r in rows}


def delete_entry(entry_id: int):
    conn = get_conn()
    conn.execute(f"DELETE FROM {ENTRIES_TABLE} WHERE id = ?", (entry_id,))
    conn.commit()
    conn.close()


def save_manual_price(club: str, price: float | None, currency: str | None = None):
    """Enregistre un prix saisi à la main pour un club, avec la devise dans laquelle
    il a été tapé (essentiel : un prix EUR affiché tel quel après passage en USD
    serait faux). Passer price=None supprime la saisie manuelle."""
    conn = get_conn()
    if price is None:
        conn.execute(f"DELETE FROM {MANUAL_PRICE_TABLE} WHERE club = ?", (club,))
    else:
        conn.execute(
            f"INSERT INTO {MANUAL_PRICE_TABLE} (club, price, currency) VALUES (?, ?, ?) "
            f"ON CONFLICT(club) DO UPDATE SET price=excluded.price, currency=excluded.currency",
            (club, price, currency),
        )
    conn.commit()
    conn.close()


def get_manual_prices() -> dict:
    """dict club -> {"price": float, "currency": str|None}. currency=None pour
    d'anciennes saisies faites avant l'ajout de ce champ (à ressaisir)."""
    conn = get_conn()
    rows = conn.execute(f"SELECT club, price, currency FROM {MANUAL_PRICE_TABLE}").fetchall()
    conn.close()
    return {r["club"]: {"price": r["price"], "currency": r["currency"]} for r in rows}


def save_no_token_flag(club: str, flagged: bool):
    """Mémorise que ce club n'a (volontairement) pas de token — indépendamment
    du fait qu'un prix ait déjà été tapé ou non. Persiste entre les sessions et
    entre deux rafraîchissements."""
    conn = get_conn()
    if flagged:
        conn.execute(
            f"INSERT INTO {NO_TOKEN_TABLE} (club) VALUES (?) ON CONFLICT(club) DO NOTHING",
            (club,),
        )
    else:
        conn.execute(f"DELETE FROM {NO_TOKEN_TABLE} WHERE club = ?", (club,))
    conn.commit()
    conn.close()


def get_no_token_flags() -> set:
    conn = get_conn()
    rows = conn.execute(f"SELECT club FROM {NO_TOKEN_TABLE}").fetchall()
    conn.close()
    return {r["club"] for r in rows}


def save_mapping(club: str, token_id: str | None):
    conn = get_conn()
    conn.execute(
        f"INSERT INTO {MAPPING_TABLE} (club, token_id) VALUES (?, ?) "
        f"ON CONFLICT(club) DO UPDATE SET token_id=excluded.token_id",
        (club, token_id),
    )
    conn.commit()
    conn.close()


def get_saved_mappings() -> dict:
    conn = get_conn()
    rows = conn.execute(f"SELECT club, token_id FROM {MAPPING_TABLE}").fetchall()
    conn.close()
    return {r["club"]: r["token_id"] for r in rows}