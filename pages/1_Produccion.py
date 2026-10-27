import streamlit as st
import pandas as pd
import plotly.express as px

from utils import (
    inject_css, load_data, sidebar_filters,
    agg_campo_sisa,
    totales_row, style_total_row, fmt_num, download_btn,
    kpi_card, sem_avance, sem_desvio,
)

inject_css()

st.markdown("← [Volver al resumen](/) ", unsafe_allow_html=False)
st.header("🌱 Producción — Detalle completo")

raw_rem, raw_sisa, rem_error, sisa_error = load_data()
sisa, rem = sidebar_filters(raw_rem, raw_sisa)

if sisa_error:
    st.warning(f"⚠️ Planificación no disponible: {sisa_error}")
if rem_error:
    st.warning(f"⚠️ Remitos no disponibles: {rem_error}")

if sisa.empty:
    st.warning("Sin datos de planificación para los filtros seleccionados.")
    st.stop()

vc_sisa = agg_campo_sisa(sisa)

# ── KPIs ─────────────────────────────────────────────────────────────────────

tot_sup_plan = sisa["superficieplanificada"].sum()
tot_sup_semb = sisa["superficiesembrada"].sum()
tot_sup_cos  = sisa["superficiecosechada"].sum()
tot_tn_plan  = sisa["tnplanificados"].sum()
tot_tn_prod  = sisa["tnproducidos"].sum()
tot_resto    = sisa["restoacosechar"].sum()
avance_gl    = tot_sup_cos / tot_sup_semb * 100 if tot_sup_semb > 0 else 0

c1, c2, c3, c4 = st.columns(4)
c1.markdown(kpi_card("Sup Planificada", f"{tot_sup_plan:,.0f} ha"), unsafe_allow_html=True)
c2.markdown(kpi_card("Sup Sembrada",    f"{tot_sup_semb:,.0f} ha"), unsafe_allow_html=True)
c3.markdown(kpi_card("Sup Cosechada",   f"{tot_sup_cos:,.0f} ha"), unsafe_allow_html=True)
c4.markdown(kpi_card("Avance Global", f"{avance_gl:.1f}%",
    delta=f"{avance_gl - 100:.1f}% restante", delta_color="inverse"), unsafe_allow_html=True)

c5, c6, c7, _ = st.columns(4)
c5.markdown(kpi_card("Tn Planificadas", f"{tot_tn_plan:,.0f}"), unsafe_allow_html=True)
c6.markdown(kpi_card("Tn Producidas", f"{tot_tn_prod:,.0f}",
    delta=f"{tot_tn_prod - tot_tn_plan:+,.0f} vs plan"), unsafe_allow_html=True)
c7.markdown(kpi_card("Resto a Cosechar", f"{tot_resto:,.0f} ha"), unsafe_allow_html=True)

st.progress(
    min(avance_gl / 100, 1.0),
    text=f"Avance de cosecha: {avance_gl:.1f}% de la superficie sembrada",
)

st.divider()

# ── Avance de cosecha por campo ───────────────────────────────────────────────

st.subheader("Avance de cosecha por campo (%)")
fig_av = px.bar(
    vc_sisa.sort_values("avance_pct"),
    x="avance_pct", y="lugar", orientation="h",
    color="avance_pct",
    color_continuous_scale=["#e74c3c", "#f39c12", "#27ae60"],
    range_color=[0, 100],
    labels={"avance_pct": "%", "lugar": ""},
    text="avance_pct",
)
fig_av.update_traces(
    texttemplate="%{text:.1f}%", textposition="outside",
    hovertemplate="<b>%{y}</b><br>Avance: <b>%{x:.1f}%</b><extra></extra>",
)
fig_av.update_layout(
    height=420, margin=dict(l=0, r=40, t=0, b=0),
    coloraxis_showscale=False,
    plot_bgcolor="rgba(0,0,0,0)", paper_bgcolor="rgba(0,0,0,0)",
)
st.plotly_chart(fig_av, use_container_width=True)

st.divider()

# ── Gráficos ──────────────────────────────────────────────────────────────────

st.subheader("Rinde planificado vs producido (kg/ha)")
_zona_order = ["nea norte", "nea centro norte", "nea centro sur", "nea sur"]
_has_zona = "zona" in vc_sisa.columns and vc_sisa["zona"].notna().any()

if _has_zona:
    _zona_cat = pd.Categorical(vc_sisa["zona"], categories=_zona_order, ordered=True)
    _vc_sorted = vc_sisa.assign(zona=_zona_cat).sort_values(["zona", "lugar"])
    _lugar_order = _vc_sorted["lugar"].unique().tolist()
    df_rinde_melt = _vc_sorted.melt(
        id_vars=["lugar", "zona"],
        value_vars=["rinde_esp_kgha", "rinde_obt_kgha"],
        var_name="tipo", value_name="kg_ha",
    ).replace({"rinde_esp_kgha": "Planificado", "rinde_obt_kgha": "Producido"})
    fig_rinde = px.bar(
        df_rinde_melt,
        x="lugar", y="kg_ha", color="tipo", barmode="group",
        category_orders={"lugar": _lugar_order},
        labels={"kg_ha": "kg/ha", "lugar": "", "tipo": ""},
        color_discrete_map={"Planificado": "#aed6f1", "Producido": "#2ecc71"},
    )
    # separadores y etiquetas de zona
    _zone_sizes = _vc_sorted.groupby("zona", observed=True)["lugar"].nunique()
    _x_pos = -0.5
    for _z in _zona_order:
        if _z not in _zone_sizes.index:
            continue
        _n = _zone_sizes[_z]
        _label_x = _x_pos + _n / 2
        fig_rinde.add_annotation(
            x=_label_x, y=1.06, xref="x", yref="paper",
            text=f"<b>{_z.title()}</b>",
            showarrow=False, font=dict(size=11, color="#555"),
            bgcolor="rgba(240,240,240,0.7)", borderpad=3,
        )
        if _x_pos > -0.5:
            fig_rinde.add_shape(
                type="line", x0=_x_pos, x1=_x_pos, y0=0, y1=1,
                xref="x", yref="paper",
                line=dict(color="#ccc", width=1, dash="dot"),
            )
        _x_pos += _n
    fig_rinde.update_layout(
        height=460, margin=dict(l=0, r=0, t=50, b=60), legend_title="",
        plot_bgcolor="rgba(0,0,0,0)", paper_bgcolor="rgba(0,0,0,0)",
    )
    fig_rinde.update_xaxes(tickangle=-30)
else:
    df_rinde_melt = vc_sisa.melt(
        id_vars="lugar",
        value_vars=["rinde_esp_kgha", "rinde_obt_kgha"],
        var_name="tipo", value_name="kg_ha",
    ).replace({"rinde_esp_kgha": "Planificado", "rinde_obt_kgha": "Producido"})
    fig_rinde = px.bar(
        df_rinde_melt,
        x="lugar", y="kg_ha", color="tipo", barmode="group",
        labels={"kg_ha": "kg/ha", "lugar": "", "tipo": ""},
        color_discrete_map={"Planificado": "#aed6f1", "Producido": "#2ecc71"},
    )
    fig_rinde.update_layout(
        height=420, margin=dict(l=0, r=0, t=0, b=0), legend_title="",
        plot_bgcolor="rgba(0,0,0,0)", paper_bgcolor="rgba(0,0,0,0)",
    )
st.plotly_chart(fig_rinde, use_container_width=True)

# ── Tabla detalle por campo ───────────────────────────────────────────────────

st.subheader("Detalle por campo — Planificado vs Real")
disp_sisa = vc_sisa.rename(columns={
    "empresasucursal":  "Sucursal",
    "lugar":            "Campo",
    "lotes":            "Lotes",
    "sup_planificada":  "S.Plan ha",
    "sup_sembrada":     "S.Semb ha",
    "sup_cosechada":    "S.Cos ha",
    "avance_pct":       "Avance %",
    "tn_planificadas":  "Tn Plan",
    "tn_producidas":    "Tn Prod",
    "tn_resto":         "Resto ha",
    "desvio_tn":        "Desvío Tn",
    "desvio_pct":       "Desvío %",
    "rinde_esp_kgha":   "R.Esp kg/ha",
    "rinde_obt_kgha":   "R.Obt kg/ha",
})[["Sucursal", "Campo", "Lotes", "S.Plan ha", "S.Semb ha", "S.Cos ha",
    "Avance %", "Tn Plan", "Tn Prod", "Desvío Tn", "Desvío %",
    "R.Esp kg/ha", "R.Obt kg/ha"]]

disp_sisa_tot = totales_row(disp_sisa, "Campo")
n_sisa = len(disp_sisa)
st.dataframe(
    style_total_row(
        disp_sisa_tot.style
            .format(fmt_num(disp_sisa_tot), na_rep="—")
            .map(sem_avance, subset=["Avance %"])
            .map(sem_desvio, subset=["Desvío %"]),
        n_sisa,
    ),
    use_container_width=True,
    hide_index=True,
)
download_btn(disp_sisa, "planificacion_campo.xlsx")

# ── Detalle por lote (SISA) ───────────────────────────────────────────────────

with st.expander("Ver detalle por lote (Planificación)"):
    cols_lote = [
        "empresasucursal", "lugar", "lote", "actividad",
        "superficieplanificada", "superficiesembrada", "superficiecosechada",
        "porcentajeavance", "tnplanificados", "tnproducidos",
        "restoacosechar", "rindeesperado", "rindeobtenido",
    ]
    disp_lote_sisa = (
        sisa[[c for c in cols_lote if c in sisa.columns]]
        .sort_values(["empresasucursal", "lugar", "lote"])
        .rename(columns={
            "empresasucursal":      "Sucursal",
            "lugar":                "Campo",
            "lote":                 "Lote",
            "actividad":            "Actividad",
            "superficieplanificada":"S.Plan ha",
            "superficiesembrada":   "S.Semb ha",
            "superficiecosechada":  "S.Cos ha",
            "porcentajeavance":     "Avance %",
            "tnplanificados":       "Tn Plan",
            "tnproducidos":         "Tn Prod",
            "restoacosechar":       "Resto ha",
            "rindeesperado":        "R.Esp kg/ha",
            "rindeobtenido":        "R.Obt kg/ha",
        })
    )
    st.dataframe(
        disp_lote_sisa.style
            .format(fmt_num(disp_lote_sisa), na_rep="—")
            .map(sem_avance, subset=["Avance %"]),
        use_container_width=True,
        hide_index=True,
    )
    download_btn(disp_lote_sisa, "detalle_lotes_planificacion.xlsx")
