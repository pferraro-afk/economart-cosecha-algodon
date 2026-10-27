import streamlit as st
import pandas as pd
import plotly.express as px

from utils import (
    inject_css, load_data, sidebar_filters,
    resumen_cruzado, download_btn, render_cosecha_html,
)

inject_css()

# ── header ────────────────────────────────────────────────────────────────────

col_btn, col_ts = st.columns([1, 9])
with col_btn:
    if st.button("↺ Actualizar"):
        st.cache_data.clear()
        st.rerun()

# ── data load ─────────────────────────────────────────────────────────────────

raw_rem, raw_sisa, rem_error, sisa_error = load_data()

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

    rinde_plan       = tot_plan / tot_semb if tot_semb > 0 else 0
    rinde_obt        = tot_prod / tot_cos  if tot_cos  > 0 else 0
    rinde_dev        = (rinde_obt - rinde_plan) / rinde_plan * 100 if rinde_plan > 0 else 0
    pct_desmot       = tot_desmotado / tot_entreg * 100 if tot_entreg > 0 else 0
    fibra_tn         = fibra_total / 1000 if not rem.empty else 0
    rinde_fibra_tnha = fibra_tn / tot_semb if tot_semb > 0 else 0
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
        <span class="kf-label">Rinde fibra parcial</span>
        <div class="kf-value-row"><span class="kf-value">{rinde_fibra_tnha:.3f}</span><span class="kf-unit">tn/ha</span></div>
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

    rc = rc.sort_values("tn_planificadas", ascending=False)

    rc_melt = rc[["campo", "entregado_tn", "en_establecimiento"]].melt(
        id_vars="campo",
        value_vars=["entregado_tn", "en_establecimiento"],
        var_name="estado", value_name="tn",
    ).replace({
        "entregado_tn":       "Entregado a Desm.",
        "en_establecimiento": "En Establecimiento",
    })
    orden_campos = rc["campo"].tolist()

    tick_labels = []
    for _, row in rc.iterrows():
        rr = row.get("rinde_obt_kgha")
        ro = row.get("rinde_plan_kgha")
        rr_str = f"{rr:,.0f}" if (rr is not None and not pd.isna(rr)) else "—"
        if ro is not None and not pd.isna(ro) and ro > 0 and rr is not None and not pd.isna(rr):
            var = (rr - ro) / ro * 100
            sign = "+" if var >= 0 else ""
            sub = f"<br><sub style='font-size:10px;color:#888'>{rr_str} kg/ha ({sign}{var:.0f}% vs RO)</sub>"
        else:
            sub = f"<br><sub style='font-size:10px;color:#888'>{rr_str} kg/ha</sub>"
        tick_labels.append(row["campo"] + sub)

    fig_rc = px.bar(
        rc_melt,
        x="campo", y="tn", color="estado", barmode="stack",
        labels={"tn": "Tn", "campo": "", "estado": ""},
        color_discrete_map={
            "Entregado a Desm.":  "#2ecc71",
            "En Establecimiento": "#f39c12",
        },
        category_orders={"campo": orden_campos},
    )
    fig_rc.add_scatter(
        x=rc["campo"], y=rc["tn_planificadas"],
        mode="markers", name="Planificado",
        marker=dict(symbol="diamond", size=12, color="#2980b9",
                    line=dict(width=1, color="#1a5276")),
    )
    for _, row in rc.iterrows():
        pct = row.get("pct_cosechado")
        if pct is not None and not pd.isna(pct):
            fig_rc.add_annotation(
                x=row["campo"],
                y=row["tn_producidas"],
                text=f"🌾 {pct:.0f}%",
                showarrow=False,
                yshift=12,
                font=dict(size=11, color="#1a5c2a", family="system-ui"),
            )
    fig_rc.update_layout(
        height=400, margin=dict(l=0, r=0, t=30, b=80),
        legend_title="", xaxis_tickangle=-30,
    )
    fig_rc.update_xaxes(
        tickmode="array",
        tickvals=orden_campos,
        ticktext=tick_labels,
    )
    st.plotly_chart(fig_rc, use_container_width=True)

    st.divider()

    rows_html = []
    for _, row in rc.iterrows():
        rows_html.append({
            "campo":             row["campo"],
            "sup_sembrada":      row.get("sup_sembrada"),
            "sup_cosechada":     row.get("sup_cosechada"),
            "pct_cosechado":     row.get("pct_cosechado"),
            "rinde_plan_kgha":   row.get("rinde_plan_kgha"),
            "rinde_obt_kgha":    row.get("rinde_obt_kgha"),
            "var_rinde_pct":     row.get("var_rinde_pct"),
            "rinde_desmote_pct": row.get("rinde_desmote_pct"),
            "rinde_neto_kgha":   row.get("rinde_neto_kgha"),
        })
    _ts  = rc["sup_sembrada"].sum()
    _tc  = rc["sup_cosechada"].sum()
    _tp  = rc["tn_planificadas"].sum()
    _tprod = rc["tn_producidas"].sum()
    _tdesm = rc["tn_desmotadas"].sum()
    _tfibn = rc["fibra_tn"].sum() if "fibra_tn" in rc.columns else 0
    _tplan_sup = rc["sup_planificada"].sum() if "sup_planificada" in rc.columns else 0
    _ro_tot = _tp * 1000 / _tplan_sup if _tplan_sup > 0 else None
    _rr_tot = _tprod * 1000 / _ts if _ts > 0 else None
    _var_tot = (_rr_tot - _ro_tot) / _ro_tot * 100 if (_ro_tot and _ro_tot > 0 and _rr_tot is not None) else None
    rows_html.append({
        "campo":             "TOTAL",
        "sup_sembrada":      _ts,
        "sup_cosechada":     _tc,
        "pct_cosechado":     _tc / _ts * 100 if _ts > 0 else None,
        "rinde_plan_kgha":   _ro_tot,
        "rinde_obt_kgha":    _rr_tot,
        "var_rinde_pct":     _var_tot,
        "rinde_desmote_pct": _tfibn / _tdesm * 100 if _tdesm > 0 else None,
        "rinde_neto_kgha":   _tdesm * 1000 / _ts if _ts > 0 else None,
    })
    st.markdown(render_cosecha_html(rows_html), unsafe_allow_html=True)
    download_btn(rc[["campo", "sup_sembrada", "sup_cosechada", "pct_cosechado",
                      "tn_planificadas", "tn_producidas", "entregado_tn",
                      "tn_desmotadas", "rinde_plan_kgha", "rinde_obt_kgha",
                      "var_rinde_pct", "rinde_desmote_pct", "rinde_neto_kgha"]],
                 "resumen_general.xlsx")

else:
    st.info("Sin datos de planificación para los filtros seleccionados.")

# ── footer ────────────────────────────────────────────────────────────────────
st.divider()
st.caption(
    f"Actualizado: {st.session_state.last_update} · "
    f"Economart / Grupo Duhau"
)
