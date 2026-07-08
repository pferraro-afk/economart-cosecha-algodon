import sys
import io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

import requests
import pandas as pd
import numpy as np
from dotenv import load_dotenv
import os

load_dotenv(".env")

CAMPANIA = "25-26"
OK   = "[OK]  "
WARN = "[WARN]"
ERR  = "[ERR] "

issues = []

def log(nivel, seccion, msg):
    tag = {"ok": OK, "warn": WARN, "err": ERR}[nivel]
    print(f"  {tag} {msg}")
    if nivel != "ok":
        issues.append((seccion, nivel, msg))

def sep(titulo):
    print(f"\n== {titulo} {'='*(60-len(titulo))}")

# ─────────────────────────────────────────────────────────────────────────────
# 1. FETCH
# ─────────────────────────────────────────────────────────────────────────────
sep("FETCH")

def get_token():
    r = requests.get(os.environ["FINNEGANS_OAUTH_URL"],
        params={"grant_type":"client_credentials",
                "client_id":os.environ["FINNEGANS_CLIENT_ID"],
                "client_secret":os.environ["FINNEGANS_CLIENT_SECRET"]},
        timeout=30)
    r.raise_for_status()
    return r.text.strip().strip('"')

try:
    token = get_token()
    r = requests.get(os.environ["FINNEGANS_REPORT_URL"],
        params={"ACCESS_TOKEN": token}, timeout=180)
    r.raise_for_status()
    raw_rem = pd.DataFrame(r.json())
    raw_rem.columns = raw_rem.columns.str.lower()
    print(f"  {OK} Remitos: {len(raw_rem)} registros totales")
except Exception as e:
    print(f"  {ERR} No se pudo obtener remitos: {e}")
    raw_rem = None

try:
    token2 = get_token()
    r2 = requests.get(os.environ["FINNEGANS_SISA_URL"],
        params={"ACCESS_TOKEN": token2, "PARAM_Campana": "25-26_CampAgr", "PARAM_IndicadorSuperficie": 1},
        timeout=180)
    r2.raise_for_status()
    raw_sisa = pd.DataFrame(r2.json())
    raw_sisa.columns = raw_sisa.columns.str.lower()
    raw_sisa = raw_sisa[raw_sisa["actividad"].str.contains("algod", case=False, na=False)].copy()
    print(f"  {OK} SISA: {len(raw_sisa)} lotes de algodon")
except Exception as e:
    print(f"  {ERR} No se pudo obtener SISA: {e}")
    raw_sisa = None

if raw_rem is None or raw_sisa is None:
    print("No se puede continuar sin datos.")
    sys.exit(1)

# ─────────────────────────────────────────────────────────────────────────────
# 2. REMITOS
# ─────────────────────────────────────────────────────────────────────────────
sep("REMITOS - limpieza y validacion")

rem = raw_rem.copy()
for col in ["pesoneto","cantidadproducidakilos","cantidadproducidafardos","cantidadstock2","supsembrada"]:
    if col in rem.columns:
        rem[col] = pd.to_numeric(rem[col].replace("NULL", None), errors="coerce")
rem["establecimiento"] = rem["establecimiento"].str.strip()
rem["empresa"]         = rem["empresa"].str.strip()
rem["fecha"]           = pd.to_datetime(rem["fecha"], dayfirst=True, errors="coerce")
if "partida" in rem.columns:
    rem["campania_norm"] = rem["partida"].str.extract(r"(\d{2}-\d{2})$")

rem = rem[rem["campania_norm"] == CAMPANIA].copy()
print(f"  {OK} Remitos campania {CAMPANIA}: {len(rem)}")

sin_fecha = rem["fecha"].isna().sum()
if sin_fecha:
    log("warn", "remitos", f"{sin_fecha} remitos sin fecha en Finnegans")
else:
    log("ok",   "remitos", "Todos los remitos tienen fecha")

nulls_peso = rem["pesoneto"].isna().sum()
ceros_peso = (rem["pesoneto"] == 0).sum()
if nulls_peso:
    log("err",  "remitos", f"{nulls_peso} remitos con pesoneto NULL")
elif ceros_peso:
    log("warn", "remitos", f"{ceros_peso} remitos con pesoneto = 0")
else:
    log("ok",   "remitos", "pesoneto sin nulos ni ceros")

for col, label in [("cantidadproducidakilos","fibra kg"),("cantidadproducidafardos","fardos")]:
    n = rem[col].isna().sum() if col in rem.columns else 0
    if n:
        log("warn", "remitos", f"{n} remitos con {label} = NULL")
    else:
        log("ok",   "remitos", f"{label}: sin nulos")

# rinde desmote por campo (rango esperado 15-45%)
vc = rem.groupby("establecimiento").agg(
    bruto=("pesoneto","sum"), fibra=("cantidadproducidakilos","sum")
).reset_index()
vc["rinde"] = vc["fibra"] / vc["bruto"] * 100
for _, row in vc.iterrows():
    if pd.isna(row["rinde"]):
        log("warn", "remitos", f"{row['establecimiento']}: rinde desmote incalculable")
    elif row["rinde"] < 15 or row["rinde"] > 45:
        log("err",  "remitos", f"{row['establecimiento']}: rinde desmote fuera de rango ({row['rinde']:.1f}%)")
    else:
        log("ok",   "remitos", f"{row['establecimiento']}: rinde desmote {row['rinde']:.1f}%")

# fechas duplicadas (mismo campo + partida + fecha + pesoneto)
dup = rem.duplicated(subset=["establecimiento","partida","fecha","pesoneto"])
if dup.sum():
    log("warn", "remitos", f"{dup.sum()} posibles remitos duplicados (mismo campo/partida/fecha/kg)")
else:
    log("ok",   "remitos", "Sin remitos duplicados")

# ─────────────────────────────────────────────────────────────────────────────
# 3. SISA
# ─────────────────────────────────────────────────────────────────────────────
sep("SISA - limpieza y validacion")

sisa = raw_sisa.copy()
for col in ["superficieplanificada","superficiesembrada","superficiecosechada",
            "porcentajeavance","tnplanificados","tnproducidos","restoacosechar",
            "cantidadproducidasecundaria"]:
    if col in sisa.columns:
        sisa[col] = pd.to_numeric(sisa[col], errors="coerce")
sisa["lugar"]           = sisa["lugar"].str.strip()
sisa["empresasucursal"] = sisa["empresasucursal"].str.strip()

for col in ["superficiesembrada","tnplanificados","tnproducidos"]:
    n = sisa[col].isna().sum()
    if n:
        log("err",  "sisa", f"{n} registros con {col} = NULL")
    else:
        log("ok",   "sisa", f"{col}: sin nulos")

# superficie cosechada > sembrada
invalidos = sisa[sisa["superficiecosechada"] > sisa["superficiesembrada"] + 0.1]
if len(invalidos):
    for _, r in invalidos.iterrows():
        log("err", "sisa", f"{r['lugar']}/{r['lote']}: sup cosechada ({r['superficiecosechada']:.1f}) > sembrada ({r['superficiesembrada']:.1f})")
else:
    log("ok", "sisa", "Superficies cosechadas <= sembradas en todos los lotes")

# tn producidas > 150% planificadas
excesos = sisa[(sisa["tnplanificados"] > 0) & (sisa["tnproducidos"] / sisa["tnplanificados"] > 1.5)]
if len(excesos):
    for _, r in excesos.iterrows():
        pct = r["tnproducidos"] / r["tnplanificados"] * 100
        log("warn", "sisa", f"{r['lugar']}/{r['lote']}: tn producidas = {pct:.0f}% del plan")
else:
    log("ok", "sisa", "Tn producidas dentro de rango razonable vs planificadas")

# avance % coherente con superficies
sisa["avance_calc"] = (sisa["superficiecosechada"] / sisa["superficiesembrada"] * 100).where(sisa["superficiesembrada"] > 0)
delta = (sisa["porcentajeavance"] - sisa["avance_calc"]).abs()
incoherentes = sisa[delta > 5].dropna(subset=["avance_calc","porcentajeavance"])
if len(incoherentes):
    log("warn", "sisa", f"{len(incoherentes)} lotes con avance% de API diferente al calculado (>5pp)")
    for _, r in incoherentes.iterrows():
        log("warn", "sisa", f"  {r['lugar']}/{r['lote']}: API={r['porcentajeavance']:.1f}% calc={r['avance_calc']:.1f}%")
else:
    log("ok", "sisa", "Avance % coherente con superficies en todos los lotes")

# ─────────────────────────────────────────────────────────────────────────────
# 4. CRUCE SISA <-> REMITOS
# ─────────────────────────────────────────────────────────────────────────────
sep("CRUCE SISA <-> REMITOS")

campos_sisa = set(sisa["lugar"].dropna().unique())
campos_rem  = set(rem["establecimiento"].dropna().unique())
solo_sisa   = campos_sisa - campos_rem
solo_rem    = campos_rem  - campos_sisa
en_ambos    = campos_sisa & campos_rem

log("ok",   "cruce", f"Campos en ambos servicios: {sorted(en_ambos)}")
if solo_sisa:
    log("warn", "cruce", f"Campos en SISA sin remitos aun: {sorted(solo_sisa)}")
if solo_rem:
    log("warn", "cruce", f"Campos en remitos sin SISA: {sorted(solo_rem)}")

sisa_agg = sisa.groupby("lugar").agg(
    tn_prod    =("tnproducidos",              "sum"),
    tn_plan    =("tnplanificados",             "sum"),
    rollos_prod=("cantidadproducidasecundaria","sum"),
).reset_index()

rem_agg = rem.groupby("establecimiento").agg(
    entreg_tn=("pesoneto","sum"),
).reset_index().rename(columns={"establecimiento":"lugar"})
rem_agg["entreg_tn"] /= 1000

rollos_agg = rem[rem["producto"].str.contains("Rollos", case=False, na=False)]\
    .groupby("establecimiento").agg(rollos_carg=("cantidadstock2","sum"))\
    .reset_index().rename(columns={"establecimiento":"lugar"})

cruce = sisa_agg.merge(rem_agg, on="lugar", how="outer").merge(rollos_agg, on="lugar", how="left")
cruce["entreg_tn"]   = cruce["entreg_tn"].fillna(0)
cruce["rollos_carg"] = cruce["rollos_carg"].fillna(0)
cruce["en_est"]      = (cruce["tn_prod"] - cruce["entreg_tn"]).clip(lower=0)

print()
hdr = f"  {'Campo':<18} {'Tn Plan':>8} {'Tn Prod':>8} {'Entregado':>10} {'En Estab':>9} {'R.Prod':>7} {'R.Carg':>7}"
print(hdr)
print("  " + "-" * (len(hdr) - 2))

for _, r in cruce.sort_values("lugar").iterrows():
    estado = ""
    if pd.notna(r.get("entreg_tn")) and pd.notna(r.get("tn_prod")):
        if r["entreg_tn"] > r["tn_prod"] + 0.5:
            estado = " <- ERR: entregado > producido"
    if r["rollos_carg"] > r["rollos_prod"] + 0.5:
        estado += f" <- WARN: {r['rollos_carg']:.0f} cargados > {r['rollos_prod']:.0f} producidos"
    print(f"  {r['lugar']:<18} {r['tn_plan']:>8.1f} {r['tn_prod']:>8.1f} {r['entreg_tn']:>10.1f} {r['en_est']:>9.1f} {r['rollos_prod']:>7.0f} {r['rollos_carg']:>7.0f}{estado}")

# ─────────────────────────────────────────────────────────────────────────────
# 5. TOTALES
# ─────────────────────────────────────────────────────────────────────────────
sep("TOTALES GENERALES")
tot = cruce.sum(numeric_only=True)
print(f"  Tn planificadas (SISA):  {tot['tn_plan']:>10.2f} Tn")
print(f"  Tn producidas (SISA):    {tot['tn_prod']:>10.2f} Tn")
print(f"  Entregado a desm.:       {tot['entreg_tn']:>10.2f} Tn")
print(f"  En establecimiento:      {tot['en_est']:>10.2f} Tn")
print(f"  Rollos producidos:       {tot['rollos_prod']:>10.0f}")
print(f"  Rollos cargados:         {tot['rollos_carg']:>10.0f}")
print(f"  Bruto total remitos:     {rem['pesoneto'].sum()/1000:>10.2f} Tn")

sep("RESULTADO FINAL")
errores  = [i for i in issues if i[1] == "err"]
warnings = [i for i in issues if i[1] == "warn"]
if not issues:
    print(f"  {OK} Todo OK. Sin errores ni advertencias.")
else:
    if errores:
        print(f"  {ERR} {len(errores)} error(es) encontrado(s):")
        for s, n, m in errores:
            print(f"       [{s}] {m}")
    if warnings:
        print(f"  {WARN} {len(warnings)} advertencia(s):")
        for s, n, m in warnings:
            print(f"       [{s}] {m}")
print()
