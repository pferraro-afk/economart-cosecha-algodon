import requests
import pandas as pd
from dotenv import load_dotenv
import os

load_dotenv(".env")

resp = requests.get(
    os.environ["FINNEGANS_OAUTH_URL"],
    params={"grant_type": "client_credentials", "client_id": os.environ["FINNEGANS_CLIENT_ID"], "client_secret": os.environ["FINNEGANS_CLIENT_SECRET"]},
    timeout=30,
)
token = resp.text.strip().strip('"')

resp2 = requests.get(
    os.environ["FINNEGANS_REPORT_URL"],
    params={"ACCESS_TOKEN": token},
    timeout=180,
)
df = pd.DataFrame(resp2.json())
df.columns = df.columns.str.lower()
df["establecimiento"] = df["establecimiento"].str.strip()
df["pesoneto"] = pd.to_numeric(df["pesoneto"].replace("NULL", None), errors="coerce")
if "partida" in df.columns:
    df["campania_norm"] = df["partida"].str.extract(r"(\d{2}-\d{2})$")

# ANTES: sin dayfirst
df["fecha_mal"] = pd.to_datetime(df["fecha"], errors="coerce")
# DESPUES: con dayfirst
df["fecha_ok"]  = pd.to_datetime(df["fecha"], dayfirst=True, errors="coerce")

rem = df[df["campania_norm"] == "25-26"].copy()

print("=== Verificacion de fechas por establecimiento (campania 25-26) ===\n")
print(f"{'Campo':<18} {'Remitos':>8} {'NaT antes':>10} {'NaT ahora':>10} {'Bruto Tn':>10}")
print("-" * 62)
for est, g in rem.groupby("establecimiento"):
    nat_antes = g["fecha_mal"].isna().sum()
    nat_ahora = g["fecha_ok"].isna().sum()
    bruto_tn  = g["pesoneto"].sum() / 1000
    flag = "  <- CORREGIDO" if nat_antes > nat_ahora else ""
    print(f"{est:<18} {len(g):>8} {nat_antes:>10} {nat_ahora:>10} {bruto_tn:>10.2f}{flag}")

print()
print("=== Rango de fechas por campo (con fix) ===\n")
print(f"{'Campo':<18} {'Fecha min':>12} {'Fecha max':>12} {'Sin fecha':>10}")
print("-" * 58)
for est, g in rem.groupby("establecimiento"):
    fmin = g["fecha_ok"].min()
    fmax = g["fecha_ok"].max()
    sin  = g["fecha_ok"].isna().sum()
    fmin_s = fmin.strftime("%d/%m/%Y") if pd.notna(fmin) else "—"
    fmax_s = fmax.strftime("%d/%m/%Y") if pd.notna(fmax) else "—"
    print(f"{est:<18} {fmin_s:>12} {fmax_s:>12} {sin:>10}")
