from dotenv import load_dotenv; load_dotenv(".env")
import os, requests, pandas as pd

token = requests.get(os.environ["FINNEGANS_OAUTH_URL"], params={
    "grant_type":"client_credentials",
    "client_id": os.environ["FINNEGANS_CLIENT_ID"],
    "client_secret": os.environ["FINNEGANS_CLIENT_SECRET"]}, timeout=30).text.strip().strip('"')

resp = requests.get(os.environ["FINNEGANS_SISA_URL"], params={
    "ACCESS_TOKEN": token, "PARAM_Campana":"25-26_CampAgr", "PARAM_IndicadorSuperficie":1}, timeout=90)
df = pd.DataFrame(resp.json())
df.columns = df.columns.str.lower()
df = df[df["actividad"].str.contains("algod", case=False, na=False)]

print("zona en columnas:", "zona" in df.columns)
if "zona" in df.columns:
    print("valores unicos de zona:", df["zona"].str.strip().str.lower().unique().tolist())
    print(df[["lugar","zona"]].drop_duplicates().sort_values("zona").to_string())
