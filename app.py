import streamlit as st
import pandas as pd
import plotly.express as px
import datetime

from utils import (
    inject_css, load_data, sidebar_filters,
    resumen_cruzado, agg_campo_sisa, agg_campo_rem, agg_desmotadora,
    sup_lote, totales_row, style_total_row, fmt_num, download_btn,
    sem_avance, sem_desvio, sem_rinde, sem_en_est, sem_avance_entrega,
)

st.set_page_config(
    page_title="Cosecha Algodón — Duhau",
    page_icon="🌿",
    layout="wide",
)

inject_css()

# ── header ────────────────────────────────────────────────────────────────────

col_btn, col_ts = st.columns([1, 9])
with col_btn:
    if st.button("↺ Actualizar"):
        st.cache_data.clear()
        st.session_state.pop("last_update", None)
        st.rerun()

# ── data load ─────────────────────────────────────────────────────────────────

raw_rem, raw_sisa, rem_error, sisa_error = load_data()

if "last_update" not in st.session_state:
    st.session_state.last_update = datetime.datetime.now().strftime("%d/%m/%Y %H:%M")

ultimo_remito = (
    raw_rem["fecha"].max().strftime("%d/%m/%Y")
    if raw_rem is not None and not raw_rem["fecha"].isna().all()
    else "—"
)

with col_ts:
    st.markdown(
        f"""
        <div style="
            background: linear-gradient(135deg, #1a5c2a 0%, #27ae60 60%, #2ecc71 100%);
            border-radius: 14px;
            padding: 18px 28px;
            display: flex;
            justify-content: space-between;
            align-items: center;
            box-shadow: 0 4px 20px rgba(46,204,113,0.25);
        ">
            <div>
                <div style="color:white;font-size:1.55rem;font-weight:900;letter-spacing:-0.02em;line-height:1.1">
                    🌿 Control de Cosecha de Algodón
                </div>
                <div style="color:rgba(255,255,255,0.82);font-size:0.85rem;margin-top:4px">
                    Grupo Duhau · Campaña 2025/26 · Finnegans API
                </div>
            </div>
            <div style="text-align:right;color:rgba(255,255,255,0.75);font-size:0.78rem;line-height:1.7">
                <div>Actualizado: <b style="color:white">{st.session_state.last_update}</b></div>
                <div>Último remito: <b style="color:white">{ultimo_remito}</b></div>
                <div style="font-size:0.70rem">↺ usá el botón para actualizar</div>
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )

st.markdown("<div style='margin-top:8px'></div>", unsafe_allow_html=True)

if sisa_error:
    st.warning(f"⚠️ Planificación no disponible: {sisa_error}")
if rem_error:
    st.warning(f"⚠️ Remitos no disponibles: {rem_error}")

# ── sidebar filters ───────────────────────────────────────────────────────────

sisa, rem = sidebar_filters(raw_rem, raw_sisa)

# ── pre-compute ───────────────────────────────────────────────────────────────

if not rem.empty:
    sup          = sup_lote(rem)
    vc           = agg_campo_rem(rem, sup)
    vd           = agg_desmotadora(rem)
    fibra_total  = rem["cantidadproducidakilos"].sum()
    consumo_total= rem["cantidadconsumo"].sum()
    rd_total     = fibra_total / consumo_total * 100 if consumo_total > 0 else 0

# ═══════════════════════════════════════════════════════════════════════════════
# RESUMEN GENERAL
# ═══════════════════════════════════════════════════════════════════════════════

st.header("Resumen General")

if not sisa.empty:
    rc = resumen_cruzado(sisa, rem)

    tot_semb      = rc["sup_sembrada"].sum()
    tot_cos       = rc["sup_cosechada"].sum()
    pct_cos       = tot_cos / tot_semb * 100 if tot_semb > 0 else 0
    tot_plan      = rc["tn_planificadas"].sum()
    tot_prod      = rc["tn_producidas"].sum()
    tot_entreg    = rc["entregado_tn"].sum()
    tot_en_est    = rc["en_establecimiento"].sum()
    tot_desmotado = rc["tn_desmotadas"].sum()
    pct_entrega   = tot_entreg / tot_prod * 100 if tot_prod > 0 else 0

    rinde_plan  = tot_plan / tot_semb if tot_semb > 0 else 0
    rinde_obt   = tot_prod / tot_cos  if tot_cos  > 0 else 0
    rinde_dev   = (rinde_obt - rinde_plan) / rinde_plan * 100 if rinde_plan > 0 else 0
    pct_desmot  = tot_desmotado / tot_entreg * 100 if tot_entreg > 0 else 0
    fibra_tn    = fibra_total / 1000 if not rem.empty else 0
    fardos_n    = int(rem["cantidadproducidafardos"].sum()) if not rem.empty else 0
    rd          = rd_total if not rem.empty else 0
    rinde_color = "#00a651" if rd >= 28 else ("#d97706" if rd >= 24 else "#ea001d")
    dev_class   = "kf-dev-up" if rinde_dev >= 0 else "kf-dev-down"
    dev_arrow   = "▲" if rinde_dev >= 0 else "▼"

    st.markdown(f"""
<style>
.kpi-flow {{
  display: flex; align-items: stretch; gap: 0; margin: 16px 0 24px;
}}
.kf-station {{
  flex: 1; background: white; border: 1px solid #e5e5e5;
  border-top: 3px solid transparent; border-radius: 12px;
  padding: 20px; display: flex; flex-direction: column; gap: 14px;
  box-shadow: 0 2px 2px rgba(0,0,0,0.04);
}}
.kf-station:hover {{ box-shadow: 0 4px 16px rgba(0,0,0,0.10); }}
.kf-plan      {{ border-top-color: #006bff; }}
.kf-harvest   {{ border-top-color: #00a651; }}
.kf-logistics {{ border-top-color: #d97706; }}
.kf-fiber     {{ border-top-color: #7c3aed; }}
.kf-header {{ display: flex; align-items: center; gap: 10px; }}
.kf-icon {{
  width: 28px; height: 28px; border-radius: 6px;
  display: flex; align-items: center; justify-content: center;
  font-size: 14px; flex-shrink: 0;
}}
.kf-plan      .kf-icon {{ background: #e6f0ff; }}
.kf-harvest   .kf-icon {{ background: #e6f7ee; }}
.kf-logistics .kf-icon {{ background: #fff6e0; }}
.kf-fiber     .kf-icon {{ background: #f0e8ff; }}
.kf-title {{ font-size: 11px; font-weight: 600; text-transform: uppercase; letter-spacing: 0.08em; color: #6b6b6b; }}
.kf-divider {{ height: 1px; background: #f2f2f2; }}
.kf-list {{ display: flex; flex-direction: column; gap: 14px; }}
.kf-item {{ display: flex; flex-direction: column; gap: 3px; }}
.kf-label {{ font-size: 11px; font-weight: 500; color: #a8a8a8; letter-spacing: 0.01em; }}
.kf-value-row {{ display: flex; align-items: baseline; gap: 4px; }}
.kf-value {{ font-size: 26px; font-weight: 600; color: #171717; letter-spacing: -1px; line-height: 1; }}
.kf-unit {{ font-size: 13px; color: #a8a8a8; }}
.kf-dev {{
  display: inline-flex; align-items: center; gap: 3px;
  font-size: 11px; font-weight: 600; padding: 2px 7px;
  border-radius: 9999px; width: fit-content; margin-top: 2px;
}}
.kf-dev-up   {{ background: #e6f7ee; color: #00a651; }}
.kf-dev-down {{ background: #ffeaea; color: #ea001d; }}
.kf-arrow {{
  display: flex; flex-direction: column; align-items: center;
  justify-content: center; gap: 6px; width: 72px; flex-shrink: 0; padding: 0 2px;
}}
.kf-arrow-badge {{
  background: #171717; color: white; font-size: 13px; font-weight: 600;
  padding: 4px 10px; border-radius: 9999px; white-space: nowrap;
  box-shadow: 0 1px 4px rgba(0,0,0,0.18);
}}
.kf-arrow-track {{ display: flex; align-items: center; width: 100%; }}
.kf-line {{ flex: 1; height: 1.5px; background: #e5e5e5; }}
.kf-chevron {{ color: #a8a8a8; font-size: 14px; line-height: 1; }}
.kf-arrow-label {{ font-size: 10px; color: #a8a8a8; font-weight: 500; text-align: center; line-height: 1.3; }}
</style>
<div class="kpi-flow">

  <div class="kf-station kf-plan">
    <div class="kf-header"><div class="kf-icon">📋</div><span class="kf-title">Planificado</span></div>
    <div class="kf-divider"></div>
    <div class="kf-list">
      <div class="kf-item">
        <span class="kf-label">Hectáreas sembradas</span>
        <div class="kf-value-row"><span class="kf-value">{tot_semb:,.0f}</span><span class="kf-unit">ha</span></div>
      </div>
      <div class="kf-item">
        <span class="kf-label">Rinde bruto planificado</span>
        <div class="kf-value-row"><span class="kf-value">{rinde_plan:,.2f}</span><span class="kf-unit">tn/ha</span></div>
      </div>
      <div class="kf-item">
        <span class="kf-label">Toneladas brutas planificadas</span>
        <div class="kf-value-row"><span class="kf-value">{tot_plan:,.0f}</span><span class="kf-unit">tn</span></div>
      </div>
    </div>
  </div>

  <div class="kf-arrow">
    <div class="kf-arrow-badge">{pct_cos:.0f}%</div>
    <div class="kf-arrow-track"><div class="kf-line"></div><span class="kf-chevron">›</span></div>
    <div class="kf-arrow-label">avance<br>cosecha</div>
  </div>

  <div class="kf-station kf-harvest">
    <div class="kf-header"><div class="kf-icon">🌾</div><span class="kf-title">Producción</span></div>
    <div class="kf-divider"></div>
    <div class="kf-list">
      <div class="kf-item">
        <span class="kf-label">Hectáreas cosechadas</span>
        <div class="kf-value-row"><span class="kf-value">{tot_cos:,.0f}</span><span class="kf-unit">ha</span></div>
      </div>
      <div class="kf-item">
        <span class="kf-label">Rinde parcial</span>
        <div class="kf-value-row"><span class="kf-value">{rinde_obt:,.2f}</span><span class="kf-unit">tn/ha</span></div>
        <span class="kf-dev {dev_class}">{dev_arrow} {abs(rinde_dev):.1f}% vs plan</span>
      </div>
      <div class="kf-item">
        <span class="kf-label">Toneladas brutas producidas</span>
        <div class="kf-value-row"><span class="kf-value">{tot_prod:,.0f}</span><span class="kf-unit">tn</span></div>
      </div>
    </div>
  </div>

  <div class="kf-arrow">
    <div class="kf-arrow-badge">{pct_entrega:.0f}%</div>
    <div class="kf-arrow-track"><div class="kf-line"></div><span class="kf-chevron">›</span></div>
    <div class="kf-arrow-label">entregado<br>a desmot.</div>
  </div>

  <div class="kf-station kf-logistics">
    <div class="kf-header"><div class="kf-icon">🚛</div><span class="kf-title">Logística</span></div>
    <div class="kf-divider"></div>
    <div class="kf-list">
      <div class="kf-item">
        <span class="kf-label">Tn brutas en establecimiento</span>
        <div class="kf-value-row"><span class="kf-value">{tot_en_est:,.1f}</span><span class="kf-unit">tn</span></div>
      </div>
      <div class="kf-item">
        <span class="kf-label">Tn entregadas a desmotadora</span>
        <div class="kf-value-row"><span class="kf-value">{tot_entreg:,.1f}</span><span class="kf-unit">tn</span></div>
      </div>
    </div>
  </div>

  <div class="kf-arrow">
    <div class="kf-arrow-badge">{pct_desmot:.0f}%</div>
    <div class="kf-arrow-track"><div class="kf-line"></div><span class="kf-chevron">›</span></div>
    <div class="kf-arrow-label">bruto<br>desmotado</div>
  </div>

  <div class="kf-station kf-fiber">
    <div class="kf-header"><div class="kf-icon">🧵</div><span class="kf-title">Desmote</span></div>
    <div class="kf-divider"></div>
    <div class="kf-list">
      <div class="kf-item">
        <span class="kf-label">Tn brutas desmotadas</span>
        <div class="kf-value-row"><span class="kf-value">{tot_desmotado:,.1f}</span><span class="kf-unit">tn</span></div>
      </div>
      <div class="kf-item">
        <span class="kf-label">Rinde de fibra</span>
        <div class="kf-value-row"><span class="kf-value" style="color:{rinde_color}">{rd:.1f}</span><span class="kf-unit">%</span></div>
      </div>
      <div class="kf-item">
        <span class="kf-label">Toneladas de fibra</span>
        <div class="kf-value-row"><span class="kf-value">{fibra_tn:,.1f}</span><span class="kf-unit">tn</span></div>
      </div>
      <div class="kf-item">
        <span class="kf-label">Fardos de fibra</span>
        <div class="kf-value-row"><span class="kf-value">{fardos_n:,}</span><span class="kf-unit">fardos</span></div>
      </div>
    </div>
  </div>

</div>
""", unsafe_allow_html=True)

    rc_melt = rc[["campo", "entregado_tn", "en_establecimiento"]].melt(
        id_vars="campo",
        value_vars=["entregado_tn", "en_establecimiento"],
        var_name="estado", value_name="tn",
    ).replace({
        "entregado_tn":       "Entregado a Desm.",
        "en_establecimiento": "En Establecimiento",
    })
    fig_rc = px.bar(
        rc_melt,
        x="campo", y="tn", color="estado", barmode="stack",
        labels={"tn": "Tn", "campo": "", "estado": ""},
        color_discrete_map={
            "Entregado a Desm.":  "#2ecc71",
            "En Establecimiento": "#f39c12",
        },
    )
    fig_rc.add_scatter(
        x=rc["campo"], y=rc["tn_planificadas"],
        mode="markers", name="Planificado",
        marker=dict(symbol="diamond", size=12, color="#2980b9",
                    line=dict(width=1, color="#1a5276")),
    )
    fig_rc.update_layout(
        height=380, margin=dict(l=0, r=0, t=10, b=40),
        legend_title="", xaxis_tickangle=-30,
    )
    st.plotly_chart(fig_rc, use_container_width=True)

    st.divider()

    disp_rc = rc.rename(columns={
        "campo":              "Campo",
        "sup_sembrada":       "Sup Semb ha",
        "sup_cosechada":      "Sup Cos ha",
        "pct_cosechado":      "% Cosechado",
        "tn_planificadas":    "Tn Plan",
        "tn_producidas":      "Tn Prod",
        "cumpl_plan_pct":     "% vs Plan",
        "entregado_tn":       "Entregado Tn",
        "avance_entrega_pct": "% Entregado",
        "en_establecimiento": "En Estab. Tn",
        "tn_desmotadas":      "Tn Desmotadas",
    })
    disp_rc_tot = totales_row(disp_rc, "Campo")
    n = len(disp_rc)
    st.dataframe(
        style_total_row(
            disp_rc_tot.style
                .format(fmt_num(disp_rc_tot), na_rep="—")
                .map(sem_en_est,        subset=["En Estab. Tn"])
                .map(sem_avance_entrega, subset=["% Entregado"])
                .map(sem_avance,        subset=["% Cosechado"]),
            n,
        ),
        use_container_width=True,
        hide_index=True,
    )
    download_btn(disp_rc, "resumen_general.xlsx")

else:
    st.info("Sin datos de planificación para los filtros seleccionados.")

st.divider()

# ═══════════════════════════════════════════════════════════════════════════════
# TABS: PRODUCCIÓN · LOGÍSTICA · DESMOTE  (resumen — 1 gráfico + 1 tabla c/u)
# ═══════════════════════════════════════════════════════════════════════════════

tab_prod, tab_log, tab_desm = st.tabs(["🌱 Producción", "🚚 Logística", "🏭 Desmote"])

# ── TAB PRODUCCIÓN ────────────────────────────────────────────────────────────

with tab_prod:
    if sisa.empty:
        st.warning("Sin datos de planificación para los filtros seleccionados.")
    else:
        vc_sisa = agg_campo_sisa(sisa)

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

        st.subheader("Planificado vs Real por campo")
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

    st.divider()
    st.page_link("pages/1_Produccion.py", label="Ver detalle completo de Producción →", icon="🌱")

# ── TAB LOGÍSTICA ─────────────────────────────────────────────────────────────

with tab_log:
    if rem.empty:
        st.info("Sin remitos para los filtros seleccionados.")
    else:
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

    st.divider()
    st.page_link("pages/2_Logistica.py", label="Ver detalle completo de Logística →", icon="🚚")

# ── TAB DESMOTE ───────────────────────────────────────────────────────────────

with tab_desm:
    if rem.empty:
        st.info("Sin remitos para los filtros seleccionados.")
    else:
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
    st.page_link("pages/3_Desmote.py", label="Ver detalle completo de Desmote →", icon="🏭")

# ── footer ────────────────────────────────────────────────────────────────────
st.divider()
st.caption(
    f"Actualizado: {st.session_state.last_update} · "
    f"Economart / Grupo Duhau"
)
