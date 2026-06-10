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

print("=== Establecimientos en remitos (campania 25-26) ===")
rem_2526 = df[df["campania_norm"] == "25-26"]
resumen = rem_2526.groupby("establecimiento").agg(
    remitos=("pesoneto","count"),
    bruto_tn=("pesoneto","sum"),
).reset_index()
resumen["bruto_tn"] = resumen["bruto_tn"] / 1000
print(resumen.sort_values("establecimiento").to_string(index=False))
