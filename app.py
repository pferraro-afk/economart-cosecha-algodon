import streamlit as st
import pandas as pd
import numpy as np
import requests
import plotly.express as px
import os
from dotenv import load_dotenv

load_dotenv(".env")

st.set_page_config(
    page_title="Cosecha Algodon - Duhau",
    page_icon="🌿",
    layout="wide",
)

# -- API ---------------------------------------------------------------------

@st.cache_data(ttl=300, show_spinner="Conectando con Finnegans...")
def fetch_data():
    resp = requests.get(
        os.environ["FINNEGANS_OAUTH_URL"],
        params={
            "grant_type":    "client_credentials",
            "client_id":     os.environ["FINNEGANS_CLIENT_ID"],
            "client_secret": os.environ["FINNEGANS_CLIENT_SECRET"],
        },
        timeout=30,
    )
    resp.raise_for_status()
    token = resp.text.strip().strip('"')
    resp2 = requests.get(
        os.environ["FINNEGANS_REPORT_URL"],
        params={"ACCESS_TOKEN": token},
        timeout=180,
    )
    resp2.raise_for_status()
    df = pd.DataFrame(resp2.json())
    df.columns = df.columns.str.lower()
    return df

# -- limpieza ----------------------------------------------------------------

def clean(df):
    for col in ["pesoneto", "cantidadproducidakilos", "cantidadproducidafardos",
                "rindefibra", "supsembrada"]:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col].replace("NULL", None), errors="coerce")
    if "depositodestino" in df.columns:
        df["desmotadora"] = (
            df["depositodestino"]
            .str.replace(r"^Desmotadora\s*-\s*", "", regex=True)
            .str.split(" - ").str[0].str.strip()
        )
    if "partida" in df.columns:
        df["campania_norm"] = df["partida"].str.extract(r"(\d{2}-\d{2})$")
    df["fecha"] = pd.to_datetime(df["fecha"], errors="coerce")
    return df

# -- agregaciones ------------------------------------------------------------

def sup_lote(df):
    return (
        df.groupby(["empresa", "establecimiento", "loteproduccion"])["supsembrada"]
        .first().reset_index().rename(columns={"supsembrada": "sup_ha"})
    )

def agg_campo(df, sup):
    g = df.groupby(["empresa", "establecimiento"]).agg(
        bruto_kg=("pesoneto", "sum"),
        fibra_kg=("cantidadproducidakilos", "sum"),
        fardos=("cantidadproducidafardos", "sum"),
        remitos=("pesoneto", "count"),
    ).reset_index()
    ha = sup.groupby(["empresa", "establecimiento"])["sup_ha"].sum().reset_index()
    g = g.merge(ha, on=["empresa", "establecimiento"], how="left")
    g["bruto_tn"]      = g["bruto_kg"] / 1000
    g["fibra_tn"]      = g["fibra_kg"] / 1000
    g["rinde_kgha"]    = g["bruto_kg"] / g["sup_ha"]
    g["rinde_desmote"] = (g["fibra_kg"] / g["bruto_kg"] * 100).where(g["bruto_kg"] > 0)
    g["ppf_kg"]        = (g["bruto_kg"] / g["fardos"]).where(g["fardos"] > 0)
    return g.sort_values(["empresa", "establecimiento"])

def agg_lote(df, sup):
    g = df.groupby(["empresa", "establecimiento", "loteproduccion"]).agg(
        bruto_kg=("pesoneto", "sum"),
        fibra_kg=("cantidadproducidakilos", "sum"),
        fardos=("cantidadproducidafardos", "sum"),
    ).reset_index()
    g = g.merge(sup, on=["empresa", "establecimiento", "loteproduccion"], how="left")
    g["bruto_tn"]      = g["bruto_kg"] / 1000
    g["fibra_tn"]      = g["fibra_kg"] / 1000
    g["rinde_kgha"]    = g["bruto_kg"] / g["sup_ha"]
    g["rinde_desmote"] = (g["fibra_kg"] / g["bruto_kg"] * 100).where(g["bruto_kg"] > 0)
    return g.sort_values(["empresa", "establecimiento", "loteproduccion"])

def agg_desmotadora(df):
    g = df.groupby(["desmotadora", "empresa", "establecimiento"]).agg(
        entrega_kg=("pesoneto", "sum"),
        fibra_kg=("cantidadproducidakilos", "sum"),
        fardos=("cantidadproducidafardos", "sum"),
    ).reset_index()
    g["rinde_desmote"] = (g["fibra_kg"] / g["entrega_kg"] * 100).where(g["entrega_kg"] > 0)
    g["ppf_kg"]        = (g["entrega_kg"] / g["fardos"]).where(g["fardos"] > 0)
    return g.sort_values(["desmotadora", "establecimiento"])

def agg_contratista(df):
    g = df.groupby("contratistacosecha").agg(
        bruto_kg=("pesoneto", "sum"),
        fibra_kg=("cantidadproducidakilos", "sum"),
        fardos=("cantidadproducidafardos", "sum"),
    ).reset_index()
    g["rinde_desmote"] = (g["fibra_kg"] / g["bruto_kg"] * 100).where(g["bruto_kg"] > 0)
    return g.sort_values("bruto_kg", ascending=False)

def agg_semanal(df):
    g = df.copy()
    g["semana"] = g["fecha"].dt.to_period("W").dt.start_time
    return g.groupby("semana").agg(
        bruto_kg=("pesoneto", "sum"),
        fardos=("cantidadproducidafardos", "sum"),
    ).reset_index()

# -- semaforo ----------------------------------------------------------------

def color_rinde(val):
    if pd.isna(val): return ""
    if val >= 28: return "background-color:#d5f5e3;color:#1a7a40;font-weight:700"
    if val >= 24: return "background-color:#fef9e7;color:#b7950b;font-weight:700"
    return "background-color:#fadbd8;color:#c0392b;font-weight:700"

# -- UI ----------------------------------------------------------------------

st.title("🌿 Control de Cosecha de Algodon")
st.caption("Grupo Duhau - Fuente: Finnegans API")

col_ref, _ = st.columns([1, 8])
with col_ref:
    if st.button("Actualizar datos"):
        st.cache_data.clear()
        st.rerun()

try:
    raw = clean(fetch_data())
except Exception as e:
    st.error(f"Error conectando con Finnegans: {e}")
    st.stop()

# -- sidebar -----------------------------------------------------------------

with st.sidebar:
    st.header("Filtros")
    empresas = sorted(raw["empresa"].dropna().unique())
    sel_empresa = st.multiselect("Empresa", empresas, default=empresas)
    campanias = sorted(raw["campania_norm"].dropna().unique(), reverse=True)
    sel_camp = st.selectbox("Campana", campanias)
    df = raw[
        raw["empresa"].isin(sel_empresa) &
        (raw["campania_norm"] == sel_camp)
    ].copy()
    campos = sorted(df["establecimiento"].dropna().unique())
    sel_campos = st.multiselect("Campo", campos, default=campos)
    df = df[df["establecimiento"].isin(sel_campos)]
    st.markdown("---")
    st.caption(f"{len(df)} remitos cargados")

if df.empty:
    st.warning("No hay datos para los filtros seleccionados.")
    st.stop()

sup   = sup_lote(df)
vc    = agg_campo(df, sup)
vl    = agg_lote(df, sup)
vd    = agg_desmotadora(df)
vcont = agg_contratista(df)
vsem  = agg_semanal(df)

# -- tarjetas ----------------------------------------------------------------

st.subheader("Resumen de campana")
c1, c2, c3, c4, c5, c6 = st.columns(6)
c1.metric("Algodon Bruto",   f"{df['pesoneto'].sum()/1000:,.1f} Tn")
c2.metric("Fibra Producida", f"{df['cantidadproducidakilos'].sum()/1000:,.1f} Tn")
rd_total = df["cantidadproducidakilos"].sum() / df["pesoneto"].sum() * 100 if df["pesoneto"].sum() > 0 else 0
c3.metric("Rinde Desmote",   f"{rd_total:.1f}%")
c4.metric("Fardos",          f"{int(df['cantidadproducidafardos'].sum()):,}")
c5.metric("Campos",          df["establecimiento"].nunique())
c6.metric("Remitos",         len(df))

st.divider()

# -- graficos ----------------------------------------------------------------

col_g1, col_g2 = st.columns(2)

with col_g1:
    st.subheader("Algodon bruto por campo (Tn)")
    fig = px.bar(
        vc.sort_values("bruto_tn"),
        x="bruto_tn", y="establecimiento", color="empresa",
        orientation="h",
        labels={"bruto_tn": "Tn", "establecimiento": ""},
        color_discrete_sequence=px.colors.qualitative.Set2,
    )
    fig.update_layout(height=400, margin=dict(l=0, r=0, t=0, b=0), legend_title="")
    st.plotly_chart(fig, use_container_width=True)

with col_g2:
    st.subheader("Rinde al desmote por campo (%)")
    fig2 = px.bar(
        vc.sort_values("rinde_desmote"),
        x="rinde_desmote", y="establecimiento", color="empresa",
        orientation="h",
        labels={"rinde_desmote": "%", "establecimiento": ""},
        color_discrete_sequence=px.colors.qualitative.Set2,
    )
    fig2.add_vline(x=24, line_dash="dot", line_color="orange", annotation_text="24%")
    fig2.add_vline(x=28, line_dash="dot", line_color="green",  annotation_text="28%")
    fig2.update_layout(height=400, margin=dict(l=0, r=0, t=0, b=0), legend_title="")
    st.plotly_chart(fig2, use_container_width=True)

if not vsem.empty and vsem["semana"].notna().any():
    st.subheader("Remitos por semana (kg bruto)")
    fig3 = px.bar(
        vsem, x="semana", y="bruto_kg",
        labels={"semana": "Semana", "bruto_kg": "kg Algodon Bruto"},
        color_discrete_sequence=["#2ecc71"],
    )
    fig3.update_layout(height=280, margin=dict(l=0, r=0, t=0, b=0))
    st.plotly_chart(fig3, use_container_width=True)

st.divider()

# -- tablas ------------------------------------------------------------------

st.subheader("Produccion por campo")
disp_campo = vc.rename(columns={
    "empresa": "Empresa", "establecimiento": "Campo", "sup_ha": "Sup (ha)",
    "bruto_tn": "Bruto (Tn)", "rinde_kgha": "Rinde Bruto (kg/ha)",
    "fibra_tn": "Fibra (Tn)", "rinde_desmote": "Rinde Desmote (%)",
    "fardos": "Fardos", "ppf_kg": "Peso Prom Fardo (kg)",
})[["Empresa", "Campo", "Sup (ha)", "Bruto (Tn)", "Rinde Bruto (kg/ha)",
    "Fibra (Tn)", "Rinde Desmote (%)", "Fardos", "Peso Prom Fardo (kg)"]]
st.dataframe(
    disp_campo.style.map(color_rinde, subset=["Rinde Desmote (%)"]),
    use_container_width=True, hide_index=True,
)

st.subheader("Produccion por lote")
disp_lote = vl.rename(columns={
    "empresa": "Empresa", "establecimiento": "Campo", "loteproduccion": "Lote",
    "sup_ha": "Sup (ha)", "bruto_tn": "Bruto (Tn)", "rinde_kgha": "Rinde Bruto (kg/ha)",
    "fibra_tn": "Fibra (Tn)", "rinde_desmote": "Rinde Desmote (%)", "fardos": "Fardos",
})[["Empresa", "Campo", "Lote", "Sup (ha)", "Bruto (Tn)", "Rinde Bruto (kg/ha)",
    "Fibra (Tn)", "Rinde Desmote (%)", "Fardos"]]
st.dataframe(
    disp_lote.style.map(color_rinde, subset=["Rinde Desmote (%)"]),
    use_container_width=True, hide_index=True,
)

st.subheader("Logistica por desmotadora")
disp_desm = vd.rename(columns={
    "desmotadora": "Desmotadora", "empresa": "Empresa", "establecimiento": "Campo",
    "entrega_kg": "Entregado (kg)", "fibra_kg": "Fibra (kg)",
    "rinde_desmote": "Rinde (%)", "fardos": "Fardos", "ppf_kg": "Peso Prom Fardo (kg)",
})[["Desmotadora", "Empresa", "Campo", "Entregado (kg)", "Fibra (kg)",
    "Rinde (%)", "Fardos", "Peso Prom Fardo (kg)"]]
st.dataframe(
    disp_desm.style.map(color_rinde, subset=["Rinde (%)"]),
    use_container_width=True, hide_index=True,
)

st.subheader("Rinde por contratista")
disp_cont = vcont.rename(columns={
    "contratistacosecha": "Contratista",
    "bruto_kg": "Bruto (kg)", "fibra_kg": "Fibra (kg)",
    "rinde_desmote": "Rinde (%)", "fardos": "Fardos",
})[["Contratista", "Bruto (kg)", "Fibra (kg)", "Rinde (%)", "Fardos"]]
st.dataframe(
    disp_cont.style.map(color_rinde, subset=["Rinde (%)"]),
    use_container_width=True, hide_index=True,
)
