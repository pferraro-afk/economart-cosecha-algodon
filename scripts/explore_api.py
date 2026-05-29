import os, requests, pandas as pd
from dotenv import load_dotenv

load_dotenv('.env')

def get_token():
    resp = requests.get(
        os.environ["FINNEGANS_OAUTH_URL"],
        params={
            "grant_type": "client_credentials",
            "client_id": os.environ["FINNEGANS_CLIENT_ID"],
            "client_secret": os.environ["FINNEGANS_CLIENT_SECRET"],
        },
        timeout=30,
    )
    resp.raise_for_status()
    return resp.text.strip().strip('"')

def fetch_data(token):
    resp = requests.get(
        os.environ["FINNEGANS_REPORT_URL"],
        params={"ACCESS_TOKEN": token},
        timeout=180,
    )
    resp.raise_for_status()
    return pd.DataFrame(resp.json())

if __name__ == "__main__":
    print("Obteniendo token...")
    token = get_token()
    print("Bajando datos...")
    df = fetch_data(token)
    df.columns = df.columns.str.lower()
    print(f"\nOK Dataset cargado: {len(df):,} filas, {len(df.columns)} columnas")
    print(f"\nColumnas disponibles:\n{list(df.columns)}")
    print(f"\nPrimeras filas:")
    print(df.head(3).to_string())
    df.to_parquet("data/raw/remitos_algodon.parquet", index=False)
    print("\nDatos guardados en data/raw/remitos_algodon.parquet")
