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

### Schema del dataset (AnalisisRemitosAlgodonDuhau)

Columnas clave (minúsculas tras normalización): `pesoneto`, `cantidadproducidakilos`, `cantidadproducidafardos`, `rindefibra`, `supsembrada`, `depositodestino`, `empresa`, `establecimiento`, `loteproduccion`, `contratistacosecha`, `partida`, `fecha`.

---

## API 2 — Control SISA (planificado vs real)

### OAuth + Endpoint

```python
# OAuth: igual que API 1 (GET con query params, token = resp.text.strip().strip('"'))
# IMPORTANTE: renovar token en CADA llamada a esta API

resp = requests.get(
    os.environ["FINNEGANS_SISA_URL"],  # https://api.finneg.com/api/reports/ControlSisaDuhau
    params={
        "ACCESS_TOKEN":              token,
        "PARAM_Campana":             "25-26_CampAgr",
        "PARAM_IndicadorSuperficie": 1,
    },
    timeout=180,
)
df = pd.DataFrame(resp.json())
df.columns = df.columns.str.lower()
```

> Credencial: misma del `.env` (`FINNEGANS_SISA_URL` agregado).

### Filtro de actividad algodón

```python
df = df[df["actividad"].str.contains("algod", case=False, na=False)]
```

Variantes existentes: "Algodón" (140 lotes), "Algodón 2da" (9), "Algodón sobre melilotus" (2). Usar "algod" (no "algodon") porque vienen con tilde.

### Schema del dataset (ControlSisaDuhau)

Columnas clave (minúsculas): `lugar`, `lote`, `empresa`, `zona`, `actividad`, `superficieplanificada`, `superficiesembrada`, `superficiecosechada`, `porcentajeavance`, `tnplanificados`, `tnproducidos`, `tnproducidossecos`, `rindeesperado`, `rindeobtenido`, `restoacosechar`, `tncertificada`, `cantidadproducidasecundaria`, `fechaprimeracosecha`, `fechaultimacosecha`.

### Quirks conocidos

- `lugar` viene con espacios al final — normalizar con `.str.strip()`
- `empresa` también viene con espacio al inicio — normalizar con `.str.strip()`
- **Rollos producidos = `cantidadproducidasecundaria`** (NO `cantidaddeproductoscosechado`)
  - `cantidadproducidasecundaria` es la cantidad de rollos cosechados (ej: 200 rollos para 800 tn = ~4 tn/rollo, peso típico)
  - `cantidaddeproductoscosechado` es otra cosa (probablemente nº de pasadas o tipos de producto), no usar para rollos

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
