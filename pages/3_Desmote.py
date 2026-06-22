import streamlit as st
import plotly.express as px

from utils import (
    inject_css, load_data, sidebar_filters,
    agg_campo_rem, agg_lote, agg_contratista,
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

fibra_total   = rem["cantidadproducidakilos"].sum()
consumo_total = rem["cantidadconsumo"].sum()
rd_total      = fibra_total / consumo_total * 100 if consumo_total > 0 else 0

# ── KPIs ─────────────────────────────────────────────────────────────────────

c1, c2 = st.columns(2)
c1.markdown(kpi_card("Fibra Producida", f"{fibra_total / 1000:,.1f} Tn"), unsafe_allow_html=True)
c2.markdown(kpi_card("Rinde Desmote", f"{rd_total:.1f}%",
    delta=f"{rd_total - 24:.1f}pp vs ref. 24%"), unsafe_allow_html=True)

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

st.subheader("Producción por campo")
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
download_btn(disp_campo, "produccion_campo.xlsx")

st.divider()

st.subheader("Producción por lote")
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
download_btn(disp_lote, "produccion_lote.xlsx")

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
