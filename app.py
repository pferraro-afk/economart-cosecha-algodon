import streamlit as st
import sys
import os

# garantiza que el directorio raíz esté en sys.path cuando las páginas se ejecutan vía exec()
_root = os.path.dirname(os.path.abspath(__file__))
if _root not in sys.path:
    sys.path.insert(0, _root)

st.set_page_config(
    page_title="Cosecha Algodón — Duhau",
    page_icon="🌿",
    layout="wide",
)

from access_control import require_login
require_login()

pg = st.navigation([
    st.Page("pages/0_Resumen.py",   title="Resumen General", icon="🏠"),
    st.Page("pages/1_Produccion.py", title="Producción",      icon="🌱"),
    st.Page("pages/2_Logistica.py",  title="Logística",       icon="🚚"),
    st.Page("pages/3_Desmote.py",    title="Desmote",         icon="🏭"),
])
pg.run()
