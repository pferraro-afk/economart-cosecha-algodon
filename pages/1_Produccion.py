import streamlit as st
import pandas as pd
import plotly.express as px

from utils import (
    inject_css, load_data, sidebar_filters,
    agg_campo_sisa, cruce_campo, cruce_lote,
    totales_row, style_total_row, fmt_num, download_btn,
    kpi_card, sem_avance, sem_desvio, sem_avance_entrega,
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

st.divider()

# ── Cruce Planificación + Remitos ─────────────────────────────────────────────

if rem.empty:
    st.info("Sin remitos para cruzar con planificación.")
    st.stop()

st.subheader("Cruce Planificación + Remitos")
sub_campo, sub_lote = st.tabs(["Por Campo", "Por Lote"])

with sub_campo:
    gc = cruce_campo(sisa, rem)

    tot_prod_c   = gc["tn_producidas"].sum()
    tot_entr_c   = gc["bruto_tn"].sum()
    tot_en_est_c = gc["en_estab_tn"].sum()
    pct_entr_c   = tot_entr_c / tot_prod_c * 100 if tot_prod_c > 0 else 0
    tot_rol_prod = gc["rollos_producidos"].sum()
    tot_rol_carg = gc["rollos_cargados"].sum()

    c1, c2, c3, c4 = st.columns(4)
    c1.markdown(kpi_card("Tn Producidas (Plan.)", f"{tot_prod_c:,.1f}"), unsafe_allow_html=True)
    c2.markdown(kpi_card("Entregado a Desm.", f"{tot_entr_c:,.1f} Tn",
        delta=f"{pct_entr_c:.0f}% entregado", delta_color="off"), unsafe_allow_html=True)
    c3.markdown(kpi_card("En Establecimiento", f"{tot_en_est_c:,.1f} Tn"), unsafe_allow_html=True)
    c4.markdown(kpi_card("Δ Rollos (Carg − Prod)", f"{tot_rol_carg - tot_rol_prod:+,.0f}",
        delta_color="off"), unsafe_allow_html=True)

    fig_gc = px.bar(
        gc.melt(
            id_vars="campo",
            value_vars=["bruto_tn", "en_estab_tn"],
            var_name="origen", value_name="tn",
        ).replace({
            "bruto_tn":    "Entregado (Remitos)",
            "en_estab_tn": "En Establecimiento",
        }),
        x="campo", y="tn", color="origen", barmode="stack",
        labels={"tn": "Tn", "campo": "", "origen": ""},
        color_discrete_map={
            "Entregado (Remitos)": "#2ecc71",
            "En Establecimiento":  "#f39c12",
        },
        height=380,
    )
    fig_gc.update_layout(
        margin=dict(l=0, r=0, t=10, b=40), legend_title="",
        xaxis_tickangle=-30,
        plot_bgcolor="rgba(0,0,0,0)", paper_bgcolor="rgba(0,0,0,0)",
    )
    st.plotly_chart(fig_gc, use_container_width=True)
    st.divider()

    cols_disp = {
        "campo":            "Campo",
        "tn_planificadas":  "Tn Plan",
        "tn_producidas":    "Tn Prod (Plan.)",
        "cumpl_plan_pct":   "% vs Plan",
        "avance_cos_pct":   "Avance Cos %",
        "bruto_tn":         "Entregado Tn",
        "pct_entregado":    "% Entregado",
        "en_estab_tn":      "En Estab Tn",
        "rollos_producidos":"Rollos Prod",
        "rollos_cargados":  "Rollos Carg",
        "delta_rollos":     "Δ Rollos",
        "pct_rollos_carg":  "% Rollos Carg",
        "cant_remitos":     "N° Remitos",
    }
    disp_gc = gc.rename(columns=cols_disp)[list(cols_disp.values())]
    disp_gc_tot = totales_row(disp_gc, "Campo")
    n_gc = len(disp_gc)
    st.dataframe(
        style_total_row(
            disp_gc_tot.style
                .format(fmt_num(disp_gc_tot), na_rep="—")
                .map(sem_avance, subset=["Avance Cos %"])
                .map(sem_avance_entrega, subset=["% Entregado"]),
            n_gc,
        ),
        use_container_width=True, hide_index=True,
    )
    download_btn(disp_gc, "cruce_campo.xlsx")

with sub_lote:
    gl = cruce_lote(sisa, rem)

    gl_plot = gl.dropna(subset=["tn_producidas"]).copy()
    gl_plot = gl_plot[gl_plot["tn_producidas"] > 0].sort_values(
        ["campo", "pct_entregado"], ascending=[True, False]
    )
    if not gl_plot.empty:
        fig_gl = px.bar(
            gl_plot,
            x="pct_entregado",
            y="lote",
            color="campo",
            orientation="h",
            custom_data=["tn_producidas", "bruto_tn", "avance_pct", "campo"],
            labels={
                "pct_entregado": "% Entregado vs Producido",
                "lote":          "Lote",
                "campo":         "Campo",
            },
            height=max(400, len(gl_plot) * 26),
        )
        fig_gl.update_traces(
            hovertemplate=(
                "<b>%{y}</b> — %{customdata[3]}<br>"
                "Entregado: %{x:.1f}%<br>"
                "Tn producidas: %{customdata[0]:,.0f}<br>"
                "Tn entregadas: %{customdata[1]:,.0f}<br>"
                "Avance cosecha: %{customdata[2]:.1f}%"
                "<extra></extra>"
            )
        )
        fig_gl.add_vline(
            x=100,
            line_dash="dot", line_color="#aaa", line_width=1,
            annotation_text="100%", annotation_position="top right",
        )
        fig_gl.update_layout(
            margin=dict(l=0, r=20, t=10, b=0), legend_title="",
            plot_bgcolor="rgba(0,0,0,0)", paper_bgcolor="rgba(0,0,0,0)",
            yaxis=dict(tickfont=dict(size=11)),
        )
        st.plotly_chart(fig_gl, use_container_width=True)
        st.divider()

    cols_l = {
        "campo":            "Campo",
        "lote":             "Lote",
        "tn_producidas":    "Tn Prod (Plan.)",
        "sup_cosechada":    "Sup Cos ha",
        "avance_pct":       "Avance %",
        "rollos_producidos":"Rollos Prod",
        "bruto_tn":         "Entregado Tn",
        "remitos":          "N° Remitos",
        "pct_entregado":    "% Entregado",
    }
    disp_gl = gl.rename(columns=cols_l)[[v for v in cols_l.values() if v in gl.rename(columns=cols_l).columns]]
    st.dataframe(
        disp_gl.style
            .format(fmt_num(disp_gl), na_rep="—")
            .map(sem_avance, subset=[c for c in ["Avance %"] if c in disp_gl.columns])
            .map(sem_avance_entrega, subset=[c for c in ["% Entregado"] if c in disp_gl.columns]),
        use_container_width=True, hide_index=True,
    )
    download_btn(disp_gl, "cruce_lote.xlsx")
