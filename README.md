# Control de Cosecha de Algodón — Economart

Tablero Streamlit para seguimiento en tiempo real de la cosecha de algodón — Grupo Duhau, Campaña 2025/26.

## Qué hace

- Cruza datos de planificación SISA con remitos reales de cosecha
- Muestra avance por establecimiento: producido, entregado a desmotadora y stock en campo
- Controla rollos producidos (SISA) vs cargados en remitos
- Analiza rendimiento por campo, lote, contratista y desmotadora
- Exporta cualquier tabla a Excel con un botón
- Modo parcial: si una API falla, muestra la otra con un aviso

## Fuentes de datos

| Servicio | Endpoint Finnegans | Descripción |
|----------|--------------------|-------------|
| Remitos  | `AnalisisRemitosAlgodonDuhau` | Remitos de cosecha por lote |
| SISA     | `ControlSisaDuhau` | Planificado vs producido por campo |

## Stack

- Python 3.11+
- Streamlit · pandas · plotly · requests · openpyxl

## Desarrollo local

```bash
pip install -r requirements.txt
# crear .env con las credenciales (ver .env.example)
streamlit run app.py
```

## Variables de entorno / Secrets

```
FINNEGANS_CLIENT_ID
FINNEGANS_CLIENT_SECRET
FINNEGANS_OAUTH_URL
FINNEGANS_REPORT_URL
FINNEGANS_SISA_URL
```

Para desarrollo local: crear un archivo `.env` con esos valores.

## Deploy en Streamlit Cloud

1. Conectar el repo en [share.streamlit.io](https://share.streamlit.io)
2. Ir a **Settings → Secrets** y pegar el contenido de `.streamlit/secrets.toml.template` con los valores reales
3. El archivo `runtime.txt` ya especifica la versión de Python

## Autor

Pedro Ferraro — Economart / Grupo Duhau
