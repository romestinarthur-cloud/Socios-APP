import pandas as pd
import streamlit as st
from datetime import datetime

import storage
from teams_scraper import get_teams
from prices import fetch_all_candidate_tokens, match_teams_to_tokens

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
       au contenu pendant qu'un rechargement (rerun) est en cours. */
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

# ---------------------------------------------------------------------------
# Chargement des données (cache 1h pour ne pas spammer socios.com / CoinGecko)
# ---------------------------------------------------------------------------

@st.cache_data(ttl=3600, show_spinner="Récupération des clubs sur socios.com...")
def load_teams():
    return get_teams()


@st.cache_data(ttl=900, show_spinner="Récupération des prix sur CoinGecko...")
def load_prices(vs_currency: str):
    return fetch_all_candidate_tokens(vs_currency=vs_currency)


def build_dataframe(capital: float, vs_currency: str) -> pd.DataFrame:
    teams, live_ok = load_teams()
    try:
        candidates = load_prices(vs_currency)
        prices_ok = True
    except Exception as e:
        candidates = []
        prices_ok = False
        st.session_state["_prices_error"] = str(e)
    st.session_state["_prices_ok"] = prices_ok

    saved_mappings = storage.get_saved_mappings()
    no_token_flags = storage.get_no_token_flags()
    manual_prices = storage.get_manual_prices()  # club -> {"price":..., "currency":...}

    enriched = match_teams_to_tokens(teams, candidates)
    cand_by_id = {c["id"]: c for c in candidates}

    for row in enriched:
        club = row["name"]

        if club in no_token_flags:
            # Marqué "aucun token trouvé" à la main : on ignore complètement le
            # matching automatique et toute correspondance sauvegardée pour ce
            # club, tant que ce drapeau n'est pas retiré dans l'onglet dédié.
            row.update(
                matched=False, match_score=None, token_id=None,
                token_symbol=None, price=None, price_change_24h=None,
            )
        else:
            override = saved_mappings.get(club)
            if override and override in cand_by_id:
                coin = cand_by_id[override]
                row.update(
                    matched=True,
                    token_id=coin["id"],
                    token_symbol=coin["symbol"].upper(),
                    price=coin.get("current_price"),
                    price_change_24h=coin.get("price_change_percentage_24h"),
                )
            # sinon : on garde le matching automatique déjà fait par match_teams_to_tokens

        # Prix saisi à la main : ne s'applique que si sa devise correspond à la
        # devise actuellement sélectionnée. Sinon un prix tapé en EUR serait
        # affiché tel quel comme un prix USD (ou l'inverse) — donc on le
        # neutralise et on demande une ressaisie plutôt que de l'utiliser.
        manual = manual_prices.get(club)
        row["needs_currency_reentry"] = False
        if manual is not None and manual.get("price") is not None:
            if manual.get("currency") == vs_currency:
                row["is_manual"] = True
                row["matched"] = True
                row["match_score"] = None
                row["price"] = manual["price"]
                row["price_change_24h"] = None
                if club in no_token_flags:
                    # Pas de vrai token pour ce club : le prix manuel EST le token.
                    row["token_id"] = None
                    row["token_symbol"] = "manuel"
                else:
                    # Le token a bien été trouvé (auto ou correspondance choisie) :
                    # on garde son id/symbole, on corrige juste le prix affiché.
                    row["token_symbol"] = f'{row.get("token_symbol") or "?"} (corrigé)'
            else:
                row["needs_currency_reentry"] = True
                row["is_manual"] = False
                row.update(
                    matched=False, token_id=None, token_symbol=None,
                    price=None, price_change_24h=None,
                )
        else:
            row["is_manual"] = False

    df = pd.DataFrame(enriched)
    df["tokens_pour_capital"] = df["price"].apply(
        lambda p: round(capital / p, 2) if p and p > 0 else None
    )
    # Toujours trié par ordre alphabétique, y compris les clubs saisis à la main.
    df = df.sort_values(by="name", ascending=True).reset_index(drop=True)
    st.session_state["_live_ok"] = live_ok
    st.session_state["_candidates"] = candidates
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
    load_teams.clear()
    load_prices.clear()
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
        "Impossible de récupérer les prix depuis CoinGecko pour l'instant "
        "(réseau indisponible ou API en rate-limit). Réessaie avec 🔄 dans un instant."
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
            <p>Prix via l'API publique CoinGecko · classement basé sur tes points de récompense saisis à la main</p>
        </div>
    </div>
    """,
    unsafe_allow_html=True,
)

m1, m2, m3, m4 = st.columns(4)
for col, value, label in [
    (m1, f"{len(df)}", "Clubs suivis"),
    (m2, f"{n_matched}", "Avec un prix"),
    (m3, f"{n_manual}", "Prix manuels"),
    (m4, f"{capital:.0f}{devise.upper()}", "Capital de référence"),
]:
    col.markdown(f'<div class="metric-card"><div class="value">{value}</div><div class="label">{label}</div></div>', unsafe_allow_html=True)

st.write("")

tab_dashboard, tab_mapping, tab_ranking, tab_history = st.tabs(
    ["📋 Saisie", "🔗 Correspondances tokens", "🏆 Classement", "📈 Évolution"]
)

# ---------------------------------------------------------------------------
# Tab 1 : saisie
# ---------------------------------------------------------------------------

with tab_dashboard:
    no_token_flags = st.session_state.get("_no_token_flags", set())
    # Un club reste dans cette zone de saisie tant qu'il est marqué "aucun token
    # trouvé" (même après avoir déjà un prix) — pour pouvoir changer la valeur
    # à tout moment — ou tant qu'il n'a toujours aucun prix du tout.
    unmatched_df = df[(~df["matched"]) | (df["name"].isin(no_token_flags))].sort_values("name")

    if not unmatched_df.empty:
        st.markdown('<div class="manual-zone">', unsafe_allow_html=True)
        st.markdown(f"#### 🛠️ {len(unmatched_df)} club(s) en saisie manuelle")
        st.caption(
            "Clubs sans correspondance automatique, ou marqués « aucun token trouvé » dans "
            "l'onglet Correspondances. Ils restent ici pour pouvoir changer le prix, et "
            "apparaissent aussi dans le tableau ci-dessous dès qu'un prix est enregistré."
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
                        storage.save_manual_price(row["name"], price_val, devise)
                        storage.save_no_token_flag(row["name"], True)
                        st.rerun()
                    else:
                        st.toast("Entre un prix supérieur à 0 avant d'enregistrer.", icon="⚠️")
        st.markdown('</div>', unsafe_allow_html=True)

    matched_df = df[df["matched"]].copy()
    matched_df["24h"] = matched_df["price_change_24h"]

    st.subheader(f"Pour {capital:.0f} {devise.upper()} investis")
    st.caption("Tu peux corriger un prix directement dans la colonne « Prix » ci-dessous, puis cliquer sur Enregistrer.")

    price_col = f"Prix ({devise.upper()})"

    @st.fragment
    def _price_editor_fragment():
        display_df = matched_df[["logo", "name", "token_symbol", "price", "24h", "tokens_pour_capital"]].rename(
            columns={
                "logo": "Logo",
                "name": "Club",
                "token_symbol": "Token",
                "price": price_col,
                "24h": "24h",
                "tokens_pour_capital": f"Tokens pour {capital:.0f}{devise.upper()}",
            }
        )
        edited_df = st.data_editor(
            display_df,
            column_config={
                "Logo": st.column_config.ImageColumn("Logo", width="small"),
                "Club": st.column_config.TextColumn(disabled=True),
                "Token": st.column_config.TextColumn(disabled=True),
                price_col: st.column_config.NumberColumn(format="%.5f", min_value=0.0, step=0.001),
                "24h": st.column_config.NumberColumn(disabled=True, format="%.2f%%"),
                f"Tokens pour {capital:.0f}{devise.upper()}": st.column_config.NumberColumn(disabled=True),
            },
            disabled=["Logo"],
            hide_index=True,
            use_container_width=True,
            key="matched_price_editor",
        )
        if st.button("💾 Enregistrer les prix corrigés"):
            changed = 0
            for i in edited_df.index:
                new_price = edited_df.loc[i, price_col]
                old_price = display_df.loc[i, price_col]
                if pd.notna(new_price) and new_price != old_price and new_price > 0:
                    storage.save_manual_price(edited_df.loc[i, "Club"], float(new_price), devise)
                    changed += 1
            if changed:
                st.rerun(scope="app")  # rerun complet nécessaire : le prix impacte d'autres onglets
            else:
                st.toast("Aucun prix modifié.", icon="ℹ️")

    _price_editor_fragment()

    st.divider()
    st.markdown("#### Saisir les points gagnés / jour")
    st.caption(
        "Pour chaque club, rentre le nombre de points de récompense (Reward Points) que "
        "l'appli Socios t'affiche par jour, pour le nombre de tokens indiqué ci-dessus. "
        "Les clubs les moins récemment mis à jour sont en haut, pour savoir par où commencer."
    )

    latest_entries = storage.get_latest_entry_per_club()
    today = datetime.now().date()

    def _days_since(club):
        entry = latest_entries.get(club)
        if not entry:
            return 99999  # jamais saisi -> tout en haut
        try:
            d = datetime.strptime(entry["entry_date"], "%Y-%m-%d").date()
            return (today - d).days
        except Exception:
            return 99999

    input_rows = matched_df[["name", "price", "tokens_pour_capital"]].copy()
    input_rows["_days"] = input_rows["name"].apply(_days_since)
    input_rows["Dernière saisie"] = input_rows["_days"].apply(
        lambda d: "Jamais" if d >= 99999 else ("Aujourd'hui" if d == 0 else f"Il y a {d} j")
    )
    # Ordre alphabétique fixe (le tri par ancienneté changeait l'ordre de façon
    # déroutante d'une saisie à l'autre) — la colonne "Dernière saisie" suffit
    # pour repérer visuellement ceux à mettre à jour en premier.
    input_rows = input_rows.sort_values("name").drop(columns=["_days"])
    input_rows["points_par_jour"] = None

    @st.fragment
    def _saisie_fragment():
        input_edited = st.data_editor(
            input_rows.rename(
                columns={
                    "name": "Club",
                    "price": "Prix",
                    "tokens_pour_capital": "Nb tokens",
                }
            ),
            column_config={
                "Club": st.column_config.TextColumn(disabled=True),
                "Prix": st.column_config.NumberColumn(disabled=True, format="%.5f"),
                "Nb tokens": st.column_config.NumberColumn(disabled=True),
                "Dernière saisie": st.column_config.TextColumn(disabled=True),
                "points_par_jour": st.column_config.NumberColumn("Points / jour", min_value=0.0, step=0.1),
            },
            column_order=["Club", "Dernière saisie", "Prix", "Nb tokens", "points_par_jour"],
            hide_index=True,
            use_container_width=True,
            key="input_table",
        )

        if st.button("💾 Enregistrer les saisies", type="primary"):
            to_save = [
                {
                    "club": r["Club"],
                    "tokens_qty": float(r["Nb tokens"]),
                    "points_per_day": float(r["points_par_jour"]),
                    "price_at_entry": float(r["Prix"]) if pd.notna(r["Prix"]) else None,
                }
                for _, r in input_edited.iterrows()
                if pd.notna(r["points_par_jour"]) and r["points_par_jour"] not in (None, 0)
            ]
            if to_save:
                storage.add_entries_bulk(to_save)  # une seule requête pour tout le lot
                st.success(f"{len(to_save)} saisie(s) enregistrée(s) le {datetime.now().strftime('%d/%m/%Y')}.")
            else:
                st.warning("Aucune valeur de points/jour renseignée.")

    _saisie_fragment()

# ---------------------------------------------------------------------------
# Tab 2 : correspondances / corrections manuelles
# ---------------------------------------------------------------------------

with tab_mapping:
    st.subheader("Vérifier / corriger les correspondances club → token")
    st.caption(
        "Choisis « — aucun — » pour un club sans le bon token : il part automatiquement "
        "dans la zone de saisie manuelle de l'onglet Saisie, où tu rentres son prix à la main."
    )
    candidates = st.session_state.get("_candidates", [])
    options = {"— aucun —": None}
    options.update({f'{c["name"]} ({c["symbol"].upper()})': c["id"] for c in candidates})

    saved_mappings = storage.get_saved_mappings()
    no_token_flags = storage.get_no_token_flags()

    for _, row in df.iterrows():
        club = row["name"]
        flagged = club in no_token_flags

        cols = st.columns([1, 3, 4])
        cols[0].image(row["logo"], width=40)
        cols[1].markdown(f"**{club}**")

        current_id = None if flagged else saved_mappings.get(club, row["token_id"])
        current_label = next((k for k, v in options.items() if v == current_id), "— aucun —")
        choice = cols[2].selectbox(
            "Token", list(options.keys()), index=list(options.keys()).index(current_label),
            key=f"map_{club}", label_visibility="collapsed",
        )
        new_id = options[choice]

        if new_id is None and (not flagged or current_id is not None):
            # "— aucun —" choisi : le club part en saisie manuelle dans l'onglet Saisie.
            storage.save_no_token_flag(club, True)
            storage.save_mapping(club, None)
            st.rerun()
        elif new_id is not None and (flagged or new_id != saved_mappings.get(club, row["token_id"])):
            # Un vrai token choisi : on retire le drapeau "aucun token" s'il y était,
            # et on enregistre la correspondance.
            storage.save_no_token_flag(club, False)
            storage.save_mapping(club, new_id)
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
            rank_col = f"Points/jour pour {capital:.0f}{devise.upper()} (actualisé)"
            rank_df = pd.DataFrame(rows).sort_values(rank_col, ascending=False)
            rank_df.insert(0, "#", range(1, len(rank_df) + 1))

            leader = rank_df.iloc[0]
            lc1, lc2 = st.columns([0.15, 0.85])
            with lc1:
                st.image(logo_by_club.get(leader["Club"]), width=70)
            with lc2:
                st.markdown(
                    f"##### 🥇 Meilleur rendement actuel : **{leader['Club']}**  \n"
                    f"{leader[rank_col]:.3f} points/jour pour {capital:.0f}{devise.upper()} investis"
                )

            top = rank_df.head(10).copy().sort_values(rank_col, ascending=True)
            st.markdown("##### 🏆 Top 10 — points/jour actualisés")
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
            st.dataframe(
                rank_df,
                hide_index=True,
                use_container_width=True,
                column_config={
                    rank_col: st.column_config.ProgressColumn(
                        rank_col, format="%.3f",
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
        # Rendement en équivalent "points/jour pour ton capital", pas juste par token
        # (brut par token = illisible, les échelles varient trop d'un club à l'autre).
        hist_df["rendement_capital"] = hist_df.apply(
            lambda r: (r["points_per_day"] / r["tokens_qty"]) * (capital / r["price_at_entry"])
            if r.get("price_at_entry") and r["price_at_entry"] > 0 else None,
            axis=1,
        )
        hist_df = hist_df.dropna(subset=["rendement_capital"])
        clubs = sorted(hist_df["club"].unique())

        @st.fragment
        def _evolution_fragment():
            chosen = st.multiselect("Clubs à afficher", clubs, default=clubs[: min(5, len(clubs))])
            if chosen:
                plot_df = hist_df[hist_df["club"].isin(chosen)][
                    ["entry_date", "club", "rendement_capital"]
                ].sort_values("entry_date")
                # Points + lignes (visible même avec une seule date par club, contrairement
                # à st.line_chart qui n'affiche rien s'il n'y a qu'un point).
                import altair as alt
                base = alt.Chart(plot_df).encode(
                    x=alt.X("entry_date:N", title="Date"),
                    y=alt.Y("rendement_capital:Q", title=f"Points/jour pour {capital:.0f}{devise.upper()}"),
                    color=alt.Color("club:N", title="Club"),
                )
                chart = (base.mark_line(point=True) + base.mark_point(size=60)).properties(height=380)
                st.altair_chart(chart, use_container_width=True)
                st.caption(f"Points de récompense par jour, pour l'équivalent de {capital:.0f}{devise.upper()} investis (au prix du token à la date de chaque saisie).")
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
