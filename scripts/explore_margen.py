"""Explore Finnegans gross-margin API for cotton (campaign 25-26).

Usage (from repo root, with the same .env as the dashboard):
    python scripts/explore_margen.py
    python scripts/explore_margen.py --campana 25-26_CampAgr

Outputs (data/raw/ is gitignored, never commit it):
    data/raw/margen_bruto_algodon.xlsx   -> cotton rows only, one sheet per source
    data/raw/margen_bruto_full.parquet   -> full report, all crops
    data/processed/schema_margen.csv     -> column names/types only (no amounts)
"""
import argparse
import json
import os
import sys

import pandas as pd
import requests
from dotenv import load_dotenv

load_dotenv(".env")

BASE = "https://api.finneg.com/api"
MARGEN_URL = os.environ.get(
    "FINNEGANS_MARGEN_URL", f"{BASE}/reports/DWMARGENBRUTOAGRICOLAAPI"
)


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


def get_json(url, extra_params=None):
    # Fresh token on every call (same quirk as ControlSisaDuhau)
    params = {"ACCESS_TOKEN": get_token(), **(extra_params or {})}
    resp = requests.get(url, params=params, timeout=300)
    if resp.status_code != 200:
        print(f"  ! HTTP {resp.status_code}: {resp.text[:300]}")
        return None
    try:
        return resp.json()
    except ValueError:
        print(f"  ! Respuesta no es JSON: {resp.text[:300]}")
        return None


def to_df(data):
    df = pd.DataFrame(data if isinstance(data, list) else [data])
    df.columns = df.columns.str.lower()
    for col in df.columns:
        if not pd.api.types.is_numeric_dtype(df[col]):
            num = pd.to_numeric(df[col].replace("NULL", None), errors="coerce")
            # keep as numeric only if the column really is numeric
            if num.notna().sum() >= 0.9 * df[col].replace("NULL", None).notna().sum() > 0:
                df[col] = num
    return df


def cotton_mask(df):
    text_cols = [c for c in df.columns if not pd.api.types.is_numeric_dtype(df[c])]
    mask = pd.Series(False, index=df.index)
    for c in text_cols:
        mask |= df[c].astype(str).str.contains("algod", case=False, na=False)
    return mask


def schema(df):
    rows = []
    for c in df.columns:
        is_text = not pd.api.types.is_numeric_dtype(df[c])
        rows.append({
            "columna": c,
            "tipo": str(df[c].dtype),
            "no_nulos": int(df[c].notna().sum()),
            # only show example values for text columns (no amounts)
            "ejemplos": ", ".join(map(str, df[c].dropna().unique()[:5])) if is_text else "",
        })
    return pd.DataFrame(rows)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--campana", default=None,
                    help="Valor para PARAM_Campana si el reporte lo pide (ej. 25-26_CampAgr)")
    args = ap.parse_args()

    os.makedirs("data/raw", exist_ok=True)
    os.makedirs("data/processed", exist_ok=True)

    print("1) Margen bruto agricola...")
    params = {"PARAM_Campana": args.campana} if args.campana else None
    data = get_json(MARGEN_URL, params)
    if data is None and not args.campana:
        print("  Reintentando con PARAM_Campana=25-26_CampAgr...")
        data = get_json(MARGEN_URL, {"PARAM_Campana": "25-26_CampAgr"})
    if data is None:
        sys.exit("No se pudo bajar el reporte de margen. Revisá el mensaje de arriba.")

    full = to_df(data)
    full.to_parquet("data/raw/margen_bruto_full.parquet", index=False)
    schema(full).to_csv("data/processed/schema_margen.csv", index=False)
    cot = full[cotton_mask(full)]
    print(f"  OK {len(full):,} filas totales, {len(cot):,} de algodon, {len(full.columns)} columnas")
    print(f"  Columnas: {list(full.columns)}")

    sheets = {"margen_algodon": cot}

    # 2) Detail endpoints need an id. Try ids found in the margin report.
    id_cols = [c for c in cot.columns if "id" in c and cot[c].notna().any()]
    print(f"\n2) Columnas tipo id en el reporte: {id_cols}")
    probes = {
        "actividadAgro": [c for c in id_cols if "activ" in c],
        "APIGetLoteActividadCW": [c for c in id_cols if "lote" in c or "activ" in c],
        "planificacionesAgricolas": [c for c in id_cols if "planif" in c],
    }
    for endpoint, cols in probes.items():
        if not cols:
            print(f"  - {endpoint}: no encontre columna de id para probar")
            continue
        sample_id = cot[cols[0]].dropna().iloc[0]
        sample_id = int(sample_id) if isinstance(sample_id, float) else sample_id
        print(f"  - {endpoint}/{sample_id} (id tomado de '{cols[0]}')")
        d = get_json(f"{BASE}/{endpoint}/{sample_id}")
        if d is not None:
            with open(f"data/raw/sample_{endpoint}.json", "w", encoding="utf-8") as f:
                json.dump(d, f, ensure_ascii=False, indent=2, default=str)
            try:
                sheets[f"muestra_{endpoint}"[:31]] = pd.json_normalize(d)
            except Exception:
                pass

    out = "data/raw/margen_bruto_algodon.xlsx"
    with pd.ExcelWriter(out) as xw:
        for name, df in sheets.items():
            df.to_excel(xw, sheet_name=name, index=False)
    print(f"\nListo. Adjuntá en el chat: {out} y data/processed/schema_margen.csv")


if __name__ == "__main__":
    main()
