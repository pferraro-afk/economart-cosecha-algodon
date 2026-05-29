# CLAUDE.md — Control de Cosecha de Algodón — Economart

## ¿Qué es este proyecto?

Sistema para automatizar el seguimiento de cosecha de algodón de Economart (Grupo Duhau). Pipeline: datos de remitos de algodón vía API Finnegans → procesamiento → informes dinámicos de avance de cosecha.

**Contexto:** Pedro trabaja en Economart (Sistemas y Planificación). Este proyecto es independiente del tablero de campaña agrícola — se enfoca específicamente en el control de remitos de cosecha de algodón.

## Principio Central

> **Finnegans es la fuente de verdad. Nunca adivinés ni interpolés datos faltantes — marcalos explícitamente.**

## Fuente de Datos — API Finnegans

### OAuth + Endpoint

```python
import requests, os

# OAuth — usa GET (no POST), parámetros como query string
resp = requests.get(
    os.environ["FINNEGANS_OAUTH_URL"],
    params={
        "grant_type": "client_credentials",
        "client_id": os.environ["FINNEGANS_CLIENT_ID"],
        "client_secret": os.environ["FINNEGANS_CLIENT_SECRET"],
    },
    timeout=30,
)
token = resp.text.strip().strip('"')

# Remitos Algodón
resp = requests.get(
    os.environ["FINNEGANS_REPORT_URL"],
    params={"ACCESS_TOKEN": token},
    timeout=180,
)
df = pd.read_json(resp.text)
df.columns = df.columns.str.lower()
```

> **Credentials:** en `.env` (nunca commitear).
> Cargalas con: `from dotenv import load_dotenv; load_dotenv('.env')`

### Quirks conocidos de la API Finnegans

- **OAuth usa GET** (no POST) con parámetros como query string.
- **NULL literal:** columnas numéricas pueden tener el string `"NULL"`. Parsear con: `pd.to_numeric(df['col'].replace('NULL', None), errors='coerce')`
- **Columnas en minúsculas** tras normalizar con `df.columns = df.columns.str.lower()`.

### Schema del dataset

> Pendiente de exploración inicial. Correr `scripts/explore_api.py` para ver columnas disponibles.

## Estructura del Repo

- `data/raw/` — datos bajados de la API (NO en Git)
- `data/processed/` — datasets limpios (SÍ en Git si no tienen datos sensibles)
- `scripts/` — Python scripts
- `reports/` — informes generados
- `docs/` — schema explorado, decisiones

## Stack Técnico

- Python 3.11+
- `pandas`, `requests`, `python-dotenv`

## Reglas

### Idioma
- Código, variables, comentarios: Inglés
- Output al usuario, informes: Español argentino (voseo)
- Commits git: Español

### Seguridad
- **Nunca commitear credentials.** Siempre en `.env`.
- **Nunca commitear `data/raw/`.**
