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
if "partida" in df.columns:
    df["campania_norm"] = df["partida"].str.extract(r"(\d{2}-\d{2})$")

# Todas las columnas del dataset
print("=== Todas las columnas disponibles ===")
for c in df.columns:
    print(f"  {c}")
print()

# Filtrar PC 2 campania 25-26
pc2 = df[(df["establecimiento"] == "PC 2") & (df["campania_norm"] == "25-26")]

# Buscar columnas que parezcan fechas
date_cols = [c for c in df.columns if any(x in c for x in ["fecha", "date", "dia", "fec"])]
print(f"=== Columnas con 'fecha' en el nombre ===")
for c in date_cols:
    print(f"  {c}")
print()

print(f"=== Valores de columnas de fecha para PC 2 ({len(pc2)} remitos) ===")
for c in date_cols:
    if c in pc2.columns:
        print(f"\n  {c}:")
        print(pc2[c].to_string(index=False))
