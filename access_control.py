import base64
import os
import time

import streamlit as st

ALLOWED_DOMAIN = "admin.com.ar"
INACTIVITY_TIMEOUT_SECONDS = 7200
LOGO_PATH = os.path.join(os.path.dirname(__file__), "assets", "logo_grupo_duhau.png")


@st.cache_resource
def _logo_data_uri() -> str:
    with open(LOGO_PATH, "rb") as f:
        encoded = base64.b64encode(f.read()).decode("ascii")
    return f"data:image/png;base64,{encoded}"


def is_allowed_domain(email: str, allowed_domain: str = ALLOWED_DOMAIN) -> bool:
    """Compara el dominio exacto tras el @, no endswith (evita bypass tipo evil-admin.com.ar)."""
    return email.split("@")[-1].lower() == allowed_domain.lower()


def is_session_expired(last_activity: float, now: float, timeout_seconds: int = INACTIVITY_TIMEOUT_SECONDS) -> bool:
    return (now - last_activity) > timeout_seconds


def _render_login_screen() -> None:
    st.markdown(
        """
        <style>
        section[data-testid="stSidebar"], header[data-testid="stHeader"],
        #MainMenu, footer { display: none; }

        .stApp { background: linear-gradient(180deg, #f8fbf9 0%, #eef6f0 100%); }

        .st-key-login_card {
            max-width: 480px;
            margin: 8vh auto 0 auto;
            padding: 3.5rem 3rem 3rem;
            border-radius: 24px;
            background: #ffffff;
            box-shadow: 0 12px 40px rgba(0, 0, 0, 0.10);
            position: relative;
            overflow: hidden;
        }
        .st-key-login_card::before {
            content: "";
            position: absolute;
            top: 0; left: 0; right: 0;
            height: 6px;
            background: linear-gradient(90deg, #2ecc71, #27ae60);
        }
        .st-key-login_card, .st-key-login_card * {
            text-align: center !important;
        }
        .st-key-login_card [data-testid="stMarkdownContainer"] {
            display: flex;
            flex-direction: column;
            align-items: center;
        }
        .st-key-login_card .login-logo {
            display: block;
            width: 260px;
            margin: 0 auto 1.5rem auto;
        }
        .st-key-login_card h2 { margin-bottom: 0.5rem; font-size: 1.6rem; }
        .st-key-login_card h2 a,
        .st-key-login_card h2 [data-testid="stHeaderActionElements"] {
            display: none !important;
        }
        .st-key-login_card p { color: #6b7280; font-size: 1.1rem; line-height: 1.6; margin-bottom: 2rem; }
        .st-key-login_card .login-footnote { margin-top: 1.4rem; font-size: 0.9rem; color: #9ca3af; }
        .st-key-login_card button {
            display: flex !important;
            align-items: center !important;
            justify-content: center !important;
            gap: 0.5rem !important;
            border-radius: 999px !important;
            font-size: 1.05rem !important;
            font-weight: 600 !important;
            padding: 0.85rem 0 !important;
            background: linear-gradient(135deg, #2ecc71, #27ae60) !important;
            border: none !important;
            box-shadow: 0 6px 16px rgba(46, 204, 113, 0.35) !important;
            transition: transform 0.15s ease, box-shadow 0.15s ease !important;
        }
        .st-key-login_card button > div {
            display: flex !important;
            align-items: center !important;
            justify-content: center !important;
        }
        .st-key-login_card button p {
            margin: 0 !important;
            line-height: 1.2 !important;
            color: #ffffff !important;
        }
        .st-key-login_card button:hover {
            transform: translateY(-2px);
            box-shadow: 0 10px 24px rgba(46, 204, 113, 0.45) !important;
        }
        .st-key-login_card button:active { transform: translateY(0); }
        </style>
        """,
        unsafe_allow_html=True,
    )
    with st.container(border=True, key="login_card"):
        st.markdown(
            f"""
            <img class="login-logo" src="{_logo_data_uri()}" alt="Grupo Duhau">
            <h2>Tablero Cosecha Algodón</h2>
            <p>Iniciá sesión con tu cuenta de Google<br>(@admin.com.ar)</p>
            """,
            unsafe_allow_html=True,
        )
        st.button(
            "Iniciar sesión con Google",
            on_click=st.login,
            type="primary",
            use_container_width=True,
        )
        st.markdown(
            '<div class="login-footnote">Acceso exclusivo para personal de Grupo Duhau</div>',
            unsafe_allow_html=True,
        )


def require_login() -> None:
    if not hasattr(st.user, "is_logged_in"):
        st.error("⚠️ Auth no configurado. Agregar sección [auth] en Streamlit Secrets.")
        st.stop()

    if not st.user.is_logged_in:
        _render_login_screen()
        st.stop()

    user_email = st.user.email or ""
    if not is_allowed_domain(user_email):
        st.error(f"Tu cuenta no pertenece al dominio autorizado (@{ALLOWED_DOMAIN}).")
        st.button("Cerrar sesión", on_click=st.logout, key="logout_wrong_domain")
        st.stop()

    now = time.time()
    last_activity = st.session_state.get("last_activity")
    if last_activity is not None and is_session_expired(last_activity, now):
        st.warning("Sesión expirada por inactividad. Volvé a iniciar sesión.")
        st.session_state.pop("last_activity", None)
        st.logout()
        st.stop()

    st.session_state["last_activity"] = now

    with st.sidebar:
        st.caption(f"Sesión: {st.user.name}")
        st.button("Cerrar sesión", on_click=st.logout, key="logout_sidebar")
