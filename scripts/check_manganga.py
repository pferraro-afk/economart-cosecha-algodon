import requests
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
print("Response preview:", resp2.text[:200])
