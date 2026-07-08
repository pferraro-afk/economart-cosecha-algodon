import time

import streamlit as st

ALLOWED_DOMAIN = "admin.com.ar"
INACTIVITY_TIMEOUT_SECONDS = 7200


def is_allowed_domain(email: str, allowed_domain: str = ALLOWED_DOMAIN) -> bool:
    """Compara el dominio exacto tras el @, no endswith (evita bypass tipo evil-admin.com.ar)."""
    return email.split("@")[-1].lower() == allowed_domain.lower()


def is_session_expired(last_activity: float, now: float, timeout_seconds: int = INACTIVITY_TIMEOUT_SECONDS) -> bool:
    return (now - last_activity) > timeout_seconds


def require_login() -> None:
    if not hasattr(st.user, "is_logged_in"):
        st.error("⚠️ Auth no configurado. Agregar sección [auth] en Streamlit Secrets.")
        st.stop()

    if not st.user.is_logged_in:
        st.header("Dashboard — Duhau")
        st.subheader("Iniciá sesión con tu cuenta de Google")
        st.button("Iniciar sesión con Google", on_click=st.login)
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
