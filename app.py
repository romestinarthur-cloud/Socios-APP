import pandas as pd
import streamlit as st
import streamlit.components.v1 as components
from datetime import datetime

import storage
import auth
from teams_scraper import get_teams
from concurrent.futures import ThreadPoolExecutor, as_completed
from prices import guess_slug, fetch_usd_to_eur_rate, fetch_fantoken_page

SOCIOS_LOGO_URL = "https://logowik.com/content/uploads/images/socioscom4620.jpg"

st.set_page_config(page_title="Socios – Rendement des Fan Tokens", page_icon="⚽", layout="wide")

storage.init_db()
st.markdown(
    """
    <style>
    .stApp { background-color: #0f1117; color: #f5f6fa; }

    /* Bandeau du haut (header Streamlit) : par défaut fond blanc/transparent,
       ce qui tranche moche avec le thème sombre du reste de l'appli. */
    [data-testid="stHeader"] {
        background-color: #0f1117 !important;
        background: #0f1117 !important;
    }
    [data-testid="stToolbar"] { background-color: #0f1117 !important; }
    [data-testid="stDecoration"] { display: none; }
    header[data-testid="stHeader"] * { color: #f5f6fa !important; }
    #MainMenu { visibility: hidden; }
    footer { visibility: hidden; }
    h1, h2, h3, h4, p, span, label, .stMarkdown { color: #f5f6fa !important; }
    [data-testid="stSidebar"] { background-color: #14161f; }
    [data-testid="stSidebar"] * { color: #f5f6fa !important; }

    /* --- Widgets d'entrée (number_input, selectbox, text_input...) ---
       Sans ça, Streamlit garde un fond clair par défaut pour ces composants
       (ils ne suivent pas .stApp), et comme le texte est forcé en blanc
       ci-dessus, on se retrouve avec du texte blanc sur fond blanc = invisible. */
    div[data-baseweb="input"],
    div[data-baseweb="select"] > div,
    div[data-baseweb="base-input"],
    div[data-baseweb="textarea"],
    .stNumberInput input,
    .stTextInput input,
    .stTextArea textarea {
        background-color: #1a1d29 !important;
        color: #f5f6fa !important;
        border: 1px solid #2f3345 !important;
    }
    .stNumberInput button { background-color: #1a1d29 !important; border-color: #2f3345 !important; }
    .stNumberInput svg, .stSelectbox svg { fill: #f5f6fa !important; }

    /* Menu déroulant ouvert d'un selectbox (rendu dans un portail à part) */
    ul[data-testid="stSelectboxVirtualDropdown"] li,
    div[data-baseweb="popover"] { background-color: #1a1d29 !important; color: #f5f6fa !important; }
    ul[data-testid="stSelectboxVirtualDropdown"] li:hover { background-color: #2f3345 !important; }

    /* Boutons */
    .stButton > button, .stDownloadButton > button {
        background-color: #1a1d29 !important;
        color: #f5f6fa !important;
        border: 1px solid #f107a3 !important;
    }
    .stButton > button:hover, .stDownloadButton > button:hover {
        background-color: #2f1a29 !important;
        border-color: #ff4fc3 !important;
        color: #ffffff !important;
    }
    .stButton > button p { color: #f5f6fa !important; }

    /* Bouton de soumission d'un st.form (utilisé dans la zone de saisie
       manuelle) : classe CSS différente de .stButton, sinon texte invisible. */
    .stFormSubmitButton > button {
        background-color: #1a1d29 !important;
        color: #f5f6fa !important;
        border: 1px solid #f107a3 !important;
    }
    .stFormSubmitButton > button:hover {
        background-color: #2f1a29 !important;
        border-color: #ff4fc3 !important;
    }
    .stFormSubmitButton > button p { color: #f5f6fa !important; }

    /* st.form ajoute par défaut une marge/bordure qui décale son contenu par
       rapport aux autres lignes — on l'enlève pour garder l'alignement. */
    div[data-testid="stForm"] {
        border: none !important;
        padding: 0 !important;
        margin: 0 !important;
    }

    /* Texte affiché (valeur sélectionnée) dans les selectbox — sinon reste
       invisible même quand le menu déroulant lui-même est bien stylé. */
    div[data-baseweb="select"] * { color: #f5f6fa !important; }

    /* Checkbox */
    .stCheckbox label p { color: #f5f6fa !important; }

    /* data_editor / dataframe cellules */
    div[data-testid="stDataFrame"], div[data-testid="stDataEditor"] {
        border-radius: 10px; overflow: hidden;
    }
    div[data-testid="stDataFrame"] *, div[data-testid="stDataEditor"] * {
        color: #0f1117 !important;
    }

    .socios-hero {
        background: linear-gradient(135deg, #7b2ff7 0%, #f107a3 100%);
        padding: 1.4rem 1.8rem; border-radius: 14px; margin-bottom: 1.2rem;
        display: flex; align-items: center; gap: 1.1rem;
    }
    .socios-hero img { height: 42px; border-radius: 6px; background: #fff; padding: 4px 8px; }
    .socios-hero h1 { color: #ffffff !important; margin: 0; font-size: 1.7rem; }
    .socios-hero p { color: #ffffff !important; opacity: 0.95; margin: 0.3rem 0 0 0; font-size: 0.9rem; }
    .metric-card {
        background: linear-gradient(160deg, #1c1f2e 0%, #171a25 100%);
        border: 1px solid #2f3345; border-radius: 12px;
        padding: 1rem 1.1rem; text-align: center;
        transition: border-color 0.15s ease;
    }
    .metric-card:hover { border-color: #f107a3; }
    .metric-card .value { font-size: 1.7rem; font-weight: 700; color: #ff4fc3 !important; }
    .metric-card .label { font-size: 0.75rem; color: #9ba0b8 !important; text-transform: uppercase; letter-spacing: 0.04em; margin-top: 0.15rem; }
    .price-up { color: #3ddc84 !important; font-weight: 600; }
    .price-down { color: #ff5c7a !important; font-weight: 600; }
    .sidebar-logo { display: block; margin: 0 auto 1rem auto; max-width: 150px; border-radius: 6px; }
    .manual-zone {
        background: #241a10; border: 1px solid #a56a1f; border-radius: 12px;
        padding: 1rem 1.2rem; margin-bottom: 1rem;
    }
    .manual-zone h4, .manual-zone p, .manual-zone .stCaption { color: #ffe4b8 !important; }
    div[data-testid="stCaptionContainer"], .stCaption { color: #c7cbdb !important; }

    /* Empêche l'assombrissement/le fondu que Streamlit applique automatiquement
       au contenu pendant qu'un rechargement (rerun) est en cours. Streamlit
       marque les blocs "obsolètes" avec l'attribut data-stale="true" et réduit
       leur opacité via le thème par défaut — on neutralise précisément ça. */
    [data-stale="true"] {
        opacity: 1 !important;
        transition: none !important;
    }
    [data-testid="stAppViewContainer"],
    [data-testid="stMain"],
    [data-testid="stMainBlockContainer"],
    .main .block-container,
    .stApp {
        opacity: 1 !important;
        transition: none !important;
        filter: none !important;
    }
    </style>
    """,
    unsafe_allow_html=True,
)

auth.require_login()


# ---------------------------------------------------------------------------
# Chargement des données (cache 1h pour ne pas spammer socios.com / CoinGecko)
# ---------------------------------------------------------------------------

@st.cache_data(ttl=3600, show_spinner="Récupération des clubs sur socios.com...")
def _fetch_teams_cached():
    """Scraping en direct de socios.com : la partie VRAIMENT coûteuse (requête
    réseau + parsing HTML), mise en cache 1h. Uniquement invalidée par le
    bouton "🔄 Rafraîchir clubs & prix" — surtout PAS par "Vérifier" ou
    "Ajouter un club", qui ne touchent que la table extra_clubs (fusionnée
    par load_teams ci-dessous à chaque appel, sans passer par ce cache)."""
    return get_teams()


def load_teams():
    """Fusionne les clubs scrapés (cache 1h, cf. _fetch_teams_cached) avec les
    clubs/logos ajoutés à la main (table extra_clubs, relue à chaque appel —
    peu coûteux, une seule petite requête DB, pas besoin de cache).
    Avant, toute cette fusion était DANS la fonction mise en cache : corriger
    un slug ("Vérifier") ou ajouter un club obligeait à vider le cache en
    entier pour que le nouveau logo apparaisse, ce qui déclenchait un
    RE-SCRAPING COMPLET de socios.com (plusieurs secondes) à chaque clic.
    En sortant la fusion du cache, "Vérifier"/"Ajouter" prennent effet
    immédiatement sans jamais retoucher au scraping."""
    teams, live_ok = _fetch_teams_cached()
    # Copie : ne pas modifier en place la liste renvoyée par le cache.
    teams = [dict(t) for t in teams]
    extra = storage.get_extra_clubs()
    if extra:
        existing_names = {t["name"] for t in teams}
        # Écrase le logo des clubs déjà présents (ex : logo mieux trouvé sur
        # fantokens.com que sur socios.com) au lieu de les ignorer.
        for t in teams:
            if t["name"] in extra:
                t["logo"] = extra[t["name"]]
        teams = teams + [
            {"name": name, "logo": logo} for name, logo in extra.items() if name not in existing_names
        ]
        teams = sorted(teams, key=lambda t: t["name"].lower())
    return teams, live_ok


@st.cache_data(ttl=3600, show_spinner=False)
def load_fx_rate(vs_currency: str) -> float:
    """Taux de change, mis en cache à part (change rarement, pas la peine
    de le redemander à chaque club)."""
    return fetch_usd_to_eur_rate() if vs_currency == "eur" else 1.0


@st.cache_data(ttl=3600, show_spinner=False)
def load_single_price(club: str, slug: str, vs_currency: str, fx_rate: float):
    """Cache PAR CLUB (clé = club + slug + devise), pas un seul gros cache
    global. Résultat : vérifier/changer le slug d'UN club, ou cocher/décocher
    "aucun token", n'a plus d'effet sur le cache des autres clubs — seul le
    club concerné est (re)fetché, tous les autres restent servis depuis le
    cache existant, instantanément."""
    page = fetch_fantoken_page(slug)
    if not page:
        return None
    price = page["price_usd"] * fx_rate if vs_currency == "eur" else page["price_usd"]
    return {"price": price, "change_24h": page["change_24h"]}


def load_prices(club_slugs: dict, vs_currency: str) -> dict:
    """Récupère le prix de chaque club via load_single_price (caché
    individuellement), en parallèle pour les clubs qui ne sont pas déjà en
    cache — donc un "Rafraîchir" complet reste rapide (parallélisé), et un
    clic isolé (Vérifier / aucun token / lien) ne retouche que le club
    concerné."""
    fx_rate = load_fx_rate(vs_currency)
    items = [(club, slug) for club, slug in club_slugs.items() if slug]
    if not items:
        return {}
    results = {}
    with ThreadPoolExecutor(max_workers=min(24, len(items))) as executor:
        future_to_club = {
            executor.submit(load_single_price, club, slug, vs_currency, fx_rate): club
            for club, slug in items
        }
        for future in as_completed(future_to_club):
            club = future_to_club[future]
            try:
                res = future.result()
            except Exception:
                continue
            if res:
                results[club] = res
    return results


def build_dataframe(capital: float, vs_currency: str) -> pd.DataFrame:
    teams, live_ok = load_teams()

    saved_mappings = storage.get_saved_mappings()  # club -> slug fantokens.com (corrigé à la main)
    no_token_flags = storage.get_no_token_flags()
    manual_prices = storage.get_manual_prices()  # club -> {"price":..., "currency":...}

    # Slug à interroger pour chaque club — y compris ceux marqués "aucun
    # token" : on les filtre plus bas (ligne "if club in no_token_flags"),
    # PAS ici. Les exclure ici changerait la clé de cache de load_prices
    # à chaque coche/décoche de la case "aucun token", et forcerait un
    # re-fetch complet de tous les autres clubs pour rien.
    club_slugs = {}
    for team in teams:
        club = team["name"]
        club_slugs[club] = saved_mappings.get(club) or guess_slug(club)

    # Prix auto (fantokens.com) réutilisés depuis la session tant que la liste
    # de clubs et la devise n'ont pas changé : sans ça, CHAQUE interaction (un
    # simple prix corrigé à la main, un point/jour saisi...) déclenchait un
    # rerun complet qui refaisait tourner load_prices pour TOUS les clubs —
    # même si le cache Streamlit sous-jacent évitait le vrai appel réseau, le
    # ré-orchestrer (spinner + pool de 100+ tâches) pour rien ralentissait et
    # donnait l'impression de "tout re-télécharger" à chaque petite mise à
    # jour. Ici, un prix manuel ne touche PAS aux prix auto : pas besoin de
    # rappeler load_prices du tout pour que la mise à jour se voie.
    price_cache_key = (vs_currency, tuple(sorted(club_slugs.items())))
    cached_prices = st.session_state.get("_price_data_cache")
    if cached_prices and cached_prices["key"] == price_cache_key:
        price_data = cached_prices["data"]
        prices_ok = cached_prices["ok"]
    else:
        try:
            # load_single_price est caché avec show_spinner=False (pour ne pas
            # spammer un spinner par club) : sans ce spinner englobant, un
            # premier chargement (cache vide/expiré) ne montre RIEN pendant
            # plusieurs secondes, ce qui donne l'impression que l'appli est
            # bloquée juste après le login.
            with st.spinner("Récupération des prix sur fantokens.com..."):
                price_data = load_prices(club_slugs, vs_currency)
            prices_ok = True
        except Exception as e:
            price_data = {}
            prices_ok = False
            st.session_state["_prices_error"] = str(e)
        st.session_state["_price_data_cache"] = {
            "key": price_cache_key, "data": price_data, "ok": prices_ok,
        }
    st.session_state["_prices_ok"] = prices_ok

    enriched = []
    for team in teams:
        club = team["name"]
        row = dict(team)

        if club in no_token_flags:
            row.update(matched=False, price=None, price_change_24h=None)
        else:
            found = price_data.get(club)
            if found:
                row.update(matched=True, price=found["price"], price_change_24h=found["change_24h"])
            else:
                # Slug deviné/enregistré introuvable sur fantokens.com (404) ou
                # échec réseau ponctuel pour ce club -> zone de saisie manuelle.
                row.update(matched=False, price=None, price_change_24h=None)

        # Prix saisi à la main : ne s'applique que si sa devise correspond à la
        # devise actuellement sélectionnée (sinon on redemande la saisie).
        manual = manual_prices.get(club)
        row["needs_currency_reentry"] = False
        auto_price_available = row["matched"]  # avant override manuel, cf. ci-dessus
        row["auto_matched"] = auto_price_available  # gardé pour is_fallback plus bas
        if manual is not None and manual.get("price") is not None:
            # Un prix "de secours" (tapé faute de prix auto) doit céder la
            # place dès qu'un prix automatique redevient disponible pour ce
            # club — sinon il resterait affiché pour toujours même après
            # correction du slug (cf. bug : compteur "prix manuels" qui ne
            # redescend jamais). Une correction volontaire (is_fallback=False)
            # reste prioritaire quoi qu'il arrive.
            stale_fallback = manual.get("is_fallback") and auto_price_available
            if stale_fallback:
                row["is_manual"] = False
            elif manual.get("currency") == vs_currency:
                row["is_manual"] = True
                row["matched"] = True
                row["price"] = manual["price"]
                row["price_change_24h"] = None
            else:
                row["needs_currency_reentry"] = True
                row["is_manual"] = False
                row.update(matched=False, price=None, price_change_24h=None)
        else:
            row["is_manual"] = False

        enriched.append(row)

    df = pd.DataFrame(enriched)
    df["tokens_pour_capital"] = df["price"].apply(
        lambda p: round(capital / p, 2) if p and p > 0 else None
    )
    # Toujours trié par ordre alphabétique, y compris les clubs saisis à la main.
    df = df.sort_values(by="name", ascending=True).reset_index(drop=True)
    st.session_state["_live_ok"] = live_ok
    st.session_state["_no_token_flags"] = no_token_flags
    return df


# ---------------------------------------------------------------------------
# Sidebar
# ---------------------------------------------------------------------------

st.sidebar.markdown(f'<img src="{SOCIOS_LOGO_URL}" class="sidebar-logo" />', unsafe_allow_html=True)
st.sidebar.title("⚙️ Paramètres")
capital = st.sidebar.number_input("Capital de référence (€)", min_value=1.0, value=100.0, step=10.0)
devise = st.sidebar.selectbox("Devise", ["eur", "usd"], index=0)

if st.sidebar.button("🔄 Rafraîchir clubs & prix"):
    _fetch_teams_cached.clear()
    load_fx_rate.clear()
    load_single_price.clear()
    st.session_state.pop("_price_data_cache", None)
    st.rerun()

df = build_dataframe(capital, devise)

if not st.session_state.get("_live_ok", True):
    st.sidebar.warning(
        "Le scraping en direct de socios.com a échoué (site injoignable ou structure "
        "changée) — liste de clubs de secours utilisée (snapshot du 17/08/2026)."
    )
else:
    st.sidebar.success(f"{len(df)} clubs récupérés en direct depuis socios.com")

if not st.session_state.get("_prices_ok", True):
    st.sidebar.error(
        "Impossible de récupérer les prix depuis fantokens.com pour l'instant "
        "(réseau indisponible, site en rate-limit, ou taux de change USD/EUR "
        "injoignable). Réessaie avec 🔄 dans un instant."
    )
    if st.session_state.get("_prices_error"):
        st.sidebar.caption(f"Détail : {st.session_state['_prices_error']}")

n_matched = int(df["matched"].sum())
n_manual = int(df["is_manual"].sum())
st.sidebar.caption(f"{n_matched}/{len(df)} clubs avec un prix ({n_manual} saisis à la main)")

st.markdown(
    f"""
    <div class="socios-hero">
        <img src="{SOCIOS_LOGO_URL}" />
        <div>
            <h1>⚽ Socios — Rendement des Fan Tokens</h1>
            <p>Prix récupérés sur fantokens.com (converti en {devise.upper()}) · classement basé sur tes points de récompense saisis à la main</p>
        </div>
    </div>
    """,
    unsafe_allow_html=True,
)

metrics = [
    (f"{len(df)}", "Clubs suivis"),
    (f"{n_matched}", "Avec un prix"),
]
if n_manual > 0:
    # Carte masquée s'il n'y a aucun club en saisie manuelle, plutôt que
    # d'afficher "0" en permanence.
    metrics.append((f"{n_manual}", "Prix manuels"))
metrics.append((f"{capital:.0f}{devise.upper()}", "Capital de référence"))

for col, (value, label) in zip(st.columns(len(metrics)), metrics):
    col.markdown(f'<div class="metric-card"><div class="value">{value}</div><div class="label">{label}</div></div>', unsafe_allow_html=True)

st.write("")

tab_dashboard, tab_mapping, tab_ranking, tab_history, tab_portfolio = st.tabs(
    ["📋 Saisie", "🔗 Correspondances tokens", "🏆 Classement", "📈 Évolution", "💼 Mon Portefeuille"]
)

# ---------------------------------------------------------------------------
# Tab 1 : saisie
# ---------------------------------------------------------------------------

with tab_dashboard:
    no_token_flags = st.session_state.get("_no_token_flags", set())
    # Un club est ici tant qu'il n'a AUCUN prix (auto ou manuel), ou tant
    # qu'il est explicitement marqué "aucun token" depuis l'onglet
    # Correspondances. Dès qu'un prix est enregistré ici, "matched" passe à
    # True (cf. build_dataframe) et le club bascule automatiquement dans le
    # tableau du bas au rerun suivant — même case, mêmes infos, pas de
    # doublon ni de désync.
    unmatched_df = df[(~df["matched"]) | (df["name"].isin(no_token_flags))].sort_values("name")

    if not unmatched_df.empty:
        st.markdown('<div class="manual-zone">', unsafe_allow_html=True)
        st.markdown(f"#### 🛠️ {len(unmatched_df)} club(s) en saisie manuelle")
        st.caption(
            "Clubs sans prix trouvé sur fantokens.com (slug introuvable — corrige-le dans "
            "l'onglet Correspondances), ou marqués « aucun token » à la main. Une fois un prix "
            "enregistré ici, il reste dans cette zone (pour pouvoir le corriger plus tard) ET "
            "apparaît aussi dans le tableau principal juste en dessous."
        )
        for _, row in unmatched_df.iterrows():
            with st.form(key=f"quick_form_{row['name']}", border=False):
                c1, c2, c3, c4 = st.columns([0.6, 2.5, 2, 1.2], vertical_alignment="center")
                c1.image(row["logo"], width=32)
                label = row["name"]
                if row.get("needs_currency_reentry"):
                    label += " ⚠️ (devise changée, prix à ressaisir)"
                c2.markdown(f"**{label}**")
                current_price = row["price"] if row.get("is_manual") and pd.notna(row["price"]) else 0.0
                price_val = c3.number_input(
                    f"Prix ({devise.upper()})", min_value=0.0, step=0.001, format="%.5f",
                    value=float(current_price),
                    key=f"quick_price_{row['name']}", label_visibility="collapsed",
                )
                btn_label = "💾 Mettre à jour" if row.get("is_manual") else "💾 Ajouter"
                submitted = c4.form_submit_button(btn_label, use_container_width=True)
                if submitted:
                    if price_val > 0:
                        storage.save_manual_price(row["name"], price_val, devise, is_fallback=True)
                        storage.save_no_token_flag(row["name"], True)
                        # Filet de sécurité en plus de la clé dynamique du champ
                        # Prix en bas (price_{club}_{prix}) : on pré-remplit
                        # nous-mêmes cette clé avec la valeur qu'on vient
                        # d'enregistrer, pour être certain que le tableau du bas
                        # l'affiche dès ce rerun, même si jamais un ancien
                        # session_state traînait encore sous cette même clé.
                        st.session_state[f"price_{row['name']}_{round(price_val, 5)}"] = price_val
                        st.rerun()
                    else:
                        st.toast("Entre un prix supérieur à 0 avant d'enregistrer.", icon="⚠️")
        st.markdown('</div>', unsafe_allow_html=True)

    matched_df = df[df["matched"]].copy().sort_values("name").reset_index(drop=True)

    st.subheader(f"Pour {capital:.0f} {devise.upper()} investis")
    st.caption(
        "Corrige un prix ou saisis les points gagnés/jour directement dans le tableau, puis "
        "clique sur Enregistrer. Le bouton 📋 copie dans le presse-papier le nombre de tokens "
        "(arrondi à l'entier inférieur) pour coller directement dans l'appli Socios."
    )

    latest_entries = storage.get_latest_entry_per_club()
    club_links = storage.get_club_links()
    today = datetime.now().date()

    def _days_since(club):
        entry = latest_entries.get(club)
        if not entry:
            return "Jamais"
        try:
            d = (today - datetime.strptime(entry["entry_date"], "%Y-%m-%d").date()).days
            return "Aujourd'hui" if d == 0 else f"Il y a {d} j"
        except Exception:
            return "—"

    @st.fragment
    def _merged_table_fragment():
        hc = st.columns([0.6, 2.1, 1.2, 0.9, 1.3, 1.2, 1.1, 1.3])
        for c, label in zip(
            hc, ["", "Club", f"Prix ({devise.upper()})", "24h", f"Tokens/{capital:.0f}{devise.upper()}",
                 "Points/jour", "Dernière saisie", "Socios"]
        ):
            c.markdown(f"**{label}**")

        for _, row in matched_df.iterrows():
            club = row["name"]
            c1, c2, c3, c4, c5, c6, c7, c8 = st.columns(
                [0.6, 2.1, 1.2, 0.9, 1.3, 1.2, 1.1, 1.3]
            )
            c1.image(row["logo"], width=30)
            c2.write(club)

            price_val = c3.number_input(
                "Prix", min_value=0.0, step=0.001, format="%.5f",
                value=float(row["price"]) if pd.notna(row["price"]) else 0.0,
                # La clé inclut le prix actuel (pas juste le club) : si ce prix
                # change ailleurs (zone de saisie manuelle du haut, puis rerun
                # complet), Streamlit voit une clé DIFFÉRENTE et recrée le
                # widget avec la nouvelle valeur, au lieu de garder l'ancienne
                # en mémoire indéfiniment. C'est ce qui manquait pour que le
                # tableau du bas suive vraiment ce qui est saisi en haut.
                key=f"price_{club}_{round(float(row['price']), 5) if pd.notna(row['price']) else 0}",
                label_visibility="collapsed",
            )

            change = row.get("price_change_24h")
            if pd.notna(change):
                css_class = "price-up" if change >= 0 else "price-down"
                c4.markdown(f'<span class="{css_class}">{change:+.2f}%</span>', unsafe_allow_html=True)
            else:
                c4.write("—")

            tokens_val = (capital / price_val) if price_val and price_val > 0 else 0.0
            c5.write(f"{tokens_val:.2f}")

            c6.number_input(
                "Points/jour", min_value=0.0, step=0.1, value=0.0,
                key=f"pts_{club}", label_visibility="collapsed",
            )

            c7.caption(_days_since(club))

            # Bouton unique : copie le nombre de tokens (arrondi) dans le presse-papier
            # ET ouvre la page Socios du club, en un seul clic. On utilise
            # components.html (et non st.markdown) car Streamlit retire les
            # attributs onclick du HTML injecté via markdown, même en unsafe_allow_html.
            tokens_floor = int(tokens_val)
            url = club_links.get(club)
            if url:
                btn_html = f'''
                <a href="{url}" target="_blank" rel="noopener" id="btn_{club}"
                   onclick="try{{navigator.clipboard.writeText('{tokens_floor}');
                        this.innerText='✅ Copié';setTimeout(()=>{{this.innerText='🔗 Ouvrir · 📋 {tokens_floor}'}},1200);
                        }}catch(e){{}}"
                   style="display:block;box-sizing:border-box;text-align:center;text-decoration:none;
                   background-color:#1a1d29;color:#f5f6fa;border:1px solid #f107a3;
                   border-radius:6px;padding:0.45rem 0.3rem;font-size:0.8rem;font-family:sans-serif;
                   cursor:pointer;"
                   title="Copie {tokens_floor} dans le presse-papier et ouvre la page Socios">
                   🔗 Ouvrir · 📋 {tokens_floor}</a>'''
            else:
                btn_html = f'''
                <button id="btn_{club}"
                   onclick="try{{navigator.clipboard.writeText('{tokens_floor}');
                        this.innerText='✅ Copié';setTimeout(()=>{{this.innerText='📋 {tokens_floor}'}},1200);
                        }}catch(e){{}}"
                   style="width:100%;box-sizing:border-box;background-color:#1a1d29;color:#f5f6fa;
                   border:1px solid #3a3f52;border-radius:6px;padding:0.45rem 0.3rem;
                   font-size:0.8rem;font-family:sans-serif;cursor:pointer;"
                   title="Pas de lien enregistré — copie {tokens_floor} dans le presse-papier">
                   📋 {tokens_floor}</button>'''
            with c8:
                components.html(btn_html, height=42)

        st.write("")
        if st.button("💾 Enregistrer (prix corrigés + points/jour)", type="primary"):
            price_changes = 0
            entries_to_save = []
            for _, row in matched_df.iterrows():
                club = row["name"]
                old_price = float(row["price"]) if pd.notna(row["price"]) else None
                price_key = f"price_{club}_{round(old_price, 5) if old_price is not None else 0}"
                new_price = st.session_state.get(price_key)
                if new_price and new_price > 0 and (old_price is None or abs(new_price - old_price) > 1e-9):
                    # is_fallback=True pour un club sans prix auto (le prix manuel
                    # cédera la place dès qu'un prix auto redevient disponible),
                    # False pour une correction volontaire d'un prix déjà trouvé
                    # (reste prioritaire indéfiniment).
                    storage.save_manual_price(
                        club, float(new_price), devise, is_fallback=not row.get("auto_matched", False)
                    )
                    price_changes += 1

                pts = st.session_state.get(f"pts_{club}", 0.0)
                if pts and pts > 0:
                    price_for_entry = new_price if new_price and new_price > 0 else old_price
                    tokens_qty = (capital / price_for_entry) if price_for_entry else 0.0
                    entries_to_save.append({
                        "club": club,
                        "tokens_qty": round(tokens_qty, 2),
                        "points_per_day": float(pts),
                        "price_at_entry": price_for_entry,
                    })

            if entries_to_save:
                storage.add_entries_bulk(entries_to_save)

            if price_changes or entries_to_save:
                msg = []
                if price_changes:
                    msg.append(f"{price_changes} prix corrigé(s)")
                if entries_to_save:
                    msg.append(f"{len(entries_to_save)} saisie(s) de points/jour")
                st.success(" et ".join(msg) + f" enregistré(s) le {datetime.now().strftime('%d/%m/%Y')}.")
                st.rerun(scope="app")  # rerun complet : le prix impacte les autres onglets
            else:
                st.toast("Rien à enregistrer.", icon="ℹ️")

    _merged_table_fragment()

# ---------------------------------------------------------------------------
# Tab 2 : correspondances / corrections manuelles
# ---------------------------------------------------------------------------

with tab_mapping:
    st.subheader("Vérifier / corriger les correspondances club → fantokens.com")
    st.caption(
        "Le slug fantokens.com est deviné automatiquement à partir du nom du club "
        "(ex: « Paris Saint-Germain » → paris-saint-germain-fan-token). Quand la "
        "déduction se trompe (sigles, accents...), colle ici le bon slug ou l'URL "
        "complète de la page https://www.fantokens.com/fr/trade/<slug> — un bouton "
        "« Vérifier » interroge fantokens.com avant d'enregistrer, pour être sûr que "
        "ça correspond bien. Coche « aucun token » si le club n'a vraiment aucun "
        "Fan Token (le prix reste alors saisi à la main dans l'onglet Saisie)."
    )
    saved_mappings = storage.get_saved_mappings()
    no_token_flags = storage.get_no_token_flags()
    club_links = storage.get_club_links()

    for _, row in df.iterrows():
        club = row["name"]
        flagged = club in no_token_flags
        current_slug = saved_mappings.get(club) or guess_slug(club)

        cols = st.columns([0.6, 2.2, 2.6, 1.1, 1.5])
        cols[0].image(row["logo"], width=36)
        cols[1].markdown(f"**{club}**" + ("  \n✅ prix trouvé" if row["matched"] else "  \n⚠️ pas de prix"))

        new_slug = cols[2].text_input(
            "Slug fantokens.com", value=current_slug, key=f"slug_{club}",
            label_visibility="collapsed", disabled=flagged,
        )
        # Si un lien complet est collé, on ne garde que le dernier segment de l'URL.
        new_slug = new_slug.strip().rstrip("/").split("/")[-1]

        if cols[3].button("Vérifier", key=f"check_{club}", use_container_width=True, disabled=flagged):
            try:
                found = fetch_fantoken_page(new_slug)
            except Exception as e:
                st.toast(f"Erreur réseau : {e}", icon="⚠️")
                found = None
            if found:
                # Une seule transaction (un seul aller-retour réseau vers la
                # base) au lieu de 3-4 commits séparés : enregistre le slug,
                # lève le flag "aucun token", nettoie l'éventuel prix de
                # secours saisi à la main entre-temps (maintenant qu'un prix
                # automatique est retrouvé, il doit reprendre la main, sinon
                # l'ancien prix manuel continue de tout écraser pour toujours
                # et le compteur "Prix manuels" ne redescend jamais), et
                # enregistre le logo trouvé sur fantokens.com s'il y en a un.
                # Pas besoin de load_teams.clear() : load_teams relit
                # extra_clubs à chaque appel, le nouveau logo apparaît donc
                # dès le prochain rerun sans re-scraper socios.com.
                storage.confirm_verification(club, new_slug, found.get("logo"))
                st.toast(f'Trouvé : {found["name"]} — ${found["price_usd"]:.5f}. Enregistré.', icon="✅")
                st.rerun()
            else:
                st.toast(f"Aucune page fantokens.com/fr/trade/{new_slug} — vérifie le slug.", icon="❌")

        flag_now = cols[4].checkbox("Aucun token", value=flagged, key=f"flag_{club}")
        if flag_now != flagged:
            storage.save_no_token_flag(club, flag_now)
            if flag_now:
                storage.save_mapping(club, None)
            st.rerun()

        with st.expander(f"🔗 Lien direct vers la page Socios de {club}"):
            new_link = st.text_input(
                "URL", value=club_links.get(club, ""), key=f"link_{club}",
                placeholder="https://www.socios.com/...", label_visibility="collapsed",
            )
            if st.button("Enregistrer le lien", key=f"link_save_{club}"):
                storage.save_club_link(club, new_link.strip() or None)
                st.toast(f"Lien enregistré pour {club}." if new_link.strip() else f"Lien retiré pour {club}.", icon="🔗")
                # Sans ce rerun, le nouveau lien restait invisible dans
                # l'onglet Saisie (bouton "🔗 Ouvrir") : ce bouton est construit
                # avec club_links, qui est lu une seule fois tout en haut du
                # script — AVANT que ce clic n'ait lieu. Il fallait donc
                # attendre une autre action ailleurs pour que le lien
                # apparaisse. C'est le même schéma que "Vérifier" /
                # "Aucun token" juste au-dessus : on force le rerun ici aussi.
                st.rerun()

    st.divider()
    st.markdown("#### ➕ Ajouter un club manquant")
    st.caption(
        "Le scraping de socios.com peut passer à côté de certains clubs. Ajoute-le ici "
        "à la main (nom exact + slug fantokens.com, comme pour vérifier un prix ci-dessus) "
        "— le logo est récupéré automatiquement depuis la même page fantokens.com, pas "
        "besoin de le chercher/coller toi-même."
    )
    with st.form("add_manual_club", border=False):
        ac1, ac2, ac3 = st.columns([2, 3, 1.2])
        new_club_name = ac1.text_input("Nom du club", placeholder="Ex: AS Saint-Étienne")
        new_club_slug = ac2.text_input(
            "Slug fantokens.com", placeholder="ex: as-saint-etienne-fan-token (ou URL complète)"
        )
        # Le bouton n'a pas de label au-dessus de lui contrairement aux deux
        # champs texte -> sans ce spacer invisible de la même hauteur qu'un
        # label Streamlit, il remonte et n'est plus aligné avec les inputs.
        ac3.markdown(
            "<div style='height: 1.9rem;'></div>", unsafe_allow_html=True
        )
        add_submitted = ac3.form_submit_button("Ajouter", use_container_width=True)
        if add_submitted:
            name = new_club_name.strip()
            slug = new_club_slug.strip().rstrip("/").split("/")[-1]
            if not name or not slug:
                st.warning("Nom et slug fantokens.com sont obligatoires.")
            else:
                try:
                    found = fetch_fantoken_page(slug)
                except Exception as e:
                    found = None
                    st.error(f"Erreur réseau en vérifiant le slug : {e}")
                if found is None:
                    st.error(
                        f"Aucune page fantokens.com/fr/trade/{slug} trouvée — vérifie le slug "
                        "(colle l'URL complète de la page si besoin)."
                    )
                else:
                    logo = found.get("logo")
                    # Une seule transaction pour les deux écritures. Pas de
                    # load_teams.clear() : load_teams relit extra_clubs à
                    # chaque appel, le club apparaît dès le prochain rerun
                    # sans re-scraper socios.com.
                    storage.add_manual_club(name, slug, logo or SOCIOS_LOGO_URL)
                    if logo:
                        st.success(f"« {name} » ajouté avec son logo et son prix ({slug}).")
                    else:
                        st.warning(
                            f"« {name} » ajouté avec son prix ({slug}), mais aucun logo trouvé "
                            "sur la page — logo Socios générique utilisé en attendant."
                        )
                    st.rerun()

    extra_clubs = storage.get_extra_clubs()
    if extra_clubs:
        st.caption("Clubs ajoutés à la main :")
        for name, logo in extra_clubs.items():
            rc1, rc2, rc3 = st.columns([0.6, 3, 1])
            rc1.image(logo, width=30)
            rc2.write(name)
            if rc3.button("🗑️ Retirer", key=f"del_extra_{name}"):
                storage.delete_extra_club(name)
                st.rerun()

# ---------------------------------------------------------------------------
# Tab 3 : classement
# ---------------------------------------------------------------------------

with tab_ranking:
    st.subheader("Classement des clubs les plus rentables")
    latest = storage.get_latest_entry_per_club()

    if not latest:
        st.info("Aucune saisie pour l'instant — va dans l'onglet **Saisie** pour commencer.")
    else:
        price_by_club = dict(zip(df["name"], df["price"]))
        logo_by_club = dict(zip(df["name"], df["logo"]))
        rows = []
        for club, entry in latest.items():
            current_price = price_by_club.get(club)
            if not current_price or entry["tokens_qty"] <= 0:
                continue
            rate_per_token = entry["points_per_day"] / entry["tokens_qty"]
            tokens_now = capital / current_price
            rendement_now = rate_per_token * tokens_now
            rows.append(
                {
                    "Club": club,
                    "Prix actuel": round(current_price, 5),
                    "Dernière saisie": entry["entry_date"],
                    "Points/jour saisis": entry["points_per_day"],
                    f"Points/jour pour {capital:.0f}{devise.upper()} (actualisé)": round(rendement_now, 3),
                }
            )
        if rows:
            rank_col = "Points/jour saisis"  # classement basé sur ce que tu as toi-même saisi
            rank_df = pd.DataFrame(rows).sort_values(rank_col, ascending=False)
            rank_df.insert(0, "#", range(1, len(rank_df) + 1))

            # Comparaison avec le dernier classement connu (mis à jour une fois par
            # jour) pour afficher qui a monté / baissé / stagné depuis la dernière fois.
            today_str = datetime.now().strftime("%Y-%m-%d")
            prev_snapshot = storage.get_rank_snapshot()
            current_positions = dict(zip(rank_df["Club"], rank_df["#"]))

            def _movement(club):
                prev = prev_snapshot.get(club)
                if not prev:
                    return "🆕 Nouveau"
                delta = prev["position"] - current_positions[club]  # positif = a monté
                if delta > 0:
                    return f"▲ +{delta}"
                elif delta < 0:
                    return f"▼ {delta}"
                else:
                    return "="

            rank_df["Évolution"] = rank_df["Club"].apply(_movement)

            # On ne réécrit le snapshot que si la référence stockée date d'avant
            # aujourd'hui (sinon rouvrir la page toute la journée écraserait la
            # comparaison en la comparant à elle-même).
            snapshot_dates = {v["date"] for v in prev_snapshot.values()}
            if not snapshot_dates or snapshot_dates != {today_str}:
                storage.save_rank_snapshot(current_positions, today_str)

            leader = rank_df.iloc[0]
            lc1, lc2 = st.columns([0.15, 0.85])
            with lc1:
                st.image(logo_by_club.get(leader["Club"]), width=70)
            with lc2:
                st.markdown(
                    f"##### 🥇 Meilleur rendement actuel : **{leader['Club']}**  \n"
                    f"{leader[rank_col]:.1f} points/jour saisis"
                )

            top = rank_df.head(10).copy().sort_values(rank_col, ascending=True)
            st.markdown("##### 🏆 Top 10 — points/jour saisis")
            # st.bar_chart ne garantissait pas l'ordre des barres — on force le tri
            # explicitement via Altair (sort par valeur décroissante, du haut vers le bas).
            import altair as alt
            chart = (
                alt.Chart(top)
                .mark_bar(color="#f107a3")
                .encode(
                    x=alt.X(f"{rank_col}:Q", title=rank_col),
                    y=alt.Y("Club:N", sort=alt.EncodingSortField(field=rank_col, order="descending"), title=None),
                )
                .properties(height=32 * len(top))
            )
            st.altair_chart(chart, use_container_width=True)

            st.markdown("##### Classement complet")
            display_cols = ["#", "Évolution", "Club", "Prix actuel", "Dernière saisie", rank_col]
            st.dataframe(
                rank_df[display_cols],
                hide_index=True,
                use_container_width=True,
                column_config={
                    rank_col: st.column_config.ProgressColumn(
                        rank_col, format="%.1f",
                        min_value=0.0, max_value=float(rank_df[rank_col].max()),
                    ),
                },
            )
        else:
            st.info("Pas encore assez de données avec prix connu pour établir un classement.")

# ---------------------------------------------------------------------------
# Tab 4 : évolution dans le temps
# ---------------------------------------------------------------------------

with tab_history:
    st.subheader("Évolution du rendement dans le temps")
    all_entries = storage.get_all_entries()
    if not all_entries:
        st.info("Aucun historique pour l'instant.")
    else:
        hist_df = pd.DataFrame([dict(r) for r in all_entries])
        clubs = sorted(hist_df["club"].unique())

        @st.fragment
        def _evolution_fragment():
            chosen = st.multiselect("Clubs à afficher", clubs, default=clubs[: min(5, len(clubs))])
            if chosen:
                plot_df = hist_df[hist_df["club"].isin(chosen)][
                    ["entry_date", "club", "points_per_day"]
                ].sort_values("entry_date")
                # Points + lignes (visible même avec une seule date par club, contrairement
                # à st.line_chart qui n'affiche rien s'il n'y a qu'un point).
                import altair as alt
                base = alt.Chart(plot_df).encode(
                    x=alt.X("entry_date:N", title="Date"),
                    y=alt.Y("points_per_day:Q", title="Points / jour saisis"),
                    color=alt.Color("club:N", title="Club"),
                )
                chart = (base.mark_line(point=True) + base.mark_point(size=60)).properties(height=380)
                st.altair_chart(chart, use_container_width=True)
                st.caption("Points de récompense par jour tels que tu les as saisis, sans recalcul.")
            else:
                st.info("Sélectionne au moins un club pour afficher le graphique.")

        _evolution_fragment()
        with st.expander("Voir toutes les saisies (modifier ou supprimer une entrée)"):
            st.caption("Tu peux corriger une valeur erronée directement dans les cases ci-dessous, puis Enregistrer.")
            hist_edit_df = pd.DataFrame([dict(r) for r in all_entries])[
                ["id", "club", "entry_date", "tokens_qty", "points_per_day"]
            ].rename(columns={
                "id": "ID", "club": "Club", "entry_date": "Date",
                "tokens_qty": "Tokens", "points_per_day": "Points/jour",
            })
            edited_hist = st.data_editor(
                hist_edit_df,
                column_config={
                    "ID": st.column_config.NumberColumn(disabled=True),
                    "Club": st.column_config.TextColumn(disabled=True),
                    "Date": st.column_config.TextColumn(help="Format AAAA-MM-JJ"),
                    "Tokens": st.column_config.NumberColumn(min_value=0.0, step=0.01),
                    "Points/jour": st.column_config.NumberColumn(min_value=0.0, step=0.1),
                },
                hide_index=True,
                use_container_width=True,
                key="history_editor",
            )
            if st.button("💾 Enregistrer les corrections d'historique"):
                changed = 0
                for i in edited_hist.index:
                    orig = hist_edit_df.loc[i]
                    new = edited_hist.loc[i]
                    if (new["Tokens"] != orig["Tokens"] or new["Points/jour"] != orig["Points/jour"]
                            or new["Date"] != orig["Date"]):
                        storage.update_entry(
                            int(new["ID"]), float(new["Tokens"]), float(new["Points/jour"]), str(new["Date"])
                        )
                        changed += 1
                if changed:
                    st.success(f"{changed} saisie(s) corrigée(s).")
                    st.rerun()
                else:
                    st.info("Aucune modification détectée.")

            st.markdown("###### Supprimer une saisie")
            for r in all_entries:
                c1, c2, c3, c4, c5 = st.columns([2, 2, 2, 2, 1])
                c1.write(r["club"])
                c2.write(r["entry_date"])
                c3.write(f'{r["tokens_qty"]} tokens')
                c4.write(f'{r["points_per_day"]} pts/j')
                if c5.button("🗑️", key=f"del_{r['id']}"):
                    storage.delete_entry(r["id"])
                    st.rerun()

# ---------------------------------------------------------------------------
# Tab 5 : mon portefeuille réel (tokens réellement détenus + points gagnés/jour)
# ---------------------------------------------------------------------------

with tab_portfolio:
    st.subheader("💼 Mes tokens détenus")
    st.caption(
        "Indépendant du tableau « Saisie » ci-dessus (qui simule pour un capital de "
        f"référence). Ici tu déclares ce que tu possèdes réellement, puis tu notes "
        "chaque jour combien un token t'a rapporté (le rendement varie d'un jour à l'autre). "
        "Ce portefeuille est **privé** : seul toi peux le voir et le modifier."
    )

    _pf_username = st.session_state["auth_user"]["username"]

    all_club_names = sorted(df["name"].unique().tolist()) if not df.empty else []
    holdings = storage.get_portfolio_holdings(_pf_username)
    latest_points = storage.get_portfolio_latest_points(_pf_username)

    @st.fragment
    def _portfolio_holdings_fragment():
        st.markdown("###### Ajouter / mettre à jour un token détenu")
        c1, c2, c3 = st.columns([3, 1.5, 1])
        club_choice = c1.selectbox(
            "Club", all_club_names, key="_pf_add_club", label_visibility="collapsed",
            placeholder="Choisir un club...", index=None,
        )
        qty_choice = c2.number_input(
            "Quantité détenue", min_value=0.0, step=1.0, key="_pf_add_qty",
            label_visibility="collapsed", placeholder="Quantité",
        )
        if c3.button("💾 Enregistrer", key="_pf_add_btn", use_container_width=True):
            if club_choice and qty_choice > 0:
                storage.set_portfolio_holding(_pf_username, club_choice, float(qty_choice))
                st.success(f"{club_choice} : {qty_choice} tokens enregistrés.")
                st.rerun(scope="fragment")
            else:
                st.toast("Choisis un club et une quantité supérieure à 0.", icon="⚠️")

        if not holdings:
            st.info("Aucun token ajouté pour l'instant.")
            return

        st.write("")
        st.markdown("###### Points gagnés par token")
        pf_entry_date = st.date_input(
            "Date de la saisie", value=datetime.now().date(), key="_pf_shared_date",
        )
        for club in sorted(holdings.keys()):
            qty = holdings[club]
            last = latest_points.get(club)
            hc1, hc2, hc3 = st.columns([2.2, 1, 1.3])
            hc1.write(f"**{club}**")
            hc2.caption(f"{qty:g} tokens")
            default_pts = (
                last["points_earned"]
                if last and last["entry_date"] == pf_entry_date.strftime("%Y-%m-%d")
                else 0.0
            )
            hc3.number_input(
                "Points gagnés", min_value=0.0, step=0.1, value=float(default_pts),
                key=f"_pf_pts_{club}_{pf_entry_date.isoformat()}", label_visibility="collapsed",
            )
            if last:
                hc1.caption(f"Dernière saisie : {last['entry_date']} → {last['points_earned']} pts")

        if st.button("💾 Enregistrer les points du jour", type="primary", key="_pf_save_all"):
            saved = 0
            for club in holdings.keys():
                pts_val = st.session_state.get(f"_pf_pts_{club}_{pf_entry_date.isoformat()}", 0.0)
                if pts_val and pts_val > 0:
                    storage.upsert_portfolio_daily_points(
                        _pf_username, club, pf_entry_date.strftime("%Y-%m-%d"), float(pts_val)
                    )
                    saved += 1
            if saved:
                st.success(f"{saved} token(s) enregistré(s) pour le {pf_entry_date.strftime('%d/%m/%Y')}.")
                st.rerun(scope="fragment")
            else:
                st.toast("Aucun point à enregistrer (tous à 0).", icon="ℹ️")

        st.write("")
        with st.expander("Retirer un token du portefeuille"):
            for club in sorted(holdings.keys()):
                rc1, rc2 = st.columns([4, 1])
                rc1.write(f"{club} — {holdings[club]:g} tokens")
                if rc2.button("🗑️", key=f"_pf_del_{club}"):
                    storage.delete_portfolio_holding(_pf_username, club)
                    st.rerun(scope="fragment")

    _portfolio_holdings_fragment()

    st.divider()
    st.subheader("📊 Stats de staking")

    pf_history = storage.get_portfolio_history(_pf_username)
    if not pf_history:
        st.info("Aucune saisie de points pour l'instant — ajoute des tokens et note leurs points/jour ci-dessus.")
    else:
        pf_df = pd.DataFrame(pf_history)
        pf_clubs = sorted(pf_df["club"].unique())

        totals_by_date = pf_df.groupby("entry_date")["points_earned"].sum().reset_index()
        last_date = totals_by_date["entry_date"].max()
        total_last_day = totals_by_date.loc[totals_by_date["entry_date"] == last_date, "points_earned"].sum()

        mcol1, mcol2 = st.columns(2)
        mcol1.markdown(
            f'<div class="metric-card"><div class="value">{total_last_day:g}</div>'
            f'<div class="label">Total points/jour ({last_date})</div></div>',
            unsafe_allow_html=True,
        )
        mcol2.markdown(
            f'<div class="metric-card"><div class="value">{len(pf_clubs)}</div>'
            f'<div class="label">Tokens suivis</div></div>',
            unsafe_allow_html=True,
        )
        st.write("")

        st.markdown("###### Total staké par jour (tous tokens confondus)")
        import altair as alt
        total_chart = alt.Chart(totals_by_date).encode(
            x=alt.X("entry_date:N", title="Date"),
            y=alt.Y("points_earned:Q", title="Total points/jour"),
        )
        st.altair_chart(
            (total_chart.mark_line(point=True) + total_chart.mark_point(size=60)).properties(height=320),
            use_container_width=True,
        )

        st.markdown("###### Évolution par token")

        @st.fragment
        def _portfolio_stats_fragment():
            chosen_pf = st.multiselect(
                "Tokens à afficher", pf_clubs, default=pf_clubs[: min(5, len(pf_clubs))],
                key="_pf_stats_clubs",
            )
            if chosen_pf:
                plot_pf = pf_df[pf_df["club"].isin(chosen_pf)][["entry_date", "club", "points_earned"]]
                base = alt.Chart(plot_pf).encode(
                    x=alt.X("entry_date:N", title="Date"),
                    y=alt.Y("points_earned:Q", title="Points gagnés"),
                    color=alt.Color("club:N", title="Token"),
                )
                chart = (base.mark_line(point=True) + base.mark_point(size=60)).properties(height=380)
                st.altair_chart(chart, use_container_width=True)
            else:
                st.info("Sélectionne au moins un token pour afficher le graphique.")

        _portfolio_stats_fragment()

        with st.expander("Voir tout l'historique (supprimer une saisie)"):
            hist_pf_df = pf_df[["id", "club", "entry_date", "points_earned"]].rename(columns={
                "id": "ID", "club": "Token", "entry_date": "Date", "points_earned": "Points",
            }).sort_values("Date", ascending=False)
            st.dataframe(hist_pf_df, hide_index=True, use_container_width=True)
            st.markdown("###### Supprimer une saisie")
            for r in sorted(pf_history, key=lambda x: x["entry_date"], reverse=True):
                dc1, dc2, dc3, dc4 = st.columns([2, 2, 2, 1])
                dc1.write(r["club"])
                dc2.write(r["entry_date"])
                dc3.write(f'{r["points_earned"]} pts')
                if dc4.button("🗑️", key=f"_pf_del_hist_{r['id']}"):
                    storage.delete_portfolio_entry(_pf_username, r["id"])
                    st.rerun()
