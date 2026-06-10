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
print("Token OK:", token[:8])

resp2 = requests.get(
    os.environ["FINNEGANS_SISA_URL"],
    params={"ACCESS_TOKEN": token, "PARAM_Campana": "25-26_CampAgr", "PARAM_IndicadorSuperficie": 1},
    timeout=180,
)
print("Status:", resp2.status_code)

df = pd.DataFrame(resp2.json())
df.columns = df.columns.str.lower()
df = df[df["actividad"].str.contains("algod", case=False, na=False)].copy()
for col in df.select_dtypes("object").columns:
    df[col] = df[col].str.strip() if df[col].dtype == "object" else df[col]
df["lugar"] = df["lugar"].str.strip()

print(f"\nTotal registros algodón: {len(df)}")
print(f"Columnas disponibles: {list(df.columns)}\n")

# Buscar El Manganga
manganga = df[df["lugar"].str.contains("manganga", case=False, na=False)]
print(f"=== El Manganga ({len(manganga)} lotes) ===")
if not manganga.empty:
    cols_show = [c for c in ["lugar", "lote", "actividad", "superficiesembrada",
                              "superficiecosechada", "tnproducidos", "tnplanificados",
                              "cantidaddeproductoscosechado", "cantidadproducidasecundaria"]
                 if c in manganga.columns]
    print(manganga[cols_show].to_string(index=False))
    if "cantidaddeproductoscosechado" in manganga.columns:
        print(f"\n→ cantidaddeproductoscosechado total: {manganga['cantidaddeproductoscosechado'].sum()}")
    if "cantidadproducidasecundaria" in manganga.columns:
        print(f"→ cantidadproducidasecundaria total:  {manganga['cantidadproducidasecundaria'].sum()}")
else:
    print("No se encontraron registros para El Manganga")
    print("\nLugares disponibles:")
    print(df["lugar"].unique())
