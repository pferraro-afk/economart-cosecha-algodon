import streamlit as st
import pandas as pd
import numpy as np
import requests
import plotly.express as px
import io
import os
import time
import datetime
from dotenv import load_dotenv

load_dotenv(".env")

st.set_page_config(
    page_title="Cosecha Algodón — Duhau",
    page_icon="🌿",
    layout="wide",
)

# ── credentials (local .env + Streamlit Cloud secrets) ───────────────────────

def get_env(key):
    try:
        return st.secrets[key]
    except (KeyError, AttributeError, FileNotFoundError):
        pass
    val = os.environ.get(key)
    if not val:
        raise ValueError(f"Credencial faltante: {key}")
    return val

# ── auth ──────────────────────────────────────────────────────────────────────

def get_token():
    resp = requests.get(
        get_env("FINNEGANS_OAUTH_URL"),
        params={
            "grant_type":    "client_credentials",
            "client_id":     get_env("FINNEGANS_CLIENT_ID"),
            "client_secret": get_env("FINNEGANS_CLIENT_SECRET"),
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
        get_env("FINNEGANS_REPORT_URL"),
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
        get_env("FINNEGANS_SISA_URL"),
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

# ── cleaning ──────────────────────────────────────────────────────────────────

def clean_remitos(df):
    for col in ["pesoneto", "cantidadproducidakilos", "cantidadproducidafardos",
                "rindefibra", "supsembrada", "cantidadstock2"]:
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
    df["fecha"] = pd.to_datetime(df["fecha"], dayfirst=True, errors="coerce")
    if "establecimiento" in df.columns:
        df["establecimiento"] = df["establecimiento"].str.strip()
    return df

def clean_sisa(df):
    num_cols = [
        "superficieplanificada", "superficiesembrada", "superficiecosechada",
        "porcentajeavance", "tnplanificados", "tnproducidos", "tnproducidossecos",
        "rindeesperado", "rindeobtenido", "restoacosechar", "tncertificada",
        "cantidadproducidasecundaria", "cantidaddeproductoscosechado",
    ]
    for col in num_cols:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors="coerce")
    for col in ["lugar", "empresasucursal", "empresa"]:
        if col in df.columns:
            df[col] = df[col].str.strip()
    return df

# ── helpers ───────────────────────────────────────────────────────────────────

def fmt_num(df):
    result = {}
    for col in df.select_dtypes("number").columns:
        vals = df[col].dropna()
        if len(vals) > 0 and ((vals % 1) == 0).all():
            fmt = "{:,.0f}"
        else:
            fmt = "{:,.2f}"
        result[col] = lambda v, f=fmt: "—" if pd.isna(v) else f.format(v)
    return result

def to_excel_bytes(df):
    buf = io.BytesIO()
    df.to_excel(buf, index=False)
    return buf.getvalue()

def download_btn(df, filename, label="⬇ Descargar Excel"):
    st.download_button(
        label=label,
        data=to_excel_bytes(df),
        file_name=filename,
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    )

def totales_row(df, label_col, label="TOTAL"):
    """Append a totals row, skipping percentage columns."""
    sum_cols = [c for c in df.select_dtypes("number").columns if "%" not in c]
    row = {c: np.nan for c in df.columns}
    row[label_col] = label
    for c in sum_cols:
        row[c] = df[c].sum()
    return pd.concat([df, pd.DataFrame([row])], ignore_index=True)

def style_total_row(styled, n_rows):
    """Bold + shaded background on the last (total) row."""
    return styled.apply(
        lambda row: [
            "font-weight:800;background-color:#e8f5e9;color:#1a5c2a"
            if row.name == n_rows else ""
            for _ in row
        ],
        axis=1,
    )

# ── semaphores ────────────────────────────────────────────────────────────────

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

def sem_en_est(val):
    if pd.isna(val): return ""
    if val == 0:   return "background-color:#d5f5e3;color:#1a7a40;font-weight:700"
    if val <= 50:  return "background-color:#fef9e7;color:#b7950b;font-weight:700"
    return "background-color:#fadbd8;color:#c0392b;font-weight:700"

def sem_avance_entrega(val):
    if pd.isna(val): return ""
    if val >= 90: return "background-color:#d5f5e3;color:#1a7a40;font-weight:700"
    if val >= 50: return "background-color:#fef9e7;color:#b7950b;font-weight:700"
    return "background-color:#fadbd8;color:#c0392b;font-weight:700"

# ── aggregations ──────────────────────────────────────────────────────────────

def resumen_cruzado(sisa_df, rem_df):
    sisa_agg = sisa_df.groupby("lugar").agg(
        sup_sembrada      = ("superficiesembrada",           "sum"),
        tn_planificadas   = ("tnplanificados",               "sum"),
        tn_producidas     = ("tnproducidos",                 "sum"),
        rollos_producidos = ("cantidadproducidasecundaria",  "sum"),
    ).reset_index().rename(columns={"lugar": "campo"})

    rem_agg = rem_df.groupby("establecimiento").agg(
        entregado_tn=("pesoneto", "sum"),
    ).reset_index().rename(columns={"establecimiento": "campo"})
    rem_agg["entregado_tn"] /= 1000

    rem_rollos = rem_df[rem_df["producto"].str.contains("Rollos", case=False, na=False)]
    rol_agg = rem_rollos.groupby("establecimiento").agg(
        rollos_cargados=("cantidadstock2", "sum"),
    ).reset_index().rename(columns={"establecimiento": "campo"})

    g = sisa_agg.merge(rem_agg, on="campo", how="left")
    g = g.merge(rol_agg, on="campo", how="left")
    g["entregado_tn"]       = g["entregado_tn"].fillna(0)
    g["rollos_cargados"]    = g["rollos_cargados"].fillna(0)
    g["en_establecimiento"] = (g["tn_producidas"] - g["entregado_tn"]).clip(lower=0)
    g["avance_entrega_pct"] = (g["entregado_tn"] / g["tn_producidas"] * 100).where(g["tn_producidas"] > 0)
    g["cumpl_plan_pct"]     = (g["tn_producidas"] / g["tn_planificadas"] * 100).where(g["tn_planificadas"] > 0)
    return g.sort_values("campo")

def agg_campo_sisa(df):
    g = df.groupby(["empresasucursal", "lugar"]).agg(
        sup_planificada = ("superficieplanificada", "sum"),
        sup_sembrada    = ("superficiesembrada",    "sum"),
        sup_cosechada   = ("superficiecosechada",   "sum"),
        tn_planificadas = ("tnplanificados",        "sum"),
        tn_producidas   = ("tnproducidos",          "sum"),
        tn_resto        = ("restoacosechar",        "sum"),
        lotes           = ("lote",                 "count"),
    ).reset_index()
    g["avance_pct"]     = (g["sup_cosechada"] / g["sup_sembrada"] * 100).where(g["sup_sembrada"] > 0)
    g["rinde_esp_kgha"] = (g["tn_planificadas"] * 1000 / g["sup_planificada"]).where(g["sup_planificada"] > 0)
    g["rinde_obt_kgha"] = (g["tn_producidas"]   * 1000 / g["sup_sembrada"]).where(g["sup_sembrada"] > 0)
    g["desvio_tn"]      = g["tn_producidas"] - g["tn_planificadas"]
    g["desvio_pct"]     = (g["desvio_tn"] / g["tn_planificadas"] * 100).where(g["tn_planificadas"] > 0)
    return g.sort_values(["empresasucursal", "lugar"])

def sup_lote(df):
    return (
        df.groupby(["empresa", "establecimiento", "loteproduccion"])["supsembrada"]
        .first().reset_index().rename(columns={"supsembrada": "sup_ha"})
    )

def agg_campo_rem(df, sup):
    g = df.groupby(["empresa", "establecimiento"]).agg(
        bruto_kg = ("pesoneto",               "sum"),
        fibra_kg = ("cantidadproducidakilos",  "sum"),
        fardos   = ("cantidadproducidafardos", "sum"),
        remitos  = ("pesoneto",               "count"),
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
        bruto_kg = ("pesoneto",               "sum"),
        fibra_kg = ("cantidadproducidakilos",  "sum"),
        fardos   = ("cantidadproducidafardos", "sum"),
    ).reset_index()
    g = g.merge(sup, on=["empresa", "establecimiento", "loteproduccion"], how="left")
    g["bruto_tn"]      = g["bruto_kg"] / 1000
    g["fibra_tn"]      = g["fibra_kg"] / 1000
    g["rinde_kgha"]    = (g["bruto_kg"] / g["sup_ha"]).where(g["sup_ha"] > 0)
    g["rinde_desmote"] = (g["fibra_kg"] / g["bruto_kg"] * 100).where(g["bruto_kg"] > 0)
    return g.sort_values(["empresa", "establecimiento", "loteproduccion"])

def agg_desmotadora(df):
    g = df.groupby(["desmotadora", "empresa", "establecimiento"]).agg(
        entrega_kg = ("pesoneto",              "sum"),
        fibra_kg   = ("cantidadproducidakilos","sum"),
        fardos     = ("cantidadproducidafardos","sum"),
    ).reset_index()
    g["rinde_desmote"] = (g["fibra_kg"] / g["entrega_kg"] * 100).where(g["entrega_kg"] > 0)
    g["ppf_kg"]        = (g["entrega_kg"] / g["fardos"]).where(g["fardos"] > 0)
    return g.sort_values(["desmotadora", "establecimiento"])

def agg_contratista(df):
    g = df.groupby("contratistacosecha").agg(
        bruto_kg = ("pesoneto",               "sum"),
        fibra_kg = ("cantidadproducidakilos",  "sum"),
        fardos   = ("cantidadproducidafardos", "sum"),
    ).reset_index()
    g["rinde_desmote"] = (g["fibra_kg"] / g["bruto_kg"] * 100).where(g["bruto_kg"] > 0)
    return g.sort_values("bruto_kg", ascending=False)

def agg_semanal(df):
    g = df.copy()
    g["semana"] = g["fecha"].dt.to_period("W").dt.start_time
    return g.groupby("semana").agg(
        bruto_kg = ("pesoneto",               "sum"),
        fardos   = ("cantidadproducidafardos", "sum"),
    ).reset_index()

def cruce_campo(sisa_df, rem_df):
    sisa_agg = sisa_df.groupby("lugar").agg(
        sup_sembrada      = ("superficiesembrada",          "sum"),
        sup_cosechada     = ("superficiecosechada",         "sum"),
        tn_planificadas   = ("tnplanificados",              "sum"),
        tn_producidas     = ("tnproducidos",                "sum"),
        rollos_producidos = ("cantidadproducidasecundaria", "sum"),
    ).reset_index().rename(columns={"lugar": "campo"})
    sisa_agg["avance_cos_pct"] = (
        sisa_agg["sup_cosechada"] / sisa_agg["sup_sembrada"] * 100
    ).where(sisa_agg["sup_sembrada"] > 0)

    rem_agg = (
        rem_df.groupby("establecimiento")
        .agg(
            bruto_tn      = ("pesoneto", "sum"),
            cant_remitos  = ("pesoneto", "count"),
            primer_remito = ("fecha",    "min"),
            ultimo_remito = ("fecha",    "max"),
        )
        .reset_index()
        .rename(columns={"establecimiento": "campo"})
    )
    rem_agg["bruto_tn"] /= 1000

    if "producto" in rem_df.columns and "cantidadstock2" in rem_df.columns:
        rem_rol = rem_df[rem_df["producto"].str.contains("Rollos", case=False, na=False)]
        rol_agg = (
            rem_rol.groupby("establecimiento")
            .agg(rollos_cargados=("cantidadstock2", "sum"))
            .reset_index()
            .rename(columns={"establecimiento": "campo"})
        )
    else:
        rol_agg = pd.DataFrame(columns=["campo", "rollos_cargados"])

    g = sisa_agg.merge(rem_agg, on="campo", how="left")
    g = g.merge(rol_agg, on="campo", how="left")
    for col in ["bruto_tn", "rollos_cargados", "cant_remitos"]:
        g[col] = g[col].fillna(0)
    g["en_estab_tn"]     = (g["tn_producidas"] - g["bruto_tn"]).clip(lower=0)
    g["pct_entregado"]   = (g["bruto_tn"]      / g["tn_producidas"]   * 100).where(g["tn_producidas"]   > 0)
    g["cumpl_plan_pct"]  = (g["tn_producidas"] / g["tn_planificadas"] * 100).where(g["tn_planificadas"] > 0)
    g["delta_rollos"]    = g["rollos_cargados"] - g["rollos_producidos"]
    g["pct_rollos_carg"] = (g["rollos_cargados"] / g["rollos_producidos"] * 100).where(g["rollos_producidos"] > 0)
    return g.sort_values("campo")


def cruce_lote(sisa_df, rem_df):
    sisa_l = sisa_df[
        ["lugar", "lote", "tnproducidos", "superficiecosechada",
         "porcentajeavance", "cantidadproducidasecundaria"]
    ].rename(columns={
        "lugar":                      "campo",
        "tnproducidos":               "tn_producidas",
        "superficiecosechada":        "sup_cosechada",
        "porcentajeavance":           "avance_pct",
        "cantidadproducidasecundaria":"rollos_producidos",
    })
    rem_l = (
        rem_df.groupby(["establecimiento", "loteproduccion"])
        .agg(bruto_tn=("pesoneto", "sum"), remitos=("pesoneto", "count"))
        .reset_index()
        .rename(columns={"establecimiento": "campo", "loteproduccion": "lote"})
    )
    rem_l["bruto_tn"] /= 1000
    g = sisa_l.merge(rem_l, on=["campo", "lote"], how="outer")
    g["bruto_tn"]      = g["bruto_tn"].fillna(0)
    g["pct_entregado"] = (g["bruto_tn"] / g["tn_producidas"] * 100).where(
        g["tn_producidas"].notna() & (g["tn_producidas"] > 0)
    )
    return g.sort_values(["campo", "lote"])


def cruce_fechas(sisa_df, rem_df):
    date_cols = [c for c in ["fechaprimeracosecha", "fechaultimacosecha"] if c in sisa_df.columns]
    if not date_cols:
        return pd.DataFrame()
    sisa_df = sisa_df.copy()
    for col in date_cols:
        sisa_df[col] = pd.to_datetime(sisa_df[col], errors="coerce")
    agg_spec = {}
    if "fechaprimeracosecha" in date_cols:
        agg_spec["primera_cosecha"] = ("fechaprimeracosecha", "min")
    if "fechaultimacosecha" in date_cols:
        agg_spec["ultima_cosecha"] = ("fechaultimacosecha", "max")
    sisa_f = sisa_df.groupby("lugar").agg(**agg_spec).reset_index().rename(columns={"lugar": "campo"})
    rem_f = (
        rem_df[rem_df["fecha"].notna()]
        .groupby("establecimiento")
        .agg(primer_remito=("fecha", "min"), ultimo_remito=("fecha", "max"), cant_remitos=("fecha", "count"))
        .reset_index()
        .rename(columns={"establecimiento": "campo"})
    )
    g = sisa_f.merge(rem_f, on="campo", how="left")
    if "primera_cosecha" in g.columns and "primer_remito" in g.columns:
        g["dias_cosecha_remito"] = (g["primer_remito"] - g["primera_cosecha"]).dt.days
    if "primera_cosecha" in g.columns and "ultimo_remito" in g.columns:
        g["duracion_total_dias"] = (g["ultimo_remito"] - g["primera_cosecha"]).dt.days
    return g.sort_values("campo")

# ═══════════════════════════════════════════════════════════════════════════════
# UI — CSS + helpers visuales
# ═══════════════════════════════════════════════════════════════════════════════

st.markdown("""
<style>
/* Fondo sutil */
[data-testid="stAppViewContainer"] > .main {
    background: linear-gradient(160deg, #f4fdf7 0%, #edf9f2 60%, #f9fffc 100%);
}
[data-testid="stSidebar"] {
    background: #ffffff;
    border-right: 1px solid #e0f2e9;
}

/* Headers de sección */
[data-testid="stAppViewContainer"] h2 {
    color: #1a5c2a;
    font-weight: 800;
    letter-spacing: -0.02em;
    border-bottom: 2px solid #2ecc71;
    padding-bottom: 6px;
    margin-bottom: 18px !important;
}
[data-testid="stAppViewContainer"] h3 {
    color: #1a5c2a;
    font-weight: 700;
}

/* KPI cards */
.kpi-card {
    background: white;
    border-radius: 14px;
    padding: 18px 20px 14px 20px;
    box-shadow: 0 2px 14px rgba(0,0,0,0.07);
    border-top: 3px solid #2ecc71;
    transition: transform 0.2s ease, box-shadow 0.2s ease;
    margin-bottom: 6px;
    min-height: 96px;
}
.kpi-card:hover {
    transform: translateY(-4px);
    box-shadow: 0 10px 28px rgba(46,204,113,0.20);
}
.kpi-label {
    font-size: 0.68rem;
    color: #888;
    font-weight: 700;
    text-transform: uppercase;
    letter-spacing: 0.07em;
    margin-bottom: 7px;
}
.kpi-value {
    font-size: 1.55rem;
    font-weight: 900;
    color: #111;
    line-height: 1.15;
}
.kpi-delta {
    font-size: 0.72rem;
    font-weight: 600;
    margin-top: 5px;
}

/* Botón actualizar */
[data-testid="stBaseButton-secondary"] {
    border: 1.5px solid #2ecc71 !important;
    color: #1a5c2a !important;
    border-radius: 20px !important;
    font-weight: 600 !important;
    transition: all 0.2s !important;
}
[data-testid="stBaseButton-secondary"]:hover {
    background: #2ecc71 !important;
    color: white !important;
}

/* Botones de descarga */
[data-testid="stDownloadButton"] button {
    background: transparent !important;
    border: 1px solid #2ecc71 !important;
    color: #1a5c2a !important;
    font-size: 0.78rem !important;
    border-radius: 20px !important;
    padding: 4px 14px !important;
    transition: all 0.2s !important;
}
[data-testid="stDownloadButton"] button:hover {
    background: #2ecc71 !important;
    color: white !important;
}

/* Ocultar footer de Streamlit */
footer { visibility: hidden; }
#MainMenu { visibility: hidden; }
</style>
""", unsafe_allow_html=True)


def kpi_card(label, value, delta=None, delta_color="normal"):
    delta_html = ""
    if delta is not None:
        s = str(delta).strip()
        neg = s.startswith("-")
        if delta_color == "normal":
            color, arrow = ("#e74c3c", "▼") if neg else ("#27ae60", "▲")
        elif delta_color == "inverse":
            color, arrow = ("#27ae60", "▼") if neg else ("#e74c3c", "▲")
        else:
            color, arrow = "#95a5a6", "→"
        delta_html = f'<div class="kpi-delta" style="color:{color}">{arrow} {s}</div>'
    return (
        f'<div class="kpi-card">'
        f'<div class="kpi-label">{label}</div>'
        f'<div class="kpi-value">{value}</div>'
        f'{delta_html}'
        f'</div>'
    )


# ── header ────────────────────────────────────────────────────────────────────

col_btn, col_ts = st.columns([1, 9])
with col_btn:
    if st.button("↺ Actualizar"):
        st.cache_data.clear()
        st.session_state.pop("last_update", None)
        st.rerun()

# ── data load (resilient — partial mode if one API fails) ─────────────────────

raw_rem  = None
raw_sisa = None
sisa_error = None
rem_error  = None

try:
    raw_rem = clean_remitos(fetch_remitos())
except Exception as e:
    rem_error = str(e)

try:
    raw_sisa = clean_sisa(fetch_sisa())
except Exception as e:
    sisa_error = str(e)

if raw_rem is None and raw_sisa is None:
    st.error("No se pudo conectar con ningún servicio de Finnegans. Verificá las credenciales.")
    st.stop()

if "last_update" not in st.session_state:
    st.session_state.last_update = datetime.datetime.now().strftime("%d/%m/%Y %H:%M")

ultimo_remito = (
    raw_rem["fecha"].max().strftime("%d/%m/%Y")
    if raw_rem is not None and not raw_rem["fecha"].isna().all()
    else "—"
)

with col_ts:
    st.markdown(
        f"""
        <div style="
            background: linear-gradient(135deg, #1a5c2a 0%, #27ae60 60%, #2ecc71 100%);
            border-radius: 14px;
            padding: 18px 28px;
            display: flex;
            justify-content: space-between;
            align-items: center;
            box-shadow: 0 4px 20px rgba(46,204,113,0.25);
        ">
            <div>
                <div style="color:white;font-size:1.55rem;font-weight:900;letter-spacing:-0.02em;line-height:1.1">
                    🌿 Control de Cosecha de Algodón
                </div>
                <div style="color:rgba(255,255,255,0.82);font-size:0.85rem;margin-top:4px">
                    Grupo Duhau · Campaña 2025/26 · Finnegans API
                </div>
            </div>
            <div style="text-align:right;color:rgba(255,255,255,0.75);font-size:0.78rem;line-height:1.7">
                <div>Actualizado: <b style="color:white">{st.session_state.last_update}</b></div>
                <div>Último remito: <b style="color:white">{ultimo_remito}</b></div>
                <div style="font-size:0.70rem">↺ auto-refresh cada 5 min</div>
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )

st.markdown("<div style='margin-top:8px'></div>", unsafe_allow_html=True)

if sisa_error:
    st.warning(f"⚠️ Planificación SISA no disponible: {sisa_error}")
if rem_error:
    st.warning(f"⚠️ Remitos no disponibles: {rem_error}")

# ── sidebar ───────────────────────────────────────────────────────────────────

with st.sidebar:
    st.header("Filtros")
    pagina = st.radio(
        "Pantalla",
        ["📊 Dashboard", "🔗 Información Cruzada"],
        label_visibility="collapsed",
    )
    st.markdown("---")

    empresas_sisa = set(raw_sisa["empresasucursal"].dropna().unique()) if raw_sisa is not None else set()
    empresas_rem  = set(raw_rem["empresa"].dropna().unique()) if raw_rem is not None else set()
    empresas      = sorted(empresas_sisa | empresas_rem)
    sel_empresa   = st.multiselect("Empresa", empresas, default=empresas)

    campos_disponibles = []
    if raw_sisa is not None:
        campos_disponibles = sorted(
            raw_sisa[raw_sisa["empresasucursal"].isin(sel_empresa)]["lugar"].dropna().unique()
        )
    sel_campos = st.multiselect("Campo", campos_disponibles, default=campos_disponibles)

    campanias = []
    if raw_rem is not None:
        campanias = sorted(raw_rem["campania_norm"].dropna().unique(), reverse=True)
    sel_camp = st.selectbox("Campaña", campanias) if campanias else "25-26"

    # date range filter
    d_desde = d_hasta = None
    if raw_rem is not None and not raw_rem["fecha"].isna().all():
        fecha_min = raw_rem["fecha"].min().date()
        fecha_max = raw_rem["fecha"].max().date()
        sel_fecha = st.date_input(
            "Período de remitos",
            value=(fecha_min, fecha_max),
            min_value=fecha_min,
            max_value=fecha_max,
        )
        if isinstance(sel_fecha, (list, tuple)) and len(sel_fecha) == 2:
            d_desde, d_hasta = sel_fecha
        elif isinstance(sel_fecha, (list, tuple)) and len(sel_fecha) == 1:
            d_desde = d_hasta = sel_fecha[0]
        else:
            d_desde = d_hasta = sel_fecha

    st.markdown("---")

    sisa = pd.DataFrame()
    if raw_sisa is not None:
        sisa = raw_sisa[
            raw_sisa["empresasucursal"].isin(sel_empresa) &
            raw_sisa["lugar"].isin(sel_campos)
        ].copy()

    rem = pd.DataFrame()
    if raw_rem is not None:
        mask = (
            raw_rem["empresa"].isin(sel_empresa) &
            (raw_rem["campania_norm"] == sel_camp)
        )
        if sel_campos:
            mask &= raw_rem["establecimiento"].isin(sel_campos)
        if d_desde and d_hasta:
            # incluir remitos sin fecha — excluirlos por dato faltante genera subconteo silencioso
            mask &= (
                raw_rem["fecha"].isna() |
                (
                    (raw_rem["fecha"].dt.date >= d_desde) &
                    (raw_rem["fecha"].dt.date <= d_hasta)
                )
            )
        rem = raw_rem[mask].copy()

    st.caption(f"SISA: {len(sisa)} lotes")
    st.caption(f"Remitos: {len(rem)} registros")
    if d_desde and d_hasta:
        sin_fecha = rem["fecha"].isna().sum()
        aviso = f" · {sin_fecha} sin fecha" if sin_fecha > 0 else ""
        st.caption(f"Período: {d_desde.strftime('%d/%m')} → {d_hasta.strftime('%d/%m')}{aviso}")

# ═══════════════════════════════════════════════════════════════════════════════
# PÁGINA — INFORMACIÓN CRUZADA
# ═══════════════════════════════════════════════════════════════════════════════

if "Cruzada" in pagina:
    st.header("Información Cruzada")

    if sisa.empty and rem.empty:
        st.warning("Sin datos para los filtros seleccionados.")
        st.stop()

    tab_campo, tab_lote, tab_rollos, tab_fechas = st.tabs(
        ["Por Campo", "Por Lote", "Rollos", "Fechas"]
    )

    # ── Por Campo ────────────────────────────────────────────────────────────
    with tab_campo:
        if sisa.empty:
            st.info("Sin datos SISA para los filtros seleccionados.")
        else:
            gc = cruce_campo(sisa, rem)

            tot_prod     = gc["tn_producidas"].sum()
            tot_entr     = gc["bruto_tn"].sum()
            tot_en_est   = gc["en_estab_tn"].sum()
            pct_entr     = tot_entr / tot_prod * 100 if tot_prod > 0 else 0
            tot_rol_prod = gc["rollos_producidos"].sum()
            tot_rol_carg = gc["rollos_cargados"].sum()

            c1, c2, c3, c4 = st.columns(4)
            c1.markdown(kpi_card("Tn Producidas (SISA)", f"{tot_prod:,.1f}"), unsafe_allow_html=True)
            c2.markdown(kpi_card("Entregado a Desm.", f"{tot_entr:,.1f} Tn",
                delta=f"{pct_entr:.0f}% entregado", delta_color="off"), unsafe_allow_html=True)
            c3.markdown(kpi_card("En Establecimiento", f"{tot_en_est:,.1f} Tn"), unsafe_allow_html=True)
            c4.markdown(kpi_card("Δ Rollos (Carg − Prod)", f"{tot_rol_carg - tot_rol_prod:+,.0f}",
                delta_color="off"), unsafe_allow_html=True)

            fig_gc = px.bar(
                gc.melt(
                    id_vars="campo",
                    value_vars=["tn_producidas", "bruto_tn", "en_estab_tn"],
                    var_name="origen", value_name="tn",
                ).replace({
                    "tn_producidas": "Producido (SISA)",
                    "bruto_tn":      "Entregado (Remitos)",
                    "en_estab_tn":   "En Establecimiento",
                }),
                x="campo", y="tn", color="origen", barmode="group",
                labels={"tn": "Tn", "campo": "", "origen": ""},
                color_discrete_map={
                    "Producido (SISA)":    "#aed6f1",
                    "Entregado (Remitos)": "#2ecc71",
                    "En Establecimiento":  "#f39c12",
                },
                height=380,
            )
            fig_gc.update_layout(
                margin=dict(l=0, r=0, t=10, b=40), legend_title="",
                xaxis_tickangle=-30,
                plot_bgcolor="rgba(0,0,0,0)", paper_bgcolor="rgba(0,0,0,0)",
            )
            st.plotly_chart(fig_gc, use_container_width=True)
            st.divider()

            cols_disp = {
                "campo":            "Campo",
                "tn_planificadas":  "Tn Plan",
                "tn_producidas":    "Tn Prod (SISA)",
                "cumpl_plan_pct":   "% vs Plan",
                "avance_cos_pct":   "Avance Cos %",
                "bruto_tn":         "Entregado Tn",
                "pct_entregado":    "% Entregado",
                "en_estab_tn":      "En Estab Tn",
                "rollos_producidos":"Rollos Prod",
                "rollos_cargados":  "Rollos Carg",
                "delta_rollos":     "Δ Rollos",
                "pct_rollos_carg":  "% Rollos Carg",
                "cant_remitos":     "N° Remitos",
            }
            disp_gc = gc.rename(columns=cols_disp)[list(cols_disp.values())]
            disp_gc_tot = totales_row(disp_gc, "Campo")
            n_gc = len(disp_gc)
            st.dataframe(
                style_total_row(
                    disp_gc_tot.style
                        .format(fmt_num(disp_gc_tot), na_rep="—")
                        .map(sem_avance, subset=["Avance Cos %"])
                        .map(sem_avance_entrega, subset=["% Entregado"]),
                    n_gc,
                ),
                use_container_width=True, hide_index=True,
            )
            download_btn(disp_gc, "cruce_campo.xlsx")

    # ── Por Lote ─────────────────────────────────────────────────────────────
    with tab_lote:
        if sisa.empty:
            st.info("Sin datos SISA para los filtros seleccionados.")
        else:
            gl = cruce_lote(sisa, rem)

            gl_scatter = gl.dropna(subset=["tn_producidas"])
            if not gl_scatter.empty:
                max_val = max(
                    gl_scatter["tn_producidas"].max(),
                    gl_scatter["bruto_tn"].max() if gl_scatter["bruto_tn"].max() > 0 else 1,
                )
                fig_gl = px.scatter(
                    gl_scatter,
                    x="tn_producidas", y="bruto_tn",
                    color="campo", hover_data=["lote", "avance_pct"],
                    labels={
                        "tn_producidas": "Tn Producidas (SISA)",
                        "bruto_tn":      "Entregado Remitos (Tn)",
                        "campo":         "Campo",
                    },
                    height=420,
                )
                fig_gl.add_scatter(
                    x=[0, max_val], y=[0, max_val],
                    mode="lines",
                    line=dict(dash="dot", color="#aaa", width=1),
                    name="Producido = Entregado", showlegend=True,
                )
                fig_gl.update_layout(
                    margin=dict(l=0, r=0, t=10, b=0), legend_title="",
                    plot_bgcolor="rgba(0,0,0,0)", paper_bgcolor="rgba(0,0,0,0)",
                )
                st.plotly_chart(fig_gl, use_container_width=True)
                st.divider()

            cols_l = {
                "campo":            "Campo",
                "lote":             "Lote",
                "tn_producidas":    "Tn Prod (SISA)",
                "sup_cosechada":    "Sup Cos ha",
                "avance_pct":       "Avance %",
                "rollos_producidos":"Rollos Prod",
                "bruto_tn":         "Entregado Tn",
                "remitos":          "N° Remitos",
                "pct_entregado":    "% Entregado",
            }
            disp_gl = gl.rename(columns=cols_l)[[v for v in cols_l.values() if v in gl.rename(columns=cols_l).columns]]
            st.dataframe(
                disp_gl.style
                    .format(fmt_num(disp_gl), na_rep="—")
                    .map(sem_avance, subset=[c for c in ["Avance %"] if c in disp_gl.columns])
                    .map(sem_avance_entrega, subset=[c for c in ["% Entregado"] if c in disp_gl.columns]),
                use_container_width=True, hide_index=True,
            )
            download_btn(disp_gl, "cruce_lote.xlsx")

    # ── Rollos ───────────────────────────────────────────────────────────────
    with tab_rollos:
        if sisa.empty:
            st.info("Sin datos SISA para los filtros seleccionados.")
        else:
            gc_r = cruce_campo(sisa, rem)[
                ["campo", "rollos_producidos", "rollos_cargados", "delta_rollos", "pct_rollos_carg"]
            ]
            gc_r = gc_r[(gc_r["rollos_producidos"] > 0) | (gc_r["rollos_cargados"] > 0)]
            if gc_r.empty:
                st.info("No hay datos de rollos para los campos seleccionados.")
            else:
                fig_gr = px.bar(
                    gc_r.melt(
                        id_vars="campo",
                        value_vars=["rollos_producidos", "rollos_cargados"],
                        var_name="tipo", value_name="rollos",
                    ).replace({
                        "rollos_producidos": "Producidos (SISA)",
                        "rollos_cargados":   "Cargados (Remitos)",
                    }),
                    x="campo", y="rollos", color="tipo", barmode="group",
                    labels={"rollos": "Rollos", "campo": "", "tipo": ""},
                    color_discrete_map={
                        "Producidos (SISA)":  "#aed6f1",
                        "Cargados (Remitos)": "#2ecc71",
                    },
                    text_auto=True,
                    height=360,
                )
                fig_gr.update_layout(
                    margin=dict(l=0, r=0, t=10, b=40), legend_title="",
                    xaxis_tickangle=-30,
                    plot_bgcolor="rgba(0,0,0,0)", paper_bgcolor="rgba(0,0,0,0)",
                )
                st.plotly_chart(fig_gr, use_container_width=True)
                st.divider()

                disp_r = gc_r.rename(columns={
                    "campo":             "Campo",
                    "rollos_producidos": "Producidos (SISA)",
                    "rollos_cargados":   "Cargados (Remitos)",
                    "delta_rollos":      "Diferencia",
                    "pct_rollos_carg":   "% Cargado",
                })
                disp_r_tot = totales_row(disp_r, "Campo")
                n_r = len(disp_r)
                st.dataframe(
                    style_total_row(
                        disp_r_tot.style.format(fmt_num(disp_r_tot)),
                        n_r,
                    ),
                    use_container_width=True, hide_index=True,
                )
                download_btn(disp_r, "cruce_rollos.xlsx")

    # ── Fechas ───────────────────────────────────────────────────────────────
    with tab_fechas:
        if sisa.empty or rem.empty:
            st.info("Se necesitan datos de ambas fuentes para el cruce de fechas.")
        else:
            gf = cruce_fechas(sisa, rem)

            if gf.empty:
                st.info("No hay columnas de fecha de cosecha en SISA.")
            else:
                gantt_df = gf.dropna(subset=["primera_cosecha", "ultimo_remito"]).rename(columns={
                    "campo":          "Campo",
                    "primera_cosecha":"Inicio",
                    "ultimo_remito":  "Fin",
                })
                if not gantt_df.empty:
                    fig_gf = px.timeline(
                        gantt_df,
                        x_start="Inicio", x_end="Fin", y="Campo",
                        color="Campo",
                        color_discrete_sequence=px.colors.qualitative.Set2,
                        height=max(300, len(gantt_df) * 40 + 80),
                    )
                    fig_gf.update_layout(
                        showlegend=False,
                        margin=dict(l=0, r=0, t=10, b=0),
                        plot_bgcolor="rgba(0,0,0,0)", paper_bgcolor="rgba(0,0,0,0)",
                    )
                    st.plotly_chart(fig_gf, use_container_width=True)
                    st.divider()

                gf_disp = gf.copy()
                for col in ["primera_cosecha", "ultima_cosecha", "primer_remito", "ultimo_remito"]:
                    if col in gf_disp.columns:
                        gf_disp[col] = gf_disp[col].dt.strftime("%d/%m/%Y").where(gf_disp[col].notna(), "—")
                for col in ["cant_remitos", "dias_cosecha_remito", "duracion_total_dias"]:
                    if col in gf_disp.columns:
                        gf_disp[col] = gf_disp[col].apply(
                            lambda v: "—" if pd.isna(v) else f"{int(v):,}"
                        )

                rename_f = {
                    "campo":               "Campo",
                    "primera_cosecha":     "1ra Cosecha (SISA)",
                    "ultima_cosecha":      "Últ Cosecha (SISA)",
                    "primer_remito":       "1er Remito",
                    "ultimo_remito":       "Últ Remito",
                    "cant_remitos":        "N° Remitos",
                    "dias_cosecha_remito": "Días 1ra Cos → 1er Rem",
                    "duracion_total_dias": "Duración Total (días)",
                }
                disp_f = gf_disp.rename(columns=rename_f)[[v for k, v in rename_f.items() if k in gf_disp.columns]]
                st.dataframe(disp_f, use_container_width=True, hide_index=True)
                download_btn(gf_disp.rename(columns=rename_f), "cruce_fechas.xlsx")

    st.stop()

# ═══════════════════════════════════════════════════════════════════════════════
# SECCIÓN 0 — RESUMEN GENERAL
# ═══════════════════════════════════════════════════════════════════════════════

st.header("Resumen General")

if not sisa.empty:
    rc = resumen_cruzado(sisa, rem)

    tot_semb     = rc["sup_sembrada"].sum()
    tot_plan     = rc["tn_planificadas"].sum()
    tot_prod     = rc["tn_producidas"].sum()
    tot_entreg   = rc["entregado_tn"].sum()
    tot_en_est   = rc["en_establecimiento"].sum()
    tot_rol_prod = rc["rollos_producidos"].sum()
    tot_rol_carg = rc["rollos_cargados"].sum()
    pct_entrega  = tot_entreg / tot_prod * 100 if tot_prod > 0 else 0
    pct_en_est   = tot_en_est / tot_prod * 100 if tot_prod > 0 else 0

    c1, c2, c3, c4 = st.columns(4)
    c1.markdown(kpi_card("Sup Sembrada", f"{tot_semb:,.0f} ha"), unsafe_allow_html=True)
    c2.markdown(kpi_card("Tn Planificadas", f"{tot_plan:,.1f} Tn"), unsafe_allow_html=True)
    c3.markdown(kpi_card("Tn Producidas", f"{tot_prod:,.1f} Tn",
        delta=f"{tot_prod - tot_plan:+,.1f} Tn vs plan"), unsafe_allow_html=True)
    c4.markdown(kpi_card("Entregado a Desm.", f"{tot_entreg:,.1f} Tn",
        delta=f"{pct_entrega:.0f}% del total prod.", delta_color="off"), unsafe_allow_html=True)

    c5, c6, c7, _ = st.columns(4)
    c5.markdown(kpi_card("En Establecimiento", f"{tot_en_est:,.1f} Tn",
        delta=f"{pct_en_est:.0f}% sin entregar", delta_color="inverse"), unsafe_allow_html=True)
    c6.markdown(kpi_card("Rollos Producidos", f"{tot_rol_prod:,.0f}"), unsafe_allow_html=True)
    c7.markdown(kpi_card("Rollos Cargados", f"{tot_rol_carg:,.0f}",
        delta=f"{tot_rol_carg - tot_rol_prod:+,.0f} vs prod.", delta_color="off"), unsafe_allow_html=True)

    # progress bar: % entregado del total producido
    st.progress(
        min(pct_entrega / 100, 1.0),
        text=f"Entregado a desmotadora: {pct_entrega:.1f}% de lo producido",
    )

    # stacked bar: entregado vs en establecimiento por campo, planificado como referencia
    rc_melt = rc[["campo", "entregado_tn", "en_establecimiento"]].melt(
        id_vars="campo",
        value_vars=["entregado_tn", "en_establecimiento"],
        var_name="estado", value_name="tn",
    ).replace({
        "entregado_tn":       "Entregado a Desm.",
        "en_establecimiento": "En Establecimiento",
    })
    fig_rc = px.bar(
        rc_melt,
        x="campo", y="tn", color="estado", barmode="stack",
        labels={"tn": "Tn", "campo": "", "estado": ""},
        color_discrete_map={
            "Entregado a Desm.":  "#2ecc71",
            "En Establecimiento": "#f39c12",
        },
    )
    fig_rc.add_scatter(
        x=rc["campo"], y=rc["tn_planificadas"],
        mode="markers", name="Planificado",
        marker=dict(symbol="diamond", size=12, color="#2980b9",
                    line=dict(width=1, color="#1a5276")),
    )
    fig_rc.update_layout(
        height=380, margin=dict(l=0, r=0, t=10, b=40),
        legend_title="", xaxis_tickangle=-30,
    )
    st.plotly_chart(fig_rc, use_container_width=True)

    st.divider()

    disp_rc = rc.rename(columns={
        "campo":              "Campo",
        "sup_sembrada":       "Sup Semb ha",
        "tn_planificadas":    "Tn Plan",
        "tn_producidas":      "Tn Prod",
        "cumpl_plan_pct":     "% vs Plan",
        "entregado_tn":       "Entregado Tn",
        "avance_entrega_pct": "% Entregado",
        "en_establecimiento": "En Estab. Tn",
        "rollos_producidos":  "Rollos Prod",
        "rollos_cargados":    "Rollos Carg",
    })
    disp_rc_tot = totales_row(disp_rc, "Campo")
    n = len(disp_rc)

    st.dataframe(
        style_total_row(
            disp_rc_tot.style
                .format(fmt_num(disp_rc_tot), na_rep="—")
                .map(sem_en_est, subset=["En Estab. Tn"])
                .map(sem_avance_entrega, subset=["% Entregado"]),
            n,
        ),
        use_container_width=True,
        hide_index=True,
    )
    download_btn(disp_rc, "resumen_general.xlsx")

else:
    st.info("Sin datos de planificación SISA para los filtros seleccionados.")

st.divider()

# ═══════════════════════════════════════════════════════════════════════════════
# SECCIÓN 1 — PLANIFICACIÓN DE CAMPAÑA (SISA)
# ═══════════════════════════════════════════════════════════════════════════════

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

    c1, c2, c3, c4 = st.columns(4)
    c1.markdown(kpi_card("Sup Planificada", f"{tot_sup_plan:,.0f} ha"), unsafe_allow_html=True)
    c2.markdown(kpi_card("Sup Sembrada",    f"{tot_sup_semb:,.0f} ha"), unsafe_allow_html=True)
    c3.markdown(kpi_card("Sup Cosechada",   f"{tot_sup_cos:,.0f} ha"), unsafe_allow_html=True)
    c4.markdown(kpi_card("Avance Global", f"{avance_gl:.1f}%",
        delta=f"{avance_gl - 100:.1f}% restante", delta_color="inverse"), unsafe_allow_html=True)

    c5, c6, c7, _ = st.columns(4)
    c5.markdown(kpi_card("Tn Planificadas", f"{tot_tn_plan:,.0f}"), unsafe_allow_html=True)
    c6.markdown(kpi_card("Tn Producidas", f"{tot_tn_prod:,.0f}",
        delta=f"{tot_tn_prod - tot_tn_plan:+,.0f} vs plan"), unsafe_allow_html=True)
    c7.markdown(kpi_card("Resto a Cosechar", f"{tot_resto:,.0f} ha"), unsafe_allow_html=True)

    st.progress(
        min(avance_gl / 100, 1.0),
        text=f"Avance de cosecha: {avance_gl:.1f}% de la superficie sembrada",
    )

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
        fig_av.update_traces(
            texttemplate="%{text:.1f}%", textposition="outside",
            hovertemplate="<b>%{y}</b><br>Avance: <b>%{x:.1f}%</b><extra></extra>",
        )
        fig_av.update_layout(
            height=420, margin=dict(l=0, r=40, t=0, b=0),
            coloraxis_showscale=False,
            plot_bgcolor="rgba(0,0,0,0)", paper_bgcolor="rgba(0,0,0,0)",
            hoverlabel=dict(bgcolor="white", font_size=13, bordercolor="#2ecc71"),
        )
        st.plotly_chart(fig_av, use_container_width=True)

    with col_g2:
        st.subheader("Rinde planificado vs producido (kg/ha)")
        df_rinde_melt = vc_sisa.melt(
            id_vars="lugar",
            value_vars=["rinde_esp_kgha", "rinde_obt_kgha"],
            var_name="tipo", value_name="kg_ha",
        ).replace({"rinde_esp_kgha": "Planificado", "rinde_obt_kgha": "Producido"})
        fig_rinde = px.bar(
            df_rinde_melt,
            x="lugar", y="kg_ha", color="tipo", barmode="group",
            labels={"kg_ha": "kg/ha", "lugar": "", "tipo": ""},
            color_discrete_map={"Planificado": "#aed6f1", "Producido": "#2ecc71"},
        )
        fig_rinde.update_traces(
            hovertemplate="<b>%{x}</b><br>%{data.name}: <b>%{y:,.0f} kg/ha</b><extra></extra>",
        )
        fig_rinde.update_layout(
            height=420, margin=dict(l=0, r=0, t=0, b=0), legend_title="",
            plot_bgcolor="rgba(0,0,0,0)", paper_bgcolor="rgba(0,0,0,0)",
            hoverlabel=dict(bgcolor="white", font_size=13, bordercolor="#aed6f1"),
        )
        st.plotly_chart(fig_rinde, use_container_width=True)

    st.subheader("Detalle por campo — Planificado vs Real")
    disp_sisa = vc_sisa.rename(columns={
        "empresasucursal":  "Sucursal",
        "lugar":            "Campo",
        "lotes":            "Lotes",
        "sup_planificada":  "S.Plan ha",
        "sup_sembrada":     "S.Semb ha",
        "sup_cosechada":    "S.Cos ha",
        "avance_pct":       "Avance %",
        "tn_planificadas":  "Tn Plan",
        "tn_producidas":    "Tn Prod",
        "tn_resto":         "Resto ha",
        "desvio_tn":        "Desvío Tn",
        "desvio_pct":       "Desvío %",
        "rinde_esp_kgha":   "R.Esp kg/ha",
        "rinde_obt_kgha":   "R.Obt kg/ha",
    })[["Sucursal", "Campo", "Lotes", "S.Plan ha", "S.Semb ha", "S.Cos ha",
        "Avance %", "Tn Plan", "Tn Prod", "Desvío Tn", "Desvío %",
        "R.Esp kg/ha", "R.Obt kg/ha"]]

    disp_sisa_tot = totales_row(disp_sisa, "Campo")
    n_sisa = len(disp_sisa)
    st.dataframe(
        style_total_row(
            disp_sisa_tot.style
                .format(fmt_num(disp_sisa_tot), na_rep="—")
                .map(sem_avance, subset=["Avance %"])
                .map(sem_desvio, subset=["Desvío %"]),
            n_sisa,
        ),
        use_container_width=True,
        hide_index=True,
    )
    download_btn(disp_sisa, "planificacion_campo.xlsx")

    with st.expander("Ver detalle por lote (SISA)"):
        cols_lote = [
            "empresasucursal", "lugar", "lote", "actividad",
            "superficieplanificada", "superficiesembrada", "superficiecosechada",
            "porcentajeavance", "tnplanificados", "tnproducidos",
            "restoacosechar", "rindeesperado", "rindeobtenido",
        ]
        disp_lote_sisa = (
            sisa[[c for c in cols_lote if c in sisa.columns]]
            .sort_values(["empresasucursal", "lugar", "lote"])
            .rename(columns={
                "empresasucursal":      "Sucursal",
                "lugar":                "Campo",
                "lote":                 "Lote",
                "actividad":            "Actividad",
                "superficieplanificada":"S.Plan ha",
                "superficiesembrada":   "S.Semb ha",
                "superficiecosechada":  "S.Cos ha",
                "porcentajeavance":     "Avance %",
                "tnplanificados":       "Tn Plan",
                "tnproducidos":         "Tn Prod",
                "restoacosechar":       "Resto ha",
                "rindeesperado":        "R.Esp kg/ha",
                "rindeobtenido":        "R.Obt kg/ha",
            })
        )
        st.dataframe(
            disp_lote_sisa.style
                .format(fmt_num(disp_lote_sisa), na_rep="—")
                .map(sem_avance, subset=["Avance %"]),
            use_container_width=True,
            hide_index=True,
        )
        download_btn(disp_lote_sisa, "detalle_lotes_sisa.xlsx")

st.divider()

# ═══════════════════════════════════════════════════════════════════════════════
# SECCIÓN 2 — REMITOS DE COSECHA
# ═══════════════════════════════════════════════════════════════════════════════

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

bruto_total = rem["pesoneto"].sum()
fibra_total = rem["cantidadproducidakilos"].sum()
rd_total    = fibra_total / bruto_total * 100 if bruto_total > 0 else 0

c1, c2, c3 = st.columns(3)
c1.markdown(kpi_card("Algodón Bruto",   f"{bruto_total / 1000:,.1f} Tn"), unsafe_allow_html=True)
c2.markdown(kpi_card("Fibra Producida", f"{fibra_total / 1000:,.1f} Tn"), unsafe_allow_html=True)
c3.markdown(kpi_card("Rinde Desmote", f"{rd_total:.1f}%",
    delta=f"{rd_total - 24:.1f}pp vs ref. 24%"), unsafe_allow_html=True)

c4, c5, c6 = st.columns(3)
c4.markdown(kpi_card("Fardos",  f"{int(rem['cantidadproducidafardos'].sum()):,}"), unsafe_allow_html=True)
c5.markdown(kpi_card("Campos",  str(rem['establecimiento'].nunique())), unsafe_allow_html=True)
c6.markdown(kpi_card("Remitos", str(len(rem))), unsafe_allow_html=True)

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
    fig.update_traces(
        hovertemplate="<b>%{y}</b><br>%{data.name}: <b>%{x:,.1f} Tn</b><extra></extra>",
    )
    fig.update_layout(
        height=420, margin=dict(l=0, r=0, t=0, b=0), legend_title="",
        plot_bgcolor="rgba(0,0,0,0)", paper_bgcolor="rgba(0,0,0,0)",
        hoverlabel=dict(bgcolor="white", font_size=13),
    )
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
    fig2.update_traces(
        hovertemplate="<b>%{y}</b><br>%{data.name}: <b>%{x:.1f}%</b><extra></extra>",
    )
    fig2.update_layout(
        height=420, margin=dict(l=0, r=0, t=0, b=0), legend_title="",
        plot_bgcolor="rgba(0,0,0,0)", paper_bgcolor="rgba(0,0,0,0)",
        hoverlabel=dict(bgcolor="white", font_size=13),
    )
    st.plotly_chart(fig2, use_container_width=True)

if not vsem.empty and vsem["semana"].notna().any():
    st.subheader("Remitos por semana (Tn bruto)")
    vsem["bruto_tn"] = vsem["bruto_kg"] / 1000
    fig3 = px.bar(
        vsem, x="semana", y="bruto_tn",
        labels={"semana": "Semana", "bruto_tn": "Tn Algodón Bruto"},
        color_discrete_sequence=["#2ecc71"],
        text="bruto_tn",
    )
    fig3.update_traces(
        texttemplate="%{text:,.1f}", textposition="outside",
        hovertemplate="Semana %{x|%d/%m}<br><b>%{y:,.1f} Tn</b><extra></extra>",
    )
    fig3.update_layout(
        height=300, margin=dict(l=0, r=0, t=10, b=0),
        plot_bgcolor="rgba(0,0,0,0)", paper_bgcolor="rgba(0,0,0,0)",
        hoverlabel=dict(bgcolor="white", font_size=13),
    )
    st.plotly_chart(fig3, use_container_width=True)

st.divider()

st.subheader("Producción por campo")
disp_campo = vc.rename(columns={
    "empresa":       "Empresa",
    "establecimiento":"Campo",
    "sup_ha":        "Sup (ha)",
    "bruto_tn":      "Bruto (Tn)",
    "rinde_kgha":    "Rinde (kg/ha)",
    "fibra_tn":      "Fibra (Tn)",
    "rinde_desmote": "Rinde Desm. (%)",
    "fardos":        "Fardos",
    "ppf_kg":        "PP Fardo (kg)",
    "remitos":       "Remitos",
})[["Empresa", "Campo", "Sup (ha)", "Bruto (Tn)", "Rinde (kg/ha)",
    "Fibra (Tn)", "Rinde Desm. (%)", "Fardos", "PP Fardo (kg)", "Remitos"]]

disp_campo_tot = totales_row(disp_campo, "Empresa", label="TOTAL")
n_campo = len(disp_campo)
st.dataframe(
    style_total_row(
        disp_campo_tot.style
            .format(fmt_num(disp_campo_tot), na_rep="—")
            .map(sem_rinde, subset=["Rinde Desm. (%)"]),
        n_campo,
    ),
    use_container_width=True,
    hide_index=True,
)
download_btn(disp_campo, "produccion_campo.xlsx")

st.subheader("Producción por lote")
disp_lote = vl.rename(columns={
    "empresa":         "Empresa",
    "establecimiento": "Campo",
    "loteproduccion":  "Lote",
    "sup_ha":          "Sup (ha)",
    "bruto_tn":        "Bruto (Tn)",
    "rinde_kgha":      "Rinde (kg/ha)",
    "fibra_tn":        "Fibra (Tn)",
    "rinde_desmote":   "Rinde Desm. (%)",
    "fardos":          "Fardos",
})[["Empresa", "Campo", "Lote", "Sup (ha)", "Bruto (Tn)", "Rinde (kg/ha)",
    "Fibra (Tn)", "Rinde Desm. (%)", "Fardos"]]
st.dataframe(
    disp_lote.style
        .format(fmt_num(disp_lote), na_rep="—")
        .map(sem_rinde, subset=["Rinde Desm. (%)"]),
    use_container_width=True,
    hide_index=True,
)
download_btn(disp_lote, "produccion_lote.xlsx")

st.subheader("Logística por desmotadora")
disp_desm = vd.rename(columns={
    "desmotadora":   "Desmotadora",
    "empresa":       "Empresa",
    "establecimiento":"Campo",
    "entrega_kg":    "Entregado (kg)",
    "fibra_kg":      "Fibra (kg)",
    "rinde_desmote": "Rinde (%)",
    "fardos":        "Fardos",
    "ppf_kg":        "PP Fardo (kg)",
})[["Desmotadora", "Empresa", "Campo", "Entregado (kg)", "Fibra (kg)",
    "Rinde (%)", "Fardos", "PP Fardo (kg)"]]
st.dataframe(
    disp_desm.style
        .format(fmt_num(disp_desm), na_rep="—")
        .map(sem_rinde, subset=["Rinde (%)"]),
    use_container_width=True,
    hide_index=True,
)
download_btn(disp_desm, "logistica_desmotadora.xlsx")

st.subheader("Rinde por contratista")
disp_cont = vcont.rename(columns={
    "contratistacosecha": "Contratista",
    "bruto_kg":           "Bruto (kg)",
    "fibra_kg":           "Fibra (kg)",
    "rinde_desmote":      "Rinde (%)",
    "fardos":             "Fardos",
})[["Contratista", "Bruto (kg)", "Fibra (kg)", "Rinde (%)", "Fardos"]]
st.dataframe(
    disp_cont.style
        .format(fmt_num(disp_cont), na_rep="—")
        .map(sem_rinde, subset=["Rinde (%)"]),
    use_container_width=True,
    hide_index=True,
)
download_btn(disp_cont, "contratistas.xlsx")

# ── footer ────────────────────────────────────────────────────────────────────
st.divider()
st.caption(
    f"Datos con caché de 5 min · "
    f"Actualizado: {st.session_state.last_update} · "
    f"Economart / Grupo Duhau"
)

# ── auto-refresh cada 5 minutos ───────────────────────────────────────────────
time.sleep(300)
st.cache_data.clear()
st.session_state.pop("last_update", None)
st.rerun()
