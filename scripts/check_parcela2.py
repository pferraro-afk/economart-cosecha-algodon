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
df["empresa"] = df["empresa"].str.strip() if "empresa" in df.columns else ""
df["pesoneto"] = pd.to_numeric(df["pesoneto"].replace("NULL", None), errors="coerce")
df["fecha"] = pd.to_datetime(df["fecha"], errors="coerce")
if "partida" in df.columns:
    df["campania_norm"] = df["partida"].str.extract(r"(\d{2}-\d{2})$")

pc2 = df[df["establecimiento"] == "PC 2"].copy()
print(f"Total remitos PC 2 (todas campanias): {len(pc2)}")
print(f"Campanias: {pc2['campania_norm'].unique()}")
print(f"Empresas:  {pc2['empresa'].unique()}")
print()

pc2_2526 = pc2[pc2["campania_norm"] == "25-26"]
print(f"Remitos 25-26: {len(pc2_2526)}")
print(f"Bruto total 25-26: {pc2_2526['pesoneto'].sum():,.0f} kg = {pc2_2526['pesoneto'].sum()/1000:,.2f} Tn")
print()

print("=== Detalle remito a remito ===")
cols = [c for c in ["empresa","establecimiento","partida","campania_norm","fecha","pesoneto"] if c in pc2_2526.columns]
print(pc2_2526[cols].sort_values("fecha").to_string(index=False))
print()

print("=== Desglose por empresa ===")
print(pc2_2526.groupby("empresa")["pesoneto"].agg(["count","sum"]).rename(columns={"count":"remitos","sum":"kg"}))
print()

# Verificar que empresas hay en SISA para PC 2
resp3 = requests.get(
    os.environ["FINNEGANS_OAUTH_URL"],
    params={"grant_type": "client_credentials", "client_id": os.environ["FINNEGANS_CLIENT_ID"], "client_secret": os.environ["FINNEGANS_CLIENT_SECRET"]},
    timeout=30,
)
token2 = resp3.text.strip().strip('"')
resp4 = requests.get(
    os.environ["FINNEGANS_SISA_URL"],
    params={"ACCESS_TOKEN": token2, "PARAM_Campana": "25-26_CampAgr", "PARAM_IndicadorSuperficie": 1},
    timeout=180,
)
sisa = pd.DataFrame(resp4.json())
sisa.columns = sisa.columns.str.lower()
sisa["lugar"] = sisa["lugar"].str.strip()
sisa["empresasucursal"] = sisa["empresasucursal"].str.strip()
sisa = sisa[sisa["actividad"].str.contains("algod", case=False, na=False)]
pc2_sisa = sisa[sisa["lugar"] == "PC 2"]
print(f"=== PC 2 en SISA ({len(pc2_sisa)} lotes) ===")
print(f"Empresasucursal: {pc2_sisa['empresasucursal'].unique()}")
print()
print("Empresas en remitos PC 2:", pc2_2526["empresa"].unique())
print("Empresasucursal en SISA PC 2:", pc2_sisa["empresasucursal"].unique())
print()
print("-> El filtro sidebar usa la UNION de ambas para mostrar opciones.")
print("-> Remitos se filtran por empresa, SISA por empresasucursal.")
print("-> Si hay empresas en remitos que NO estan en SISA, esos remitos quedan fuera cuando el usuario filtra.")
