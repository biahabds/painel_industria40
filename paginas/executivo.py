import plotly.graph_objects as go
import streamlit as st

from core import dados, kpis, ui


def render(ctx):
    ui.cabecalho("🏭 Visão geral executiva",
                 "Resumo do período selecionado para a direção da indústria")
    maqs = dados.maquinas()
    prod = dados.producao(ctx)
    vend = dados.vendas(ctx)
    ultima = dados.telemetria_ultima(ctx)
    desg = dados.desgaste_atual(ctx)
    k = kpis.kpis_executivos(prod, vend, maqs, ultima, desg)

    c = st.columns(4)
    c[0].metric("Quantidade produzida", ui.fint(k["produzido"]),
                help="Soma de qty_produced (production_events) no período")
    c[1].metric("Produtos rejeitados", ui.fint(k["rejeitado"]),
                help="Soma de qty_rejected no período")
    c[2].metric("Taxa de rejeição", ui.fpct(k["taxa_rejeicao"], 2),
                help="Rejeitados ÷ produzidos")
    c[3].metric("Pedidos de venda", ui.fint(k["pedidos"]),
                help=f"Todos os status; {ui.fint(k['pedidos_validos'])} não cancelados")
    c = st.columns(4)
    c[0].metric("Faturamento total", ui.fbrl(k["faturamento"]),
                help="Soma de total_amount dos pedidos não cancelados")
    c[1].metric("Máquinas monitoradas", ui.fint(k["maquinas"]))
    c[2].metric("Máquinas em atenção/crítica", ui.fint(k["maquinas_alerta"]),
                delta=f"{k['maquinas_criticas']} crítica(s)" if k["maquinas_criticas"] else None,
                delta_color="inverse",
                help="Status da leitura de telemetria mais recente de cada máquina")
    c[3].metric("Componentes com desgaste elevado", ui.fint(k["componentes_alerta"]),
                delta=f"{k['componentes_criticos']} acima de 90%" if k["componentes_criticos"] else None,
                delta_color="inverse", help="parts_wear com wear_pct ≥ 75%")

    st.markdown("#### 🚦 Situação atual das máquinas")
    if ultima.empty:
        ui.sem_dados("Sem telemetria disponível.")
    else:
        cols = st.columns(max(1, len(ultima)))
        for col, (_, r) in zip(cols, ultima.sort_values("machine_code").iterrows()):
            classe = {"CRITICO": "card-alerta", "ATENCAO": "card-atencao"}.get(r["machine_status"], "card-ok")
            col.markdown(
                f'<div class="{classe}"><b>{r["machine_code"]}</b> {ui.badge(r["machine_status"])}<br>'
                f'<span class="nota">🌡️ {ui.fnum(r["temperature_c"])} °C · 〰️ {ui.fnum(r["vibration_mm_s"], 2)} mm/s'
                f' · ⚡ {ui.fnum(r["energy_kw"])} kW</span></div>', unsafe_allow_html=True)

    alertas = desg[desg["situacao"] != "NORMAL"] if not desg.empty else desg
    if not alertas.empty:
        st.markdown("#### 🔔 Componentes que exigem atenção")
        for _, r in alertas.iterrows():
            classe = "card-alerta" if r["situacao"] == "CRÍTICO" else "card-atencao"
            st.markdown(f'<div class="{classe}">{ui.badge(r["situacao"])} <b>{r["componente"]}</b> — '
                        f'desgaste {ui.fnum(r["wear_pct"])}% · ~{ui.fint(r["estimated_remaining_hours"])} h '
                        f'restantes</div>', unsafe_allow_html=True)

    st.markdown("#### 📈 Evolução no período")
    if prod.empty and vend.empty:
        ui.sem_dados()
        return
    sp = kpis.serie_temporal(prod, "ended_at", {"aprovado": ("qty_approved", "sum"),
                                                "rejeitado": ("qty_rejected", "sum")}, ctx.freq_pandas)
    sv = kpis.serie_temporal(vend, "created_at", {"faturamento": ("receita_valida", "sum")},
                             ctx.freq_pandas)
    fig = go.Figure()
    if not sp.empty:
        fig.add_bar(x=sp["ended_at"], y=sp["aprovado"], name="Aprovado", marker_color=ui.COR["secundaria"])
        fig.add_bar(x=sp["ended_at"], y=sp["rejeitado"], name="Rejeitado", marker_color=ui.COR["critico"])
    if not sv.empty:
        fig.add_scatter(x=sv["created_at"], y=sv["faturamento"], name="Faturamento (R$)", yaxis="y2",
                        mode="lines+markers", line=dict(color=ui.COR["primaria"], width=3))
    fig.update_layout(barmode="stack", title="Produção (unidades) e faturamento (R$)",
                      yaxis=dict(title="Unidades"),
                      yaxis2=dict(title="R$", overlaying="y", side="right", showgrid=False),
                      legend=dict(orientation="h", y=1.12))
    ui.grafico(fig, 380)
