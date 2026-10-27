import streamlit as st
import pandas as pd
import plotly.express as px

from utils import (
    inject_css, load_data, sidebar_filters,
    agg_desmotadora, agg_semanal, cruce_campo, cruce_lote, cruce_fechas,
    totales_row, style_total_row, fmt_num, download_btn,
    kpi_card, sem_avance, sem_avance_entrega,
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

vd   = agg_desmotadora(rem)
vsem = agg_semanal(rem)
gc   = cruce_campo(sisa, rem) if not sisa.empty else None

bruto_total      = rem["cantidad"].sum()
sin_desmotar_tot = vd["stock_sin_desmotar"].sum()

# ── KPIs ─────────────────────────────────────────────────────────────────────

c1, c2, c3, c4, c5 = st.columns(5)
if gc is not None:
    tot_prod_c   = gc["tn_producidas"].sum()
    tot_entr_c   = gc["bruto_tn"].sum()
    tot_en_est_c = gc["en_estab_tn"].sum()
    pct_entr_c   = tot_entr_c / tot_prod_c * 100 if tot_prod_c > 0 else 0
    c1.markdown(kpi_card("Tn Producidas (Plan.)", f"{tot_prod_c:,.1f}"), unsafe_allow_html=True)
    c2.markdown(kpi_card("Entregado a Desm.", f"{tot_entr_c:,.1f} Tn",
        delta=f"{pct_entr_c:.0f}% entregado", delta_color="off"), unsafe_allow_html=True)
    c3.markdown(kpi_card("En el Campo", f"{tot_en_est_c:,.1f} Tn"), unsafe_allow_html=True)
else:
    c1.markdown(kpi_card("Tn Producidas (Plan.)", "—"), unsafe_allow_html=True)
    c2.markdown(kpi_card("Entregado a Desm.", f"{bruto_total / 1000:,.1f} Tn"), unsafe_allow_html=True)
    c3.markdown(kpi_card("En el Campo", "—"), unsafe_allow_html=True)
c4.markdown(kpi_card("Sin Desmotar en Desm.", f"{sin_desmotar_tot / 1000:,.1f} Tn"), unsafe_allow_html=True)
c5.markdown(kpi_card("Remitos", str(len(rem))), unsafe_allow_html=True)

st.divider()

# ── Gráficos ──────────────────────────────────────────────────────────────────

col_g1, col_g2 = st.columns(2)

with col_g1:
    st.subheader("Entregado vs en el campo (Tn)")
    if gc is None:
        st.info("Sin datos de planificación para los filtros seleccionados.")
    else:
        fig_gc = px.bar(
            gc.melt(
                id_vars="campo",
                value_vars=["bruto_tn", "en_estab_tn"],
                var_name="origen", value_name="tn",
            ).replace({
                "bruto_tn":    "Entregado (Remitos)",
                "en_estab_tn": "En el Campo",
            }),
            x="campo", y="tn", color="origen", barmode="stack",
            labels={"tn": "Tn", "campo": "", "origen": ""},
            color_discrete_map={
                "Entregado (Remitos)": "#2ecc71",
                "En el Campo":         "#f39c12",
            },
            height=420,
        )
        fig_gc.update_layout(
            margin=dict(l=0, r=0, t=10, b=40), legend_title="",
            xaxis_tickangle=-30,
            plot_bgcolor="rgba(0,0,0,0)", paper_bgcolor="rgba(0,0,0,0)",
        )
        st.plotly_chart(fig_gc, use_container_width=True)

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

# ── Sub-tabs: Campo · Lote · Rollos · Fechas ──────────────────────────────────

sub_campo, sub_lote, sub_rollos, sub_fechas = st.tabs(["Por Campo", "Por Lote", "Rollos", "Fechas"])

with sub_campo:
    if gc is None:
        st.info("Sin datos de planificación para los filtros seleccionados.")
    else:
        cols_disp = {
            "campo":            "Campo",
            "tn_planificadas":  "Tn Plan",
            "tn_producidas":    "Tn Prod (Plan.)",
            "cumpl_plan_pct":   "% vs Plan",
            "avance_cos_pct":   "Avance Cos %",
            "bruto_tn":         "Entregado Tn",
            "pct_entregado":    "% Entregado",
            "en_estab_tn":      "En Campo Tn",
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
    if sisa.empty:
        st.info("Sin datos de planificación para los filtros seleccionados.")
    else:
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

with sub_rollos:
    if gc is None:
        st.info("Sin datos de planificación para los filtros seleccionados.")
    else:
        gc_r = gc[
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
    if sisa.empty:
        st.info("Se necesitan datos de ambas fuentes para el cruce de fechas.")
    else:
        gf = cruce_fechas(sisa, rem)
        if gf.empty:
            st.info("No hay columnas de fecha de cosecha en la planificación.")
        else:
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
