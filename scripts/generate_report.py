import pandas as pd
import numpy as np
import os
from datetime import datetime

EMPRESA_FILTRO   = None          # None = todas las empresas
CAMPANIA_FILTRO  = "25-26"

# ── helpers ─────────────────────────────────────────────────────────────────

def fmt_tn(v):
    return f"{v/1000:,.1f}" if pd.notna(v) and v else "—"

def fmt_n(v, dec=0):
    if pd.isna(v) or v == 0: return "—"
    return f"{v:,.{dec}f}"

def fmt_pct(v):
    return f"{v:.1f}%" if pd.notna(v) and v else "—"

def fmt_kgha(v):
    return f"{v:,.0f}" if pd.notna(v) and v else "—"

def semaforo_rinde(v, bajo=24, alto=28):
    if pd.isna(v): return ""
    if v < bajo:   return "rojo"
    if v < alto:   return "amarillo"
    return "verde"

# ── carga y limpieza ─────────────────────────────────────────────────────────

def load_data(excel_path=None):
    if excel_path and os.path.exists(excel_path):
        df = pd.read_excel(excel_path, sheet_name="MtzDatosFinnegans")
        df.columns = df.columns.str.strip().str.lower().str.replace(" ", "_")
        print(f"Fuente: Excel ({len(df)} filas)")
    else:
        df = pd.read_parquet("data/raw/remitos_algodon.parquet")
        print(f"Fuente: API parquet ({len(df)} filas)")
    return df

def clean(df):
    # normalizar columnas numericas con NULL literal
    for col in ["pesoneto", "cantidadproducidakilos", "cantidadproducidafardos",
                "rindefibra", "supsembrada", "cantidadproducidatotal"]:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col].replace("NULL", None), errors="coerce")

    # extraer desmotadora del depositodestino
    if "depositodestino" in df.columns:
        df["desmotadora"] = (
            df["depositodestino"]
            .str.replace(r"^Desmotadora\s*-\s*", "", regex=True)
            .str.split(" - ").str[0]
            .str.strip()
        )
    else:
        df["desmotadora"] = "—"

    # normalizar campania
    for col in ["campaniaagricola", "campania"]:
        if col in df.columns:
            df["_campania"] = df[col].fillna("").str.strip()
            break

    return df

def filtrar(df):
    mask = pd.Series([True] * len(df), index=df.index)
    if EMPRESA_FILTRO:
        mask &= df["empresa"] == EMPRESA_FILTRO
    # campaña: desde campaniaagricola o desde partida
    if "_campania" in df.columns and df["_campania"].notna().any() and df["_campania"].ne("").any():
        mask &= df["_campania"].str.contains(CAMPANIA_FILTRO, na=False)
    elif "partida" in df.columns:
        mask &= df["partida"].str.endswith(CAMPANIA_FILTRO, na=False)
    resultado = df[mask].copy()
    label = EMPRESA_FILTRO or "todas las empresas"
    print(f"Filtro '{label}' + campaña '{CAMPANIA_FILTRO}': {len(resultado)} remitos")
    return resultado

# ── superficie por lote (deduplicada) ───────────────────────────────────────

def sup_por_lote(df):
    return (
        df.groupby(["establecimiento", "loteproduccion"])["supsembrada"]
        .first()
        .reset_index()
        .rename(columns={"supsembrada": "superficie_ha"})
    )

# ── vistas ───────────────────────────────────────────────────────────────────

def vista_por_campo(df, sup):
    agg = df.groupby(["empresa", "establecimiento"]).agg(
        bruto_kg   = ("pesoneto",               "sum"),
        fibra_kg   = ("cantidadproducidakilos",  "sum"),
        fardos     = ("cantidadproducidafardos",  "sum"),
    ).reset_index()
    ha = sup.groupby(["establecimiento"])["superficie_ha"].sum().reset_index()
    out = agg.merge(ha, on="establecimiento", how="left")
    out["rinde_bruto_kgha"]  = out["bruto_kg"]  / out["superficie_ha"]
    out["rinde_fibra_kgha"]  = out["fibra_kg"]  / out["superficie_ha"]
    out["rinde_desmote_pct"] = (out["fibra_kg"] / out["bruto_kg"] * 100).where(out["bruto_kg"] > 0)
    out["peso_prom_fardo_kg"]= (out["bruto_kg"] / out["fardos"]).where(out["fardos"] > 0)
    return out.sort_values(["empresa", "establecimiento"])

def vista_por_lote(df, sup):
    agg = df.groupby(["empresa", "establecimiento", "loteproduccion"]).agg(
        bruto_kg   = ("pesoneto",               "sum"),
        fibra_kg   = ("cantidadproducidakilos",  "sum"),
        fardos     = ("cantidadproducidafardos",  "sum"),
    ).reset_index()
    out = agg.merge(sup, on=["establecimiento", "loteproduccion"], how="left")
    out["rinde_bruto_kgha"]  = out["bruto_kg"]  / out["superficie_ha"]
    out["rinde_fibra_kgha"]  = out["fibra_kg"]  / out["superficie_ha"]
    out["rinde_desmote_pct"] = (out["fibra_kg"] / out["bruto_kg"] * 100).where(out["bruto_kg"] > 0)
    return out.sort_values(["empresa", "establecimiento", "loteproduccion"])

def vista_logistica(df):
    agg = df.groupby(["desmotadora", "establecimiento"]).agg(
        entrega_kg = ("pesoneto",               "sum"),
        fibra_kg   = ("cantidadproducidakilos",  "sum"),
        fardos     = ("cantidadproducidafardos",  "sum"),
    ).reset_index()
    agg["rinde_desmote_pct"] = (agg["fibra_kg"] / agg["entrega_kg"] * 100).where(agg["entrega_kg"] > 0)
    agg["peso_prom_fardo_kg"]= (agg["entrega_kg"] / agg["fardos"]).where(agg["fardos"] > 0)
    return agg.sort_values(["desmotadora", "establecimiento"])

def vista_contratista(df):
    agg = df.groupby("contratistacosecha").agg(
        bruto_kg = ("pesoneto",               "sum"),
        fibra_kg = ("cantidadproducidakilos",  "sum"),
        fardos   = ("cantidadproducidafardos",  "sum"),
    ).reset_index()
    agg["rinde_desmote_pct"] = (agg["fibra_kg"] / agg["bruto_kg"] * 100).where(agg["bruto_kg"] > 0)
    return agg.sort_values("bruto_kg", ascending=False)

def resumen(df, sup):
    return {
        "remitos":       len(df),
        "bruto_tn":      df["pesoneto"].sum() / 1000,
        "fibra_tn":      df["cantidadproducidakilos"].sum() / 1000,
        "fardos":        int(df["cantidadproducidafardos"].sum()),
        "rinde_pct":     df["cantidadproducidakilos"].sum() / df["pesoneto"].sum() * 100 if df["pesoneto"].sum() > 0 else 0,
        "superficie_ha": sup["superficie_ha"].sum(),
        "campos":        df["establecimiento"].nunique(),
        "lotes":         df["loteproduccion"].nunique(),
    }

# ── HTML ─────────────────────────────────────────────────────────────────────

CSS = """
body{font-family:Arial,sans-serif;font-size:13px;color:#222;margin:0;padding:24px;background:#f4f4f4}
h1{font-size:21px;margin-bottom:2px}
h2{font-size:14px;margin-top:32px;margin-bottom:8px;border-bottom:2px solid #ccc;padding-bottom:4px;text-transform:uppercase;letter-spacing:.5px;color:#444}
.meta{color:#888;font-size:11px;margin-bottom:20px}
.cards{display:flex;flex-wrap:wrap;gap:12px;margin-bottom:28px}
.card{background:#fff;border-radius:6px;padding:12px 18px;min-width:130px;box-shadow:0 1px 3px rgba(0,0,0,.1)}
.card .val{font-size:26px;font-weight:bold;color:#2c3e50}
.card .lbl{font-size:11px;color:#999;margin-top:2px}
table{border-collapse:collapse;width:100%;background:#fff;border-radius:6px;overflow:hidden;box-shadow:0 1px 3px rgba(0,0,0,.1);margin-bottom:24px}
thead tr{background:#2c3e50;color:#fff}
th{padding:8px 10px;text-align:left;font-size:11px;font-weight:600;white-space:nowrap}
td{padding:6px 10px;border-bottom:1px solid #f0f0f0;font-size:12px}
tr:last-child td{border-bottom:none}
tr:hover td{background:#fafafa}
.r{text-align:right}
.sub{background:#ecf0f1!important;font-weight:600}
.verde{background:#d5f5e3;color:#1a7a40;font-weight:700}
.amarillo{background:#fef9e7;color:#b7950b;font-weight:700}
.rojo{background:#fadbd8;color:#c0392b;font-weight:700}
.tot td{background:#eaf0fb;font-weight:700}
"""

def tr_campo(r):
    rd = r["rinde_desmote_pct"]
    cl = semaforo_rinde(rd)
    return f"""<tr>
      <td>{r['empresa']}</td>
      <td>{r['establecimiento']}</td>
      <td class="r">{fmt_n(r['superficie_ha'],1)}</td>
      <td class="r">{fmt_tn(r['bruto_kg'])}</td>
      <td class="r">{fmt_kgha(r['rinde_bruto_kgha'])}</td>
      <td class="r">{fmt_tn(r['fibra_kg'])}</td>
      <td class="r">{fmt_kgha(r['rinde_fibra_kgha'])}</td>
      <td class="r {cl}">{fmt_pct(rd)}</td>
      <td class="r">{fmt_n(r['fardos'])}</td>
      <td class="r">{fmt_kgha(r['peso_prom_fardo_kg'])}</td>
    </tr>"""

def tr_lote(r):
    rd = r["rinde_desmote_pct"]
    cl = semaforo_rinde(rd)
    return f"""<tr>
      <td>{r['empresa']}</td>
      <td>{r['establecimiento']}</td>
      <td>{r['loteproduccion']}</td>
      <td class="r">{fmt_n(r['superficie_ha'],1)}</td>
      <td class="r">{fmt_tn(r['bruto_kg'])}</td>
      <td class="r">{fmt_kgha(r['rinde_bruto_kgha'])}</td>
      <td class="r">{fmt_tn(r['fibra_kg'])}</td>
      <td class="r">{fmt_kgha(r['rinde_fibra_kgha'])}</td>
      <td class="r {cl}">{fmt_pct(rd)}</td>
      <td class="r">{fmt_n(r['fardos'])}</td>
    </tr>"""

def tr_logistica(r):
    rd = r["rinde_desmote_pct"]
    cl = semaforo_rinde(rd)
    return f"""<tr>
      <td>{r['desmotadora']}</td>
      <td>{r['establecimiento']}</td>
      <td class="r">{fmt_tn(r['entrega_kg'])}</td>
      <td class="r">{fmt_tn(r['fibra_kg'])}</td>
      <td class="r {cl}">{fmt_pct(rd)}</td>
      <td class="r">{fmt_n(r['fardos'])}</td>
      <td class="r">{fmt_kgha(r['peso_prom_fardo_kg'])}</td>
    </tr>"""

def tr_contratista(r):
    rd = r["rinde_desmote_pct"]
    cl = semaforo_rinde(rd)
    return f"""<tr>
      <td>{r['contratistacosecha']}</td>
      <td class="r">{fmt_tn(r['bruto_kg'])}</td>
      <td class="r">{fmt_tn(r['fibra_kg'])}</td>
      <td class="r {cl}">{fmt_pct(rd)}</td>
      <td class="r">{fmt_n(r['fardos'])}</td>
    </tr>"""

def totales_campo(vc):
    tot = vc[["bruto_kg","fibra_kg","fardos","superficie_ha"]].sum()
    rd = tot["fibra_kg"] / tot["bruto_kg"] * 100 if tot["bruto_kg"] > 0 else np.nan
    ppf = tot["bruto_kg"] / tot["fardos"] if tot["fardos"] > 0 else np.nan
    return f"""<tr class="tot">
      <td><b>TOTAL</b></td>
      <td class="r">{fmt_n(tot['superficie_ha'],1)}</td>
      <td class="r">{fmt_tn(tot['bruto_kg'])}</td>
      <td class="r">—</td>
      <td class="r">{fmt_tn(tot['fibra_kg'])}</td>
      <td class="r">—</td>
      <td class="r">{fmt_pct(rd)}</td>
      <td class="r">{fmt_n(tot['fardos'])}</td>
      <td class="r">{fmt_kgha(ppf)}</td>
    </tr>"""

def totales_contratista(vc):
    tot = vc[["bruto_kg","fibra_kg","fardos"]].sum()
    rd = tot["fibra_kg"] / tot["bruto_kg"] * 100 if tot["bruto_kg"] > 0 else np.nan
    return f"""<tr class="tot">
      <td><b>TOTAL</b></td>
      <td class="r">{fmt_tn(tot['bruto_kg'])}</td>
      <td class="r">{fmt_tn(tot['fibra_kg'])}</td>
      <td class="r">{fmt_pct(rd)}</td>
      <td class="r">{fmt_n(tot['fardos'])}</td>
    </tr>"""

def build_html(res, vc, vl, vlog, vcont, fecha):
    rows_campo      = "\n".join(tr_campo(r)      for _, r in vc.iterrows())
    rows_lote       = "\n".join(tr_lote(r)       for _, r in vl.iterrows())
    rows_logistica  = "\n".join(tr_logistica(r)  for _, r in vlog.iterrows())
    rows_contratista= "\n".join(tr_contratista(r) for _, r in vcont.iterrows())

    return f"""<!DOCTYPE html>
<html lang="es">
<head>
<meta charset="UTF-8">
<title>Cosecha Algodón — ECO NEA {CAMPANIA_FILTRO}</title>
<style>{CSS}</style>
</head>
<body>

<h1>Control de Cosecha de Algodón — ECO NEA</h1>
<p class="meta">Campaña {CAMPANIA_FILTRO} &nbsp;·&nbsp; Generado el {fecha} &nbsp;·&nbsp; Fuente: Finnegans</p>

<div class="cards">
  <div class="card"><div class="val">{fmt_tn(res['bruto_tn']*1000)} Tn</div><div class="lbl">Algodón Bruto Entregado</div></div>
  <div class="card"><div class="val">{fmt_tn(res['fibra_tn']*1000)} Tn</div><div class="lbl">Fibra Producida</div></div>
  <div class="card"><div class="val">{fmt_pct(res['rinde_pct'])}</div><div class="lbl">Rinde al Desmote</div></div>
  <div class="card"><div class="val">{res['fardos']:,}</div><div class="lbl">Fardos</div></div>
  <div class="card"><div class="val">{fmt_n(res['superficie_ha'],0)} ha</div><div class="lbl">Superficie</div></div>
  <div class="card"><div class="val">{res['campos']}</div><div class="lbl">Campos</div></div>
  <div class="card"><div class="val">{res['lotes']}</div><div class="lbl">Lotes</div></div>
  <div class="card"><div class="val">{res['remitos']}</div><div class="lbl">Remitos</div></div>
</div>

<p style="font-size:11px;color:#888;margin-bottom:20px">
  Rinde al desmote: <span class="verde" style="padding:2px 6px;border-radius:3px">&ge; 28%</span>
  &nbsp;<span class="amarillo" style="padding:2px 6px;border-radius:3px">24–28%</span>
  &nbsp;<span class="rojo" style="padding:2px 6px;border-radius:3px">&lt; 24%</span>
</p>

<h2>Producción por Campo</h2>
<table>
  <thead><tr>
    <th>Empresa</th>
    <th>Campo</th>
    <th>Sup (ha)</th>
    <th>Algodón Bruto (Tn)</th>
    <th>Rinde Bruto (kg/ha)</th>
    <th>Fibra (Tn)</th>
    <th>Rinde Fibra (kg/ha)</th>
    <th>Rinde Desmote</th>
    <th>Fardos</th>
    <th>Peso Prom Fardo (kg)</th>
  </tr></thead>
  <tbody>
    {rows_campo}
    {totales_campo(vc)}
  </tbody>
</table>

<h2>Producción por Lote</h2>
<table>
  <thead><tr>
    <th>Empresa</th>
    <th>Campo</th>
    <th>Lote</th>
    <th>Sup (ha)</th>
    <th>Algodón Bruto (Tn)</th>
    <th>Rinde Bruto (kg/ha)</th>
    <th>Fibra (Tn)</th>
    <th>Rinde Fibra (kg/ha)</th>
    <th>Rinde Desmote</th>
    <th>Fardos</th>
  </tr></thead>
  <tbody>{rows_lote}</tbody>
</table>

<h2>Logística por Desmotadora</h2>
<table>
  <thead><tr>
    <th>Desmotadora</th>
    <th>Campo</th>
    <th>Algodón Entregado (Tn)</th>
    <th>Fibra (Tn)</th>
    <th>Rinde Desmote</th>
    <th>Fardos</th>
    <th>Peso Prom Fardo (kg)</th>
  </tr></thead>
  <tbody>{rows_logistica}</tbody>
</table>

<h2>Rinde por Contratista</h2>
<table>
  <thead><tr>
    <th>Contratista</th>
    <th>Algodón Bruto (Tn)</th>
    <th>Fibra (Tn)</th>
    <th>Rinde Desmote</th>
    <th>Fardos</th>
  </tr></thead>
  <tbody>
    {rows_contratista}
    {totales_contratista(vcont)}
  </tbody>
</table>

</body>
</html>"""

# ── main ─────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    # Usa parquet (API) como fuente principal — tiene los datos más actualizados
    # Pasar EXCEL como argumento si se quiere usar el Excel como fuente
    EXCEL = None

    df_raw = load_data(EXCEL)
    df     = filtrar(clean(df_raw))

    sup  = sup_por_lote(df)
    vc   = vista_por_campo(df, sup)
    vl   = vista_por_lote(df, sup)
    vlog = vista_logistica(df)
    vcont= vista_contratista(df)
    res  = resumen(df, sup)

    fecha = datetime.now().strftime("%d/%m/%Y %H:%M")
    html  = build_html(res, vc, vl, vlog, vcont, fecha)

    os.makedirs("reports", exist_ok=True)
    out = "reports/cosecha_algodon_nea_25_26.html"
    with open(out, "w", encoding="utf-8") as f:
        f.write(html)
    print(f"Reporte generado: {out}")
