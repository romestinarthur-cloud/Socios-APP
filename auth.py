"""
Système de login très simple pour restreindre l'accès à l'appli.

- Le super admin est créé automatiquement au premier lancement à partir des
  Secrets Streamlit ADMIN_USERNAME / ADMIN_PASSWORD (à définir dans
  Streamlit Cloud > Settings > Secrets, jamais dans le code).
- Le super admin peut ensuite créer/supprimer des comptes depuis un panneau
  dans la barre latérale ("👤 Comptes").
- Les mots de passe ne sont jamais stockés en clair (hash PBKDF2 + sel par
  utilisateur, table app_users dans la base Postgres).
"""

import streamlit as st

import storage


def _login_form():
    st.markdown(
        """
        <div style="display:flex;justify-content:center;margin-top:8vh;">
        </div>
        """,
        unsafe_allow_html=True,
    )
    col = st.columns([1, 1, 1])[1]
    with col:
        st.markdown("## 🔒 Connexion")
        with st.form("login_form", clear_on_submit=False):
            username = st.text_input("Identifiant")
            password = st.text_input("Mot de passe", type="password")
            submitted = st.form_submit_button("Se connecter", use_container_width=True)
        if submitted:
            # Retour visuel immédiat : sans ça, l'écran ne bouge pas pendant
            # la vérification + le chargement complet de l'appli qui suit,
            # et on croit que la touche Entrée / le clic n'a rien fait.
            with st.spinner("Connexion..."):
                user = storage.verify_user(username, password)
            if user:
                st.session_state["auth_user"] = user
                st.rerun()
            else:
                st.error("Identifiant ou mot de passe incorrect.")


def _user_management_panel():
    """Panneau visible uniquement par les administrateurs pour créer /
    supprimer des comptes."""
    with st.sidebar.expander("👤 Comptes", expanded=False):
        st.caption(f"Connecté en tant que **{st.session_state['auth_user']['username']}**")

        st.markdown("**Créer un accès**")
        new_username = st.text_input("Nouvel identifiant", key="_new_username")
        new_password = st.text_input(
            "Nouveau mot de passe", type="password", key="_new_password"
        )
        new_is_admin = st.checkbox("Administrateur (peut aussi gérer les comptes)", key="_new_is_admin")
        if st.button("Créer / mettre à jour ce compte", key="_create_user_btn"):
            if not new_username.strip() or not new_password:
                st.warning("Identifiant et mot de passe requis.")
            else:
                storage.create_user(new_username, new_password, is_admin=new_is_admin)
                st.success(f"Compte '{new_username}' créé.")
                st.rerun()

        st.divider()
        st.markdown("**Comptes existants**")
        users = storage.list_users()
        current_username = st.session_state["auth_user"]["username"]
        for u in users:
            label = u["username"] + (" 👑" if u["is_admin"] else "")
            c1, c2 = st.columns([3, 1])
            c1.write(label)
            if u["username"] != current_username:
                if c2.button("🗑️", key=f"_del_user_{u['username']}"):
                    storage.delete_user(u["username"])
                    st.rerun()
            else:
                c2.write("(vous)")


def require_login():
    """À appeler tout en haut de app.py, juste après storage.init_db().
    Bloque l'exécution du reste du script tant que l'utilisateur n'est pas
    authentifié."""
    if "auth_user" not in st.session_state:
        # Cas de premier lancement : aucun admin bootstrap n'a pu être créé
        # car les secrets ne sont pas configurés.
        if not storage.list_users():
            st.error(
                "Aucun compte n'existe encore. Configure `ADMIN_USERNAME` et "
                "`ADMIN_PASSWORD` dans les Secrets Streamlit (Settings → "
                "Secrets) puis recharge la page pour créer ton accès super admin."
            )
            st.stop()
        _login_form()
        st.stop()

    # Utilisateur connecté : bouton de déconnexion + panneau admin
    st.sidebar.markdown("---")
    if st.sidebar.button("🚪 Déconnexion"):
        del st.session_state["auth_user"]
        st.rerun()

    if st.session_state["auth_user"]["is_admin"]:
        _user_management_panel()
