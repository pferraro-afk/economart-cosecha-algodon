import streamlit as st
import pandas as pd
import numpy as np
import requests
import plotly.express as px
import io
import os
import datetime
from dotenv import load_dotenv

load_dotenv(".env")

# ── credentials ───────────────────────────────────────────────────────────────

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

@st.cache_data(show_spinner="Cargando remitos...")
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

@st.cache_data(show_spinner="Cargando planificación...")
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
    for col in ["pesoneto", "cantidad", "cantidadproducidakilos", "cantidadproducidafardos",
                "rindefibra", "supsembrada", "cantidadstock2", "cantidadconsumo"]:
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
    if "zona" in df.columns:
        df["zona"] = df["zona"].str.strip().str.lower()
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
    sum_cols = [c for c in df.select_dtypes("number").columns if "%" not in c]
    row = {c: np.nan for c in df.columns}
    row[label_col] = label
    for c in sum_cols:
        row[c] = df[c].sum()
    return pd.concat([df, pd.DataFrame([row])], ignore_index=True)

def style_total_row(styled, n_rows):
    return styled.apply(
        lambda row: [
            "font-weight:800;background-color:#e8f5e9;color:#1a5c2a"
            if row.name == n_rows else ""
            for _ in row
        ],
        axis=1,
    )

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

def sem_desvio_kgha(val):
    if pd.isna(val): return ""
    if val >= 0:    return "background-color:#d5f5e3;color:#1a7a40;font-weight:700"
    if val >= -200: return "background-color:#fef9e7;color:#b7950b;font-weight:700"
    return "background-color:#fadbd8;color:#c0392b;font-weight:700"

# ── HTML cosecha table ────────────────────────────────────────────────────────

def _avance_cell_style(v):
    if pd.isna(v): return "background:#f5f5f5;color:#aaa"
    if v >= 90:    return "background:#d5f5e3;color:#1a7a40;font-weight:700"
    if v >= 70:    return "background:#e9f7ef;color:#27ae60;font-weight:700"
    if v >= 50:    return "background:#fef9e7;color:#b7950b;font-weight:700"
    if v >= 30:    return "background:#fdebd0;color:#d35400;font-weight:700"
    return "background:#fadbd8;color:#c0392b;font-weight:700"

def _rrro_cell_style(v):
    if pd.isna(v): return "background:#f5f5f5;color:#aaa"
    if v >= 0:    return "background:#d5f5e3;color:#1a7a40;font-weight:700"
    if v >= -10:  return "background:#fef9e7;color:#b7950b;font-weight:700"
    return "background:#fadbd8;color:#c0392b;font-weight:700"

def _fibra_cell_style(v):
    if pd.isna(v): return "background:#f5f5f5;color:#aaa"
    if v >= 28:   return "background:#d5f5e3;color:#1a7a40;font-weight:700"
    if v >= 24:   return "background:#fef9e7;color:#b7950b;font-weight:700"
    return "background:#fadbd8;color:#c0392b;font-weight:700"

def _f(v, fmt, suffix=""):
    return "—" if (v is None or (isinstance(v, float) and pd.isna(v))) else f"{v:{fmt}}{suffix}"

def render_cosecha_html(rows):
    tbody = ""
    for idx, row in enumerate(rows):
        is_total = row.get("campo") == "TOTAL"
        row_bg = "background:#e8f5e9" if is_total else ("background:#f9f9f9" if idx % 2 == 0 else "background:#ffffff")
        fw     = "font-weight:800;color:#1a5c2a" if is_total else "font-weight:400;color:#222"
        td     = "padding:9px 14px;border-bottom:1px solid #eee"
        av   = row.get("pct_cosechado")
        rrro = row.get("var_rinde_pct")
        fib  = row.get("rinde_desmote_pct")
        av_s   = _avance_cell_style(av)
        rrro_s = _rrro_cell_style(rrro)
        fib_s  = _fibra_cell_style(fib)
        rrro_str = "—" if (rrro is None or (isinstance(rrro, float) and pd.isna(rrro))) else f"{rrro:+.1f}%"
        tbody += f"""
<tr style="{row_bg}">
  <td style="{td};{fw}">{row.get('campo','')}</td>
  <td style="{td};text-align:right;color:#333">{_f(row.get('sup_sembrada'), ',.0f')}</td>
  <td style="{td};text-align:center;{av_s}">{_f(av, '.1f', '%')}</td>
  <td style="{td};text-align:right;color:#333">{_f(row.get('sup_cosechada'), ',.0f')}</td>
  <td style="{td};text-align:right;color:#333">{_f(row.get('rinde_plan_kgha'), ',.0f')}</td>
  <td style="{td};text-align:right;color:#333">{_f(row.get('rinde_obt_kgha'), ',.0f')}</td>
  <td style="{td};text-align:center;{rrro_s}">{rrro_str}</td>
  <td style="{td};text-align:center;{fib_s}">{_f(fib, '.1f', '%')}</td>
  <td style="{td};text-align:right;color:#333">{_f(row.get('rinde_neto_kgha'), ',.0f')}</td>
</tr>"""
    return f"""
<div style="overflow-x:auto;border-radius:12px;box-shadow:0 2px 16px rgba(0,0,0,0.08);margin:10px 0 4px 0">
<table style="width:100%;border-collapse:collapse;font-size:0.84rem;font-family:system-ui,sans-serif">
  <thead>
    <tr style="background:#1a5c2a;color:white">
      <th style="padding:11px 14px;text-align:left;font-weight:700;letter-spacing:.02em">Campo</th>
      <th style="padding:11px 14px;text-align:right;font-weight:700;white-space:nowrap">Sup Semb (ha)</th>
      <th style="padding:11px 14px;text-align:center;font-weight:700;white-space:nowrap">Avance %</th>
      <th style="padding:11px 14px;text-align:right;font-weight:700;white-space:nowrap">Sup Cos (ha)</th>
      <th style="padding:11px 14px;text-align:right;font-weight:700;white-space:nowrap">RO (kg/ha)</th>
      <th style="padding:11px 14px;text-align:right;font-weight:700;white-space:nowrap">RR (kg/ha)</th>
      <th style="padding:11px 14px;text-align:center;font-weight:700;white-space:nowrap">RR/RO %</th>
      <th style="padding:11px 14px;text-align:center;font-weight:700;white-space:nowrap">R. Fibra %</th>
      <th style="padding:11px 14px;text-align:right;font-weight:700;white-space:nowrap">R. Neto (kg/ha)</th>
    </tr>
  </thead>
  <tbody>{tbody}</tbody>
</table>
</div>"""

# ── aggregations ──────────────────────────────────────────────────────────────

def resumen_cruzado(sisa_df, rem_df):
    sisa_agg = sisa_df.groupby("lugar").agg(
        sup_planificada   = ("superficieplanificada",       "sum"),
        sup_sembrada      = ("superficiesembrada",          "sum"),
        sup_cosechada     = ("superficiecosechada",         "sum"),
        tn_planificadas   = ("tnplanificados",              "sum"),
        tn_producidas     = ("tnproducidos",                "sum"),
    ).reset_index().rename(columns={"lugar": "campo"})
    sisa_agg["pct_cosechado"]    = (sisa_agg["sup_cosechada"] / sisa_agg["sup_sembrada"] * 100).where(sisa_agg["sup_sembrada"] > 0)
    sisa_agg["rinde_obt_kgha"]  = (sisa_agg["tn_producidas"] * 1000 / sisa_agg["sup_sembrada"]).where(sisa_agg["sup_sembrada"] > 0)
    sisa_agg["rinde_plan_kgha"] = (sisa_agg["tn_planificadas"] * 1000 / sisa_agg["sup_planificada"]).where(sisa_agg["sup_planificada"] > 0)

    rem_agg = rem_df.groupby("establecimiento").agg(
        entregado_tn  = ("cantidad",               "sum"),
        tn_desmotadas = ("cantidadconsumo",        "sum"),
        fibra_kg      = ("cantidadproducidakilos", "sum"),
    ).reset_index().rename(columns={"establecimiento": "campo"})
    rem_agg["entregado_tn"]  = rem_agg["entregado_tn"]  / 1000
    rem_agg["tn_desmotadas"] = rem_agg["tn_desmotadas"] / 1000
    rem_agg["fibra_tn"]      = rem_agg["fibra_kg"]      / 1000

    g = sisa_agg.merge(rem_agg, on="campo", how="left")
    g["entregado_tn"]       = g["entregado_tn"].fillna(0)
    g["tn_desmotadas"]      = g["tn_desmotadas"].fillna(0)
    g["fibra_tn"]           = g["fibra_tn"].fillna(0)
    g["en_establecimiento"] = (g["tn_producidas"] - g["entregado_tn"]).clip(lower=0)
    g["avance_entrega_pct"] = (g["entregado_tn"] / g["tn_producidas"] * 100).where(g["tn_producidas"] > 0)
    g["cumpl_plan_pct"]     = (g["tn_producidas"] / g["tn_planificadas"] * 100).where(g["tn_planificadas"] > 0)
    g["rinde_fibra_kgha"]   = (g["fibra_tn"] * 1000 / g["sup_sembrada"]).where(g["sup_sembrada"] > 0)
    g["rinde_neto_kgha"]    = (g["tn_desmotadas"] * 1000 / g["sup_sembrada"]).where(g["sup_sembrada"] > 0)
    g["var_rinde_kgha"]     = g["rinde_obt_kgha"] - g["rinde_plan_kgha"]
    g["rinde_desmote_pct"]  = (g["fibra_tn"] / g["tn_desmotadas"] * 100).where(g["tn_desmotadas"] > 0)
    g["var_rinde_pct"]      = (g["var_rinde_kgha"] / g["rinde_plan_kgha"] * 100).where(
        g["rinde_plan_kgha"].notna() & (g["rinde_plan_kgha"] > 0)
    )
    return g.sort_values("campo")

def agg_campo_sisa(df):
    _agg = dict(
        sup_planificada = ("superficieplanificada", "sum"),
        sup_sembrada    = ("superficiesembrada",    "sum"),
        sup_cosechada   = ("superficiecosechada",   "sum"),
        tn_planificadas = ("tnplanificados",        "sum"),
        tn_producidas   = ("tnproducidos",          "sum"),
        tn_resto        = ("restoacosechar",        "sum"),
        lotes           = ("lote",                 "count"),
    )
    if "zona" in df.columns:
        _agg["zona"] = ("zona", "first")
    g = df.groupby(["empresasucursal", "lugar"]).agg(**_agg).reset_index()
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
        bruto_kg    = ("cantidad",               "sum"),
        consumo_kg  = ("cantidadconsumo",        "sum"),
        fibra_kg    = ("cantidadproducidakilos",  "sum"),
        fardos      = ("cantidadproducidafardos", "sum"),
        remitos     = ("cantidad",               "count"),
    ).reset_index()
    ha = sup.groupby(["empresa", "establecimiento"])["sup_ha"].sum().reset_index()
    g = g.merge(ha, on=["empresa", "establecimiento"], how="left")
    g["bruto_tn"]      = g["bruto_kg"] / 1000
    g["fibra_tn"]      = g["fibra_kg"] / 1000
    g["rinde_kgha"]    = (g["bruto_kg"] / g["sup_ha"]).where(g["sup_ha"] > 0)
    g["rinde_desmote"] = (g["fibra_kg"] / g["consumo_kg"] * 100).where(g["consumo_kg"] > 0)
    g["ppf_kg"]        = (g["bruto_kg"] / g["fardos"]).where(g["fardos"] > 0)
    return g.sort_values(["empresa", "establecimiento"])

def agg_lote(df, sup):
    g = df.groupby(["empresa", "establecimiento", "loteproduccion"]).agg(
        bruto_kg   = ("cantidad",               "sum"),
        consumo_kg = ("cantidadconsumo",        "sum"),
        fibra_kg   = ("cantidadproducidakilos",  "sum"),
        fardos     = ("cantidadproducidafardos", "sum"),
    ).reset_index()
    g = g.merge(sup, on=["empresa", "establecimiento", "loteproduccion"], how="left")
    g["bruto_tn"]      = g["bruto_kg"] / 1000
    g["fibra_tn"]      = g["fibra_kg"] / 1000
    g["rinde_kgha"]    = (g["bruto_kg"] / g["sup_ha"]).where(g["sup_ha"] > 0)
    g["rinde_desmote"] = (g["fibra_kg"] / g["consumo_kg"] * 100).where(g["consumo_kg"] > 0)
    return g.sort_values(["empresa", "establecimiento", "loteproduccion"])

def agg_desmotadora(df):
    g = df.groupby(["desmotadora", "empresa", "establecimiento"]).agg(
        entrega_kg = ("cantidad",              "sum"),
        consumo_kg = ("cantidadconsumo",       "sum"),
        fibra_kg   = ("cantidadproducidakilos","sum"),
        fardos     = ("cantidadproducidafardos","sum"),
    ).reset_index()
    g["rinde_desmote"] = (g["fibra_kg"] / g["consumo_kg"] * 100).where(g["consumo_kg"] > 0)
    g["ppf_kg"]        = (g["entrega_kg"] / g["fardos"]).where(g["fardos"] > 0)
    return g.sort_values(["desmotadora", "establecimiento"])

def agg_contratista(df):
    g = df.groupby("contratistacosecha").agg(
        bruto_kg   = ("cantidad",               "sum"),
        consumo_kg = ("cantidadconsumo",        "sum"),
        fibra_kg   = ("cantidadproducidakilos",  "sum"),
        fardos     = ("cantidadproducidafardos", "sum"),
    ).reset_index()
    g["rinde_desmote"] = (g["fibra_kg"] / g["consumo_kg"] * 100).where(g["consumo_kg"] > 0)
    return g.sort_values("bruto_kg", ascending=False)

def agg_semanal(df):
    g = df.copy()
    g["semana"] = g["fecha"].dt.to_period("W").dt.start_time
    return g.groupby("semana").agg(
        bruto_kg = ("cantidad",               "sum"),
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
            bruto_tn      = ("cantidad", "sum"),
            cant_remitos  = ("cantidad", "count"),
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
        .agg(bruto_tn=("cantidad", "sum"), remitos=("cantidad", "count"))
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

# ── CSS ───────────────────────────────────────────────────────────────────────

def inject_css():
    st.markdown("""
<style>
[data-testid="stAppViewContainer"] > .main {
    background: linear-gradient(160deg, #f4fdf7 0%, #edf9f2 60%, #f9fffc 100%);
}
[data-testid="stSidebar"] {
    background: #ffffff;
    border-right: 1px solid #e0f2e9;
}
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
.stTabs [data-baseweb="tab-list"] {
    justify-content: center;
    gap: 24px;
    margin-top: 8px;
    margin-bottom: 4px;
}
.stTabs [data-baseweb="tab"] {
    font-size: 1.15rem;
    font-weight: 700;
    padding: 14px 36px;
    border-radius: 10px 10px 0 0;
}
.stTabs [aria-selected="true"] {
    background-color: #e8f5e9;
    color: #1a5c2a;
}
footer { visibility: hidden; }
#MainMenu { visibility: hidden; }
</style>
""", unsafe_allow_html=True)

# ── data loading + sidebar ────────────────────────────────────────────────────

def load_data():
    raw_rem = raw_sisa = None
    rem_error = sisa_error = None
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
    return raw_rem, raw_sisa, rem_error, sisa_error


def sidebar_filters(raw_rem, raw_sisa):
    with st.sidebar:
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
            sin_fecha = rem["fecha"].isna().sum() if not rem.empty else 0
            aviso = f" · {sin_fecha} sin fecha" if sin_fecha > 0 else ""
            st.caption(f"Período: {d_desde.strftime('%d/%m')} → {d_hasta.strftime('%d/%m')}{aviso}")

    return sisa, rem
