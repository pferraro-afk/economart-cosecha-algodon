import streamlit as st
import plotly.express as px

from utils import (
    inject_css, load_data, sidebar_filters,
    agg_campo_rem, agg_lote, agg_contratista, agg_desmotadora,
    sup_lote, totales_row, style_total_row, fmt_num, download_btn,
    kpi_card, sem_rinde,
)

inject_css()

st.markdown("← [Volver al resumen](/) ", unsafe_allow_html=False)
st.header("🏭 Desmote — Detalle completo")

raw_rem, raw_sisa, rem_error, sisa_error = load_data()
sisa, rem = sidebar_filters(raw_rem, raw_sisa)

if sisa_error:
    st.warning(f"⚠️ Planificación no disponible: {sisa_error}")
if rem_error:
    st.warning(f"⚠️ Remitos no disponibles: {rem_error}")

if rem.empty:
    st.info("Sin remitos para los filtros seleccionados.")
    st.stop()

sup   = sup_lote(rem)
vc    = agg_campo_rem(rem, sup)
vl    = agg_lote(rem, sup)
vcont = agg_contratista(rem)
vd    = agg_desmotadora(rem)

fibra_total   = rem["cantidadproducidakilos"].sum()
consumo_total = rem["cantidadconsumo"].sum()
rd_total      = fibra_total / consumo_total * 100 if consumo_total > 0 else 0

# ── KPIs ─────────────────────────────────────────────────────────────────────

_sup_semb_desm = vc["sup_ha"].sum() if "sup_ha" in vc.columns else 0
_rinde_fibra_tnha = (fibra_total / 1000) / _sup_semb_desm if _sup_semb_desm > 0 else None

entrega_tot = vd["entrega_kg"].sum()
sin_desm_tot = vd["stock_sin_desmotar"].sum()
fardos_tot = int(rem["cantidadproducidafardos"].sum())

c1, c2, c3, c4 = st.columns(4)
c1.markdown(kpi_card("Entregado a Desm.", f"{entrega_tot / 1000:,.1f} Tn"), unsafe_allow_html=True)
c2.markdown(kpi_card("Desmotado", f"{consumo_total / 1000:,.1f} Tn"), unsafe_allow_html=True)
c3.markdown(kpi_card("Sin Desmotar", f"{sin_desm_tot / 1000:,.1f} Tn"), unsafe_allow_html=True)
c4.markdown(kpi_card("Fardos", f"{fardos_tot:,}"), unsafe_allow_html=True)

c5, c6, c7, _ = st.columns(4)
c5.markdown(kpi_card("Fibra Producida", f"{fibra_total / 1000:,.1f} Tn"), unsafe_allow_html=True)
c6.markdown(kpi_card("Rinde Desmote", f"{rd_total:.1f}%",
    delta=f"{rd_total - 24:.1f}pp vs ref. 24%"), unsafe_allow_html=True)
if _rinde_fibra_tnha is not None:
    c7.markdown(kpi_card("Rinde Fibra", f"{_rinde_fibra_tnha:.3f} Tn/ha"), unsafe_allow_html=True)
else:
    c7.markdown(kpi_card("Rinde Fibra", "—"), unsafe_allow_html=True)

st.divider()

# ── Por desmotadora ───────────────────────────────────────────────────────────

st.subheader("Entregado vs. Desmotado por desmotadora")
vd_tot = vd.groupby("desmotadora", as_index=False).agg(
    entrega_kg=("entrega_kg", "sum"),
    consumo_kg=("consumo_kg", "sum"),
)
fig_vd = px.bar(
    vd_tot.melt(
        id_vars="desmotadora",
        value_vars=["entrega_kg", "consumo_kg"],
        var_name="tipo", value_name="kg",
    ).replace({"entrega_kg": "Entregado", "consumo_kg": "Desmotado"}),
    x="desmotadora", y="kg", color="tipo", barmode="group",
    labels={"kg": "Kg", "desmotadora": "", "tipo": ""},
    color_discrete_map={"Entregado": "#aed6f1", "Desmotado": "#2ecc71"},
    text_auto=".2s",
    height=420,
)
fig_vd.update_layout(
    margin=dict(l=0, r=0, t=10, b=40), legend_title="",
    xaxis_tickangle=-30,
    plot_bgcolor="rgba(0,0,0,0)", paper_bgcolor="rgba(0,0,0,0)",
)
st.plotly_chart(fig_vd, use_container_width=True)

st.subheader("Detalle por desmotadora")
disp_desm = vd.rename(columns={
    "desmotadora":        "Desmotadora",
    "empresa":            "Empresa",
    "establecimiento":    "Campo",
    "entrega_kg":         "Entregado (kg)",
    "consumo_kg":         "Desmotado (kg)",
    "stock_sin_desmotar": "Sin Desmotar (kg)",
    "fibra_kg":           "Fibra (kg)",
    "rinde_desmote":      "Rinde (%)",
    "fardos":             "Fardos",
    "ppf_kg":             "PP Fardo (kg)",
})[["Desmotadora", "Empresa", "Campo", "Entregado (kg)", "Desmotado (kg)",
    "Sin Desmotar (kg)", "Fibra (kg)", "Rinde (%)", "Fardos", "PP Fardo (kg)"]]
st.dataframe(
    disp_desm.style
        .format(fmt_num(disp_desm), na_rep="—")
        .map(sem_rinde, subset=["Rinde (%)"]),
    use_container_width=True,
    hide_index=True,
)
download_btn(disp_desm, "desmote_desmotadora.xlsx")

st.divider()

# ── Gráfico rinde por campo ───────────────────────────────────────────────────

st.subheader("Rinde al desmote por campo (%)")
fig_desm = px.bar(
    vc.sort_values("rinde_desmote"),
    x="rinde_desmote", y="establecimiento", color="empresa",
    orientation="h",
    labels={"rinde_desmote": "%", "establecimiento": ""},
    color_discrete_sequence=px.colors.qualitative.Set2,
)
fig_desm.add_vline(x=24, line_dash="dot", line_color="orange", annotation_text="24%")
fig_desm.add_vline(x=28, line_dash="dot", line_color="green",  annotation_text="28%")
fig_desm.update_traces(
    hovertemplate="<b>%{y}</b><br>%{data.name}: <b>%{x:.1f}%</b><extra></extra>",
)
fig_desm.update_layout(
    height=420, margin=dict(l=0, r=0, t=0, b=0), legend_title="",
    plot_bgcolor="rgba(0,0,0,0)", paper_bgcolor="rgba(0,0,0,0)",
)
st.plotly_chart(fig_desm, use_container_width=True)

st.divider()

# ── Tablas detalle ────────────────────────────────────────────────────────────

st.subheader("Desmote por campo")
disp_campo = vc.rename(columns={
    "empresa":        "Empresa",
    "establecimiento":"Campo",
    "sup_ha":         "Sup (ha)",
    "bruto_tn":       "Bruto (Tn)",
    "rinde_kgha":     "Rinde (kg/ha)",
    "fibra_tn":       "Fibra (Tn)",
    "rinde_desmote":  "Rinde Desm. (%)",
    "fardos":         "Fardos",
    "ppf_kg":         "PP Fardo (kg)",
    "remitos":        "Remitos",
})[["Empresa", "Campo", "Sup (ha)", "Bruto (Tn)", "Rinde (kg/ha)",
    "Fibra (Tn)", "Rinde Desm. (%)", "Fardos", "PP Fardo (kg)", "Remitos"]]

disp_campo_tot = totales_row(disp_campo, "Empresa", label="TOTAL")
n_campo = len(disp_campo)
st.dataframe(
    style_total_row(
        disp_campo_tot.style
            .format(fmt_num(disp_campo_tot), na_rep="—")
            .map(sem_rinde, subset=["Rinde Desm. (%)"]),
        n_campo,
    ),
    use_container_width=True,
    hide_index=True,
)
download_btn(disp_campo, "desmote_campo.xlsx")

st.divider()

st.subheader("Desmote por lote")
disp_lote = vl.rename(columns={
    "empresa":         "Empresa",
    "establecimiento": "Campo",
    "loteproduccion":  "Lote",
    "sup_ha":          "Sup (ha)",
    "bruto_tn":        "Bruto (Tn)",
    "rinde_kgha":      "Rinde (kg/ha)",
    "fibra_tn":        "Fibra (Tn)",
    "rinde_desmote":   "Rinde Desm. (%)",
    "fardos":          "Fardos",
})[["Empresa", "Campo", "Lote", "Sup (ha)", "Bruto (Tn)", "Rinde (kg/ha)",
    "Fibra (Tn)", "Rinde Desm. (%)", "Fardos"]]
st.dataframe(
    disp_lote.style
        .format(fmt_num(disp_lote), na_rep="—")
        .map(sem_rinde, subset=["Rinde Desm. (%)"]),
    use_container_width=True,
    hide_index=True,
)
download_btn(disp_lote, "desmote_lote.xlsx")

st.divider()

st.subheader("Rinde por contratista")
disp_cont = vcont.rename(columns={
    "contratistacosecha": "Contratista",
    "bruto_kg":           "Bruto (kg)",
    "fibra_kg":           "Fibra (kg)",
    "rinde_desmote":      "Rinde (%)",
    "fardos":             "Fardos",
})[["Contratista", "Bruto (kg)", "Fibra (kg)", "Rinde (%)", "Fardos"]]
st.dataframe(
    disp_cont.style
        .format(fmt_num(disp_cont), na_rep="—")
        .map(sem_rinde, subset=["Rinde (%)"]),
    use_container_width=True,
    hide_index=True,
)
download_btn(disp_cont, "contratistas.xlsx")
