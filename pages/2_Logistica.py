import streamlit as st
import plotly.express as px

from utils import (
    inject_css, load_data, sidebar_filters,
    agg_campo_rem, agg_desmotadora, agg_semanal, cruce_campo, cruce_fechas,
    sup_lote, totales_row, style_total_row, fmt_num, download_btn,
    kpi_card, sem_rinde,
)

inject_css()

st.markdown("← [Volver al resumen](/) ", unsafe_allow_html=False)
st.header("🚚 Logística — Detalle completo")

raw_rem, raw_sisa, rem_error, sisa_error = load_data()
sisa, rem = sidebar_filters(raw_rem, raw_sisa)

if sisa_error:
    st.warning(f"⚠️ Planificación no disponible: {sisa_error}")
if rem_error:
    st.warning(f"⚠️ Remitos no disponibles: {rem_error}")

if rem.empty:
    st.info("Sin remitos para los filtros seleccionados.")
    st.stop()

sup  = sup_lote(rem)
vc   = agg_campo_rem(rem, sup)
vd   = agg_desmotadora(rem)
vsem = agg_semanal(rem)

bruto_total = rem["cantidad"].sum()

# ── KPIs ─────────────────────────────────────────────────────────────────────

c1, c2, c3, c4 = st.columns(4)
c1.markdown(kpi_card("Algodón Bruto",   f"{bruto_total / 1000:,.1f} Tn"), unsafe_allow_html=True)
c2.markdown(kpi_card("Remitos",         str(len(rem))), unsafe_allow_html=True)
c3.markdown(kpi_card("Campos",          str(rem["establecimiento"].nunique())), unsafe_allow_html=True)
c4.markdown(kpi_card("Fardos",          f"{int(rem['cantidadproducidafardos'].sum()):,}"), unsafe_allow_html=True)

st.divider()

# ── Gráficos ──────────────────────────────────────────────────────────────────

col_g1, col_g2 = st.columns(2)

with col_g1:
    st.subheader("Algodón bruto por campo (Tn)")
    fig_log = px.bar(
        vc.sort_values("bruto_tn"),
        x="bruto_tn", y="establecimiento", color="empresa",
        orientation="h",
        labels={"bruto_tn": "Tn", "establecimiento": ""},
        color_discrete_sequence=px.colors.qualitative.Set2,
    )
    fig_log.update_traces(
        hovertemplate="<b>%{y}</b><br>%{data.name}: <b>%{x:,.1f} Tn</b><extra></extra>",
    )
    fig_log.update_layout(
        height=420, margin=dict(l=0, r=0, t=0, b=0), legend_title="",
        plot_bgcolor="rgba(0,0,0,0)", paper_bgcolor="rgba(0,0,0,0)",
    )
    st.plotly_chart(fig_log, use_container_width=True)

with col_g2:
    if not vsem.empty and vsem["semana"].notna().any():
        st.subheader("Tn entregada por semana")
        vsem["bruto_tn"] = vsem["bruto_kg"] / 1000
        fig_sem = px.bar(
            vsem, x="semana", y="bruto_tn",
            labels={"semana": "Semana", "bruto_tn": "Tn Entregada"},
            color_discrete_sequence=["#2ecc71"],
            text="bruto_tn",
        )
        fig_sem.update_traces(
            texttemplate="%{text:,.1f}", textposition="outside",
            hovertemplate="Semana %{x|%d/%m}<br><b>%{y:,.1f} Tn</b><extra></extra>",
        )
        fig_sem.update_layout(
            height=420, margin=dict(l=0, r=0, t=10, b=0),
            plot_bgcolor="rgba(0,0,0,0)", paper_bgcolor="rgba(0,0,0,0)",
        )
        st.plotly_chart(fig_sem, use_container_width=True)

st.divider()

# ── Sub-tabs: Rollos · Fechas · Desmotadora ───────────────────────────────────

sub_rollos, sub_fechas, sub_desm = st.tabs(["Rollos", "Fechas", "Por Desmotadora"])

with sub_rollos:
    if sisa.empty:
        st.info("Sin datos de planificación para los filtros seleccionados.")
    else:
        gc_r = cruce_campo(sisa, rem)[
            ["campo", "rollos_producidos", "rollos_cargados", "delta_rollos", "pct_rollos_carg"]
        ]
        gc_r = gc_r[(gc_r["rollos_producidos"] > 0) | (gc_r["rollos_cargados"] > 0)]
        if gc_r.empty:
            st.info("No hay datos de rollos para los campos seleccionados.")
        else:
            fig_gr = px.bar(
                gc_r.melt(
                    id_vars="campo",
                    value_vars=["rollos_producidos", "rollos_cargados"],
                    var_name="tipo", value_name="rollos",
                ).replace({
                    "rollos_producidos": "Producidos (Plan.)",
                    "rollos_cargados":   "Cargados (Remitos)",
                }),
                x="campo", y="rollos", color="tipo", barmode="group",
                labels={"rollos": "Rollos", "campo": "", "tipo": ""},
                color_discrete_map={
                    "Producidos (Plan.)":  "#aed6f1",
                    "Cargados (Remitos)": "#2ecc71",
                },
                text_auto=True,
                height=360,
            )
            fig_gr.update_layout(
                margin=dict(l=0, r=0, t=10, b=40), legend_title="",
                xaxis_tickangle=-30,
                plot_bgcolor="rgba(0,0,0,0)", paper_bgcolor="rgba(0,0,0,0)",
            )
            st.plotly_chart(fig_gr, use_container_width=True)
            st.divider()

            disp_r = gc_r.rename(columns={
                "campo":             "Campo",
                "rollos_producidos": "Producidos (Plan.)",
                "rollos_cargados":   "Cargados (Remitos)",
                "delta_rollos":      "Diferencia",
                "pct_rollos_carg":   "% Cargado",
            })
            disp_r_tot = totales_row(disp_r, "Campo")
            n_r = len(disp_r)
            st.dataframe(
                style_total_row(
                    disp_r_tot.style.format(fmt_num(disp_r_tot)),
                    n_r,
                ),
                use_container_width=True, hide_index=True,
            )
            download_btn(disp_r, "cruce_rollos.xlsx")

with sub_fechas:
    if sisa.empty or rem.empty:
        st.info("Se necesitan datos de ambas fuentes para el cruce de fechas.")
    else:
        gf = cruce_fechas(sisa, rem)
        if gf.empty:
            st.info("No hay columnas de fecha de cosecha en la planificación.")
        else:
            import pandas as pd
            gantt_df = gf.dropna(subset=["primera_cosecha", "ultimo_remito"]).rename(columns={
                "campo":          "Campo",
                "primera_cosecha":"Inicio",
                "ultimo_remito":  "Fin",
            })
            if not gantt_df.empty:
                fig_gf = px.timeline(
                    gantt_df,
                    x_start="Inicio", x_end="Fin", y="Campo",
                    color="Campo",
                    color_discrete_sequence=px.colors.qualitative.Set2,
                    height=max(300, len(gantt_df) * 40 + 80),
                )
                fig_gf.update_layout(
                    showlegend=False,
                    margin=dict(l=0, r=0, t=10, b=0),
                    plot_bgcolor="rgba(0,0,0,0)", paper_bgcolor="rgba(0,0,0,0)",
                )
                st.plotly_chart(fig_gf, use_container_width=True)
                st.divider()

            import pandas as pd
            gf_disp = gf.copy()
            for col in ["primera_cosecha", "ultima_cosecha", "primer_remito", "ultimo_remito"]:
                if col in gf_disp.columns:
                    gf_disp[col] = gf_disp[col].dt.strftime("%d/%m/%Y").where(gf_disp[col].notna(), "—")
            for col in ["cant_remitos", "dias_cosecha_remito", "duracion_total_dias"]:
                if col in gf_disp.columns:
                    gf_disp[col] = gf_disp[col].apply(
                        lambda v: "—" if pd.isna(v) else f"{int(v):,}"
                    )
            rename_f = {
                "campo":               "Campo",
                "primera_cosecha":     "1ra Cosecha (Plan.)",
                "ultima_cosecha":      "Últ Cosecha (Plan.)",
                "primer_remito":       "1er Remito",
                "ultimo_remito":       "Últ Remito",
                "cant_remitos":        "N° Remitos",
                "dias_cosecha_remito": "Días 1ra Cos → 1er Rem",
                "duracion_total_dias": "Duración Total (días)",
            }
            disp_f = gf_disp.rename(columns=rename_f)[[v for k, v in rename_f.items() if k in gf_disp.columns]]
            st.dataframe(disp_f, use_container_width=True, hide_index=True)
            download_btn(gf_disp.rename(columns=rename_f), "cruce_fechas.xlsx")

with sub_desm:
    st.subheader("Logística por desmotadora")
    disp_desm = vd.rename(columns={
        "desmotadora":    "Desmotadora",
        "empresa":        "Empresa",
        "establecimiento":"Campo",
        "entrega_kg":     "Entregado (kg)",
        "fibra_kg":       "Fibra (kg)",
        "rinde_desmote":  "Rinde (%)",
        "fardos":         "Fardos",
        "ppf_kg":         "PP Fardo (kg)",
    })[["Desmotadora", "Empresa", "Campo", "Entregado (kg)", "Fibra (kg)",
        "Rinde (%)", "Fardos", "PP Fardo (kg)"]]
    st.dataframe(
        disp_desm.style
            .format(fmt_num(disp_desm), na_rep="—")
            .map(sem_rinde, subset=["Rinde (%)"]),
        use_container_width=True,
        hide_index=True,
    )
    download_btn(disp_desm, "logistica_desmotadora.xlsx")
