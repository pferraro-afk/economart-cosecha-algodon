import streamlit as st
import pandas as pd
import numpy as np
import requests
import plotly.express as px
import os
from dotenv import load_dotenv

load_dotenv(".env")

st.set_page_config(
    page_title="Cosecha Algodón - Duhau",
    page_icon="🌿",
    layout="wide",
)

# ── OAuth ─────────────────────────────────────────────────────────────────────

def get_token():
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
    return resp.text.strip().strip('"')

# ── fetch ─────────────────────────────────────────────────────────────────────

@st.cache_data(ttl=300, show_spinner="Cargando remitos...")
def fetch_remitos():
    token = get_token()
    resp = requests.get(
        os.environ["FINNEGANS_REPORT_URL"],
        params={"ACCESS_TOKEN": token},
        timeout=180,
    )
    resp.raise_for_status()
    df = pd.DataFrame(resp.json())
    df.columns = df.columns.str.lower()
    return df

@st.cache_data(ttl=300, show_spinner="Cargando planificación SISA...")
def fetch_sisa():
    token = get_token()
    resp = requests.get(
        os.environ["FINNEGANS_SISA_URL"],
        params={
            "ACCESS_TOKEN":              token,
            "PARAM_Campana":             "25-26_CampAgr",
            "PARAM_IndicadorSuperficie": 1,
        },
        timeout=180,
    )
    resp.raise_for_status()
    df = pd.DataFrame(resp.json())
    df.columns = df.columns.str.lower()
    return df[df["actividad"].str.contains("algod", case=False, na=False)].copy()

# ── limpieza ──────────────────────────────────────────────────────────────────

def clean_remitos(df):
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
    if "establecimiento" in df.columns:
        df["establecimiento"] = df["establecimiento"].str.strip()
    return df

def clean_sisa(df):
    num_cols = ["superficieplanificada", "superficiesembrada", "superficiecosechada",
                "porcentajeavance", "tnplanificados", "tnproducidos", "tnproducidossecos",
                "rindeesperado", "rindeobtenido", "restoacosechar", "tncertificada",
                "cantidadproducidasecundaria", "cantidaddeproductoscosechado"]
    for col in num_cols:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors="coerce")
    if "lugar" in df.columns:
        df["lugar"] = df["lugar"].str.strip()
    if "empresasucursal" in df.columns:
        df["empresasucursal"] = df["empresasucursal"].str.strip()
    return df

# ── formato numérico ─────────────────────────────────────────────────────────

def fmt_num(df):
    return {col: "{:,.2f}" for col in df.select_dtypes("number").columns}

# ── semáforos ─────────────────────────────────────────────────────────────────

def sem_rinde(val):
    if pd.isna(val): return ""
    if val >= 28: return "background-color:#d5f5e3;color:#1a7a40;font-weight:700"
    if val >= 24: return "background-color:#fef9e7;color:#b7950b;font-weight:700"
    return "background-color:#fadbd8;color:#c0392b;font-weight:700"

def sem_avance(val):
    if pd.isna(val): return ""
    if val >= 90: return "background-color:#d5f5e3;color:#1a7a40;font-weight:700"
    if val >= 50: return "background-color:#fef9e7;color:#b7950b;font-weight:700"
    return "background-color:#fadbd8;color:#c0392b;font-weight:700"

def sem_desvio(val):
    if pd.isna(val): return ""
    if val >= -5:  return "background-color:#d5f5e3;color:#1a7a40;font-weight:700"
    if val >= -15: return "background-color:#fef9e7;color:#b7950b;font-weight:700"
    return "background-color:#fadbd8;color:#c0392b;font-weight:700"

# ── resumen cruzado ──────────────────────────────────────────────────────────

def resumen_cruzado(sisa_df, rem_df):
    sisa_agg = sisa_df.groupby("lugar").agg(
        sup_sembrada=("superficiesembrada",          "sum"),
        tn_planificadas=("tnplanificados",            "sum"),
        tn_producidas=("tnproducidos",                "sum"),
        rollos_producidos=("cantidaddeproductoscosechado", "sum"),
    ).reset_index().rename(columns={"lugar": "campo"})

    rem_agg = rem_df.groupby("establecimiento").agg(
        entregado_tn=("pesoneto", "sum"),
    ).reset_index().rename(columns={"establecimiento": "campo"})
    rem_agg["entregado_tn"] = rem_agg["entregado_tn"] / 1000

    rem_rollos = rem_df[rem_df["producto"].str.contains("Rollos", case=False, na=False)]
    rol_agg = rem_rollos.groupby("establecimiento").agg(
        rollos_cargados=("cantidadstock2", "sum"),
    ).reset_index().rename(columns={"establecimiento": "campo"})

    g = sisa_agg.merge(rem_agg, on="campo", how="left")
    g = g.merge(rol_agg, on="campo", how="left")
    g["entregado_tn"]       = g["entregado_tn"].fillna(0)
    g["rollos_cargados"]    = g["rollos_cargados"].fillna(0)
    g["en_establecimiento"] = (g["tn_producidas"] - g["entregado_tn"]).clip(lower=0)
    return g.sort_values("campo")

def sem_en_establecimiento(val):
    if pd.isna(val): return ""
    if val == 0:  return "background-color:#d5f5e3;color:#1a7a40;font-weight:700"
    if val <= 50: return "background-color:#fef9e7;color:#b7950b;font-weight:700"
    return "background-color:#fadbd8;color:#c0392b;font-weight:700"

# ── agregaciones SISA ─────────────────────────────────────────────────────────

def agg_campo_sisa(df):
    g = df.groupby(["empresasucursal", "lugar"]).agg(
        sup_planificada=("superficieplanificada", "sum"),
        sup_sembrada=("superficiesembrada",       "sum"),
        sup_cosechada=("superficiecosechada",     "sum"),
        tn_planificadas=("tnplanificados",         "sum"),
        tn_producidas=("tnproducidos",             "sum"),
        tn_resto=("restoacosechar",                "sum"),
        lotes=("lote",                             "count"),
    ).reset_index()
    g["avance_pct"]     = (g["sup_cosechada"] / g["sup_sembrada"] * 100).where(g["sup_sembrada"] > 0)
    g["rinde_esp_kgha"] = (g["tn_planificadas"] * 1000 / g["sup_planificada"]).where(g["sup_planificada"] > 0)
    g["rinde_obt_kgha"] = (g["tn_producidas"]   * 1000 / g["sup_sembrada"]).where(g["sup_sembrada"] > 0)
    g["desvio_tn"]      = g["tn_producidas"] - g["tn_planificadas"]
    g["desvio_pct"]     = (g["desvio_tn"] / g["tn_planificadas"] * 100).where(g["tn_planificadas"] > 0)
    return g.sort_values(["empresasucursal", "lugar"])

# ── agregaciones remitos ──────────────────────────────────────────────────────

def sup_lote(df):
    return (
        df.groupby(["empresa", "establecimiento", "loteproduccion"])["supsembrada"]
        .first().reset_index().rename(columns={"supsembrada": "sup_ha"})
    )

def agg_campo_rem(df, sup):
    g = df.groupby(["empresa", "establecimiento"]).agg(
        bruto_kg=("pesoneto",               "sum"),
        fibra_kg=("cantidadproducidakilos",  "sum"),
        fardos=("cantidadproducidafardos",   "sum"),
        remitos=("pesoneto",                 "count"),
    ).reset_index()
    ha = sup.groupby(["empresa", "establecimiento"])["sup_ha"].sum().reset_index()
    g = g.merge(ha, on=["empresa", "establecimiento"], how="left")
    g["bruto_tn"]      = g["bruto_kg"] / 1000
    g["fibra_tn"]      = g["fibra_kg"] / 1000
    g["rinde_kgha"]    = (g["bruto_kg"] / g["sup_ha"]).where(g["sup_ha"] > 0)
    g["rinde_desmote"] = (g["fibra_kg"] / g["bruto_kg"] * 100).where(g["bruto_kg"] > 0)
    g["ppf_kg"]        = (g["bruto_kg"] / g["fardos"]).where(g["fardos"] > 0)
    return g.sort_values(["empresa", "establecimiento"])

def agg_lote(df, sup):
    g = df.groupby(["empresa", "establecimiento", "loteproduccion"]).agg(
        bruto_kg=("pesoneto",               "sum"),
        fibra_kg=("cantidadproducidakilos",  "sum"),
        fardos=("cantidadproducidafardos",   "sum"),
    ).reset_index()
    g = g.merge(sup, on=["empresa", "establecimiento", "loteproduccion"], how="left")
    g["bruto_tn"]      = g["bruto_kg"] / 1000
    g["fibra_tn"]      = g["fibra_kg"] / 1000
    g["rinde_kgha"]    = (g["bruto_kg"] / g["sup_ha"]).where(g["sup_ha"] > 0)
    g["rinde_desmote"] = (g["fibra_kg"] / g["bruto_kg"] * 100).where(g["bruto_kg"] > 0)
    return g.sort_values(["empresa", "establecimiento", "loteproduccion"])

def agg_desmotadora(df):
    g = df.groupby(["desmotadora", "empresa", "establecimiento"]).agg(
        entrega_kg=("pesoneto",               "sum"),
        fibra_kg=("cantidadproducidakilos",   "sum"),
        fardos=("cantidadproducidafardos",    "sum"),
    ).reset_index()
    g["rinde_desmote"] = (g["fibra_kg"] / g["entrega_kg"] * 100).where(g["entrega_kg"] > 0)
    g["ppf_kg"]        = (g["entrega_kg"] / g["fardos"]).where(g["fardos"] > 0)
    return g.sort_values(["desmotadora", "establecimiento"])

def agg_contratista(df):
    g = df.groupby("contratistacosecha").agg(
        bruto_kg=("pesoneto",               "sum"),
        fibra_kg=("cantidadproducidakilos",  "sum"),
        fardos=("cantidadproducidafardos",   "sum"),
    ).reset_index()
    g["rinde_desmote"] = (g["fibra_kg"] / g["bruto_kg"] * 100).where(g["bruto_kg"] > 0)
    return g.sort_values("bruto_kg", ascending=False)

def agg_semanal(df):
    g = df.copy()
    g["semana"] = g["fecha"].dt.to_period("W").dt.start_time
    return g.groupby("semana").agg(
        bruto_kg=("pesoneto",              "sum"),
        fardos=("cantidadproducidafardos", "sum"),
    ).reset_index()

# ── UI ────────────────────────────────────────────────────────────────────────

st.title("🌿 Control de Cosecha de Algodón")
st.caption("Grupo Duhau — Fuente: Finnegans API")

col_ref, _ = st.columns([1, 8])
with col_ref:
    if st.button("Actualizar datos"):
        st.cache_data.clear()
        st.rerun()

try:
    raw_rem  = clean_remitos(fetch_remitos())
    raw_sisa = clean_sisa(fetch_sisa())
except Exception as e:
    st.error(f"Error conectando con Finnegans: {e}")
    st.stop()

# ── sidebar ───────────────────────────────────────────────────────────────────

with st.sidebar:
    st.header("Filtros")

    # empresas: unión de sucursales (SISA) y empresa (remitos)
    empresas = sorted(
        set(raw_sisa["empresasucursal"].dropna().unique()) |
        set(raw_rem["empresa"].dropna().unique())
    )
    sel_empresa = st.multiselect("Empresa", empresas, default=empresas)

    # campos: siempre desde SISA (lugar) — es la fuente primaria de planificación
    campos_disponibles = sorted(
        raw_sisa[raw_sisa["empresasucursal"].isin(sel_empresa)]["lugar"].dropna().unique()
    )
    sel_campos = st.multiselect("Campo", campos_disponibles, default=campos_disponibles)

    campanias = sorted(raw_rem["campania_norm"].dropna().unique(), reverse=True)
    sel_camp  = st.selectbox("Campaña", campanias) if campanias else "25-26"

    st.markdown("---")

    # cada servicio filtra por su propia columna
    sisa = raw_sisa[
        raw_sisa["empresasucursal"].isin(sel_empresa) &
        raw_sisa["lugar"].isin(sel_campos)
    ].copy()

    rem = raw_rem[
        raw_rem["empresa"].isin(sel_empresa) &
        (raw_rem["campania_norm"] == sel_camp) &
        raw_rem["establecimiento"].isin(sel_campos)
    ].copy()

    st.caption(f"SISA: {len(sisa)} lotes")
    st.caption(f"Remitos: {len(rem)} registros")

# ── SECCIÓN 0: RESUMEN GENERAL ────────────────────────────────────────────────

st.header("Resumen General")

if not sisa.empty:
    rc = resumen_cruzado(sisa, rem)

    tot_semb       = rc["sup_sembrada"].sum()
    tot_plan       = rc["tn_planificadas"].sum()
    tot_prod       = rc["tn_producidas"].sum()
    tot_entreg     = rc["entregado_tn"].sum()
    tot_en_est     = rc["en_establecimiento"].sum()
    tot_rol_prod   = rc["rollos_producidos"].sum()
    tot_rol_carg   = rc["rollos_cargados"].sum()

    c1, c2, c3, c4, c5, c6, c7 = st.columns(7)
    c1.metric("Sup Sembrada",        f"{tot_semb:,.0f} ha")
    c2.metric("Tn Planificadas",     f"{tot_plan:,.2f} Tn")
    c3.metric("Tn Producidas",       f"{tot_prod:,.2f} Tn")
    c4.metric("Entregado a Desm.",   f"{tot_entreg:,.2f} Tn")
    c5.metric("En Establecimiento",  f"{tot_en_est:,.2f} Tn")
    c6.metric("Rollos Producidos",   f"{tot_rol_prod:,.0f}")
    c7.metric("Rollos Cargados",     f"{tot_rol_carg:,.0f}")

    st.divider()

    disp_rc = rc.rename(columns={
        "campo":              "Campo",
        "sup_sembrada":       "Sup Semb (ha)",
        "tn_planificadas":    "Tn Planificadas",
        "tn_producidas":      "Tn Producidas",
        "entregado_tn":       "Entregado a Desm. (Tn)",
        "en_establecimiento": "En Establecimiento (Tn)",
        "rollos_producidos":  "Rollos Producidos",
        "rollos_cargados":    "Rollos Cargados",
    })
    st.dataframe(
        disp_rc.style
            .format(fmt_num(disp_rc), na_rep="—")
            .map(sem_en_establecimiento, subset=["En Establecimiento (Tn)"]),
        use_container_width=True, hide_index=True,
    )

st.divider()

# ── SECCIÓN 1: PLANIFICACIÓN DE CAMPAÑA (SISA) ────────────────────────────────

st.header("Planificación de Campaña")

if sisa.empty:
    st.warning("Sin datos de planificación para los filtros seleccionados.")
else:
    vc_sisa = agg_campo_sisa(sisa)

    tot_sup_plan = sisa["superficieplanificada"].sum()
    tot_sup_semb = sisa["superficiesembrada"].sum()
    tot_sup_cos  = sisa["superficiecosechada"].sum()
    tot_tn_plan  = sisa["tnplanificados"].sum()
    tot_tn_prod  = sisa["tnproducidos"].sum()
    tot_resto    = sisa["restoacosechar"].sum()
    avance_gl    = tot_sup_cos / tot_sup_semb * 100 if tot_sup_semb > 0 else 0

    c1, c2, c3, c4, c5, c6, c7 = st.columns(7)
    c1.metric("Sup Planificada",  f"{tot_sup_plan:,.0f} ha")
    c2.metric("Sup Sembrada",     f"{tot_sup_semb:,.0f} ha")
    c3.metric("Sup Cosechada",    f"{tot_sup_cos:,.0f} ha")
    c4.metric("Avance Global",    f"{avance_gl:.1f}%")
    c5.metric("Tn Planificadas",  f"{tot_tn_plan:,.0f}")
    c6.metric("Tn Producidas",    f"{tot_tn_prod:,.0f}")
    c7.metric("Resto a Cosechar", f"{tot_resto:,.0f} ha")

    st.divider()

    col_g1, col_g2 = st.columns(2)

    with col_g1:
        st.subheader("Avance de cosecha por campo (%)")
        fig_av = px.bar(
            vc_sisa.sort_values("avance_pct"),
            x="avance_pct", y="lugar", orientation="h",
            color="avance_pct",
            color_continuous_scale=["#fadbd8", "#fef9e7", "#d5f5e3"],
            range_color=[0, 100],
            labels={"avance_pct": "%", "lugar": ""},
            text="avance_pct",
        )
        fig_av.update_traces(texttemplate="%{text:.1f}%", textposition="outside")
        fig_av.update_layout(height=400, margin=dict(l=0, r=40, t=0, b=0),
                             coloraxis_showscale=False)
        st.plotly_chart(fig_av, use_container_width=True)

    with col_g2:
        st.subheader("Rinde planificado vs producido (kg/ha)")
        df_rinde_melt = vc_sisa.melt(
            id_vars="lugar",
            value_vars=["rinde_esp_kgha", "rinde_obt_kgha"],
            var_name="tipo", value_name="kg_ha"
        ).replace({"rinde_esp_kgha": "Planificado", "rinde_obt_kgha": "Producido"})
        fig_rinde = px.bar(
            df_rinde_melt,
            x="lugar", y="kg_ha", color="tipo", barmode="group",
            labels={"kg_ha": "kg/ha", "lugar": "", "tipo": ""},
            color_discrete_map={"Planificado": "#aed6f1", "Producido": "#2ecc71"},
        )
        fig_rinde.update_layout(height=400, margin=dict(l=0, r=0, t=0, b=0), legend_title="")
        st.plotly_chart(fig_rinde, use_container_width=True)

    st.subheader("Detalle por campo — Planificado vs Real")
    disp_sisa = vc_sisa.rename(columns={
        "empresasucursal": "Sucursal", "lugar": "Campo", "lotes": "Lotes",
        "sup_planificada": "Sup Plan (ha)", "sup_sembrada": "Sup Semb (ha)",
        "sup_cosechada": "Sup Cos (ha)",   "avance_pct": "Avance (%)",
        "tn_planificadas": "Tn Plan",       "tn_producidas": "Tn Prod",
        "tn_resto": "Resto (ha)",           "desvio_tn": "Desvío Tn",
        "desvio_pct": "Desvío (%)",         "rinde_esp_kgha": "Rinde Esp (kg/ha)",
        "rinde_obt_kgha": "Rinde Obt (kg/ha)",
    })[["Sucursal", "Campo", "Lotes", "Sup Plan (ha)", "Sup Semb (ha)", "Sup Cos (ha)",
        "Avance (%)", "Tn Plan", "Tn Prod", "Desvío Tn", "Desvío (%)",
        "Rinde Esp (kg/ha)", "Rinde Obt (kg/ha)"]]
    st.dataframe(
        disp_sisa.style
            .format(fmt_num(disp_sisa), na_rep="—")
            .map(sem_avance, subset=["Avance (%)"])
            .map(sem_desvio, subset=["Desvío (%)"]),
        use_container_width=True, hide_index=True,
    )

    with st.expander("Ver detalle por lote (SISA)"):
        cols_lote = ["empresasucursal", "lugar", "lote", "actividad",
                     "superficieplanificada", "superficiesembrada", "superficiecosechada",
                     "porcentajeavance", "tnplanificados", "tnproducidos",
                     "restoacosechar", "rindeesperado", "rindeobtenido"]
        disp_lote_sisa = (
            sisa[[c for c in cols_lote if c in sisa.columns]]
            .sort_values(["empresasucursal", "lugar", "lote"])
            .rename(columns={
                "empresasucursal": "Sucursal", "lugar": "Campo", "lote": "Lote",
                "actividad": "Actividad",
                "superficieplanificada": "Sup Plan (ha)", "superficiesembrada": "Sup Semb (ha)",
                "superficiecosechada": "Sup Cos (ha)",    "porcentajeavance": "Avance (%)",
                "tnplanificados": "Tn Plan",              "tnproducidos": "Tn Prod",
                "restoacosechar": "Resto (ha)",           "rindeesperado": "Rinde Esp (kg/ha)",
                "rindeobtenido": "Rinde Obt (kg/ha)",
            })
        )
        st.dataframe(
            disp_lote_sisa.style
                .format(fmt_num(disp_lote_sisa), na_rep="—")
                .map(sem_avance, subset=["Avance (%)"]),
            use_container_width=True, hide_index=True,
        )

st.divider()

# ── SECCIÓN 2: REMITOS DE COSECHA ─────────────────────────────────────────────

st.header("Remitos de Cosecha")

if rem.empty:
    st.info("Sin remitos para los filtros seleccionados.")
    st.stop()

sup   = sup_lote(rem)
vc    = agg_campo_rem(rem, sup)
vl    = agg_lote(rem, sup)
vd    = agg_desmotadora(rem)
vcont = agg_contratista(rem)
vsem  = agg_semanal(rem)

c1, c2, c3, c4, c5, c6 = st.columns(6)
c1.metric("Algodón Bruto",   f"{rem['pesoneto'].sum()/1000:,.1f} Tn")
c2.metric("Fibra Producida", f"{rem['cantidadproducidakilos'].sum()/1000:,.1f} Tn")
rd_total = (rem["cantidadproducidakilos"].sum() / rem["pesoneto"].sum() * 100
            if rem["pesoneto"].sum() > 0 else 0)
c3.metric("Rinde Desmote",   f"{rd_total:.1f}%")
c4.metric("Fardos",          f"{int(rem['cantidadproducidafardos'].sum()):,}")
c5.metric("Campos",          rem["establecimiento"].nunique())
c6.metric("Remitos",         len(rem))

st.divider()

col_g1, col_g2 = st.columns(2)

with col_g1:
    st.subheader("Algodón bruto por campo (Tn)")
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
        labels={"semana": "Semana", "bruto_kg": "kg Algodón Bruto"},
        color_discrete_sequence=["#2ecc71"],
    )
    fig3.update_layout(height=280, margin=dict(l=0, r=0, t=0, b=0))
    st.plotly_chart(fig3, use_container_width=True)

st.divider()

st.subheader("Producción por campo")
disp_campo = vc.rename(columns={
    "empresa": "Empresa", "establecimiento": "Campo", "sup_ha": "Sup (ha)",
    "bruto_tn": "Bruto (Tn)", "rinde_kgha": "Rinde Bruto (kg/ha)",
    "fibra_tn": "Fibra (Tn)", "rinde_desmote": "Rinde Desmote (%)",
    "fardos": "Fardos", "ppf_kg": "Peso Prom Fardo (kg)",
})[["Empresa", "Campo", "Sup (ha)", "Bruto (Tn)", "Rinde Bruto (kg/ha)",
    "Fibra (Tn)", "Rinde Desmote (%)", "Fardos", "Peso Prom Fardo (kg)"]]
st.dataframe(
    disp_campo.style
        .format(fmt_num(disp_campo), na_rep="—")
        .map(sem_rinde, subset=["Rinde Desmote (%)"]),
    use_container_width=True, hide_index=True,
)

st.subheader("Producción por lote")
disp_lote = vl.rename(columns={
    "empresa": "Empresa", "establecimiento": "Campo", "loteproduccion": "Lote",
    "sup_ha": "Sup (ha)", "bruto_tn": "Bruto (Tn)", "rinde_kgha": "Rinde Bruto (kg/ha)",
    "fibra_tn": "Fibra (Tn)", "rinde_desmote": "Rinde Desmote (%)", "fardos": "Fardos",
})[["Empresa", "Campo", "Lote", "Sup (ha)", "Bruto (Tn)", "Rinde Bruto (kg/ha)",
    "Fibra (Tn)", "Rinde Desmote (%)", "Fardos"]]
st.dataframe(
    disp_lote.style
        .format(fmt_num(disp_lote), na_rep="—")
        .map(sem_rinde, subset=["Rinde Desmote (%)"]),
    use_container_width=True, hide_index=True,
)

st.subheader("Logística por desmotadora")
disp_desm = vd.rename(columns={
    "desmotadora": "Desmotadora", "empresa": "Empresa", "establecimiento": "Campo",
    "entrega_kg": "Entregado (kg)", "fibra_kg": "Fibra (kg)",
    "rinde_desmote": "Rinde (%)", "fardos": "Fardos", "ppf_kg": "Peso Prom Fardo (kg)",
})[["Desmotadora", "Empresa", "Campo", "Entregado (kg)", "Fibra (kg)",
    "Rinde (%)", "Fardos", "Peso Prom Fardo (kg)"]]
st.dataframe(
    disp_desm.style
        .format(fmt_num(disp_desm), na_rep="—")
        .map(sem_rinde, subset=["Rinde (%)"]),
    use_container_width=True, hide_index=True,
)

st.subheader("Rinde por contratista")
disp_cont = vcont.rename(columns={
    "contratistacosecha": "Contratista",
    "bruto_kg": "Bruto (kg)", "fibra_kg": "Fibra (kg)",
    "rinde_desmote": "Rinde (%)", "fardos": "Fardos",
})[["Contratista", "Bruto (kg)", "Fibra (kg)", "Rinde (%)", "Fardos"]]
st.dataframe(
    disp_cont.style
        .format(fmt_num(disp_cont), na_rep="—")
        .map(sem_rinde, subset=["Rinde (%)"]),
    use_container_width=True, hide_index=True,
)
