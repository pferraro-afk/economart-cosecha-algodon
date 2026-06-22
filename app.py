import streamlit as st

st.set_page_config(
    page_title="Cosecha Algodón — Duhau",
    page_icon="🌿",
    layout="wide",
)

pg = st.navigation([
    st.Page("pages/0_Resumen.py",   title="Resumen General", icon="🏠"),
    st.Page("pages/1_Produccion.py", title="Producción",      icon="🌱"),
    st.Page("pages/2_Logistica.py",  title="Logística",       icon="🚚"),
    st.Page("pages/3_Desmote.py",    title="Desmote",         icon="🏭"),
])
pg.run()
