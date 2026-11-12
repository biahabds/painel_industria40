import plotly.graph_objects as go
import streamlit as st

from core import dados, kpis, ui


def render(ctx):
    ui.cabecalho("Visão geral executiva",
                 "Resumo do período selecionado para a direção da indústria")
    maqs = dados.maquinas()
    prod = dados.producao(ctx)
    vend = dados.vendas(ctx)
    ultima = dados.telemetria_ultima(ctx)
    desg = dados.desgaste_atual(ctx)
    k = kpis.kpis_executivos(prod, vend, maqs, ultima, desg)

    st_ = ui.STATUS
    c = st.columns(4, gap="small")
    ui.kpi(c[0], "factory", "Produção total", ui.fcurto(k["produzido"]) + " un.",
           f"{ui.fint(k['produzido'])} unidades")
    ui.kpi(c[1], "block", "Rejeitados", ui.fcurto(k["rejeitado"]) + " un.",
           f"{ui.fint(k['rejeitado'])} unidades", st_["critico"])
    ui.kpi(c[2], "trending_down", "Taxa de rejeição", ui.fpct(k["taxa_rejeicao"], 2),
           "rejeitados ÷ produzidos",
           st_["critico"] if k["taxa_rejeicao"] and k["taxa_rejeicao"] > 0.05 else st_["atencao"])
    ui.kpi(c[3], "receipt_long", "Pedidos", ui.fint(k["pedidos"]),
           f"{ui.fint(k['pedidos_validos'])} não cancelados", ui.COR["secundaria"])
    st.write("")
    c = st.columns(4, gap="small")
    ui.kpi(c[0], "payments", "Faturamento", ui.fcurto(k["faturamento"], moeda=True),
           f"ticket médio {ui.fbrl(k['ticket_medio'])}", ui.COR["secundaria"])
    ui.kpi(c[1], "precision_manufacturing", "Máquinas", ui.fint(k["maquinas"]),
           "com telemetria")
    ui.kpi(c[2], "warning", "Máquinas em alerta", ui.fint(k["maquinas_alerta"]),
           f"{k['maquinas_criticas']} crítica(s) agora",
           st_["critico"] if k["maquinas_criticas"] else
           (st_["atencao"] if k["maquinas_alerta"] else st_["ok"]))
    ui.kpi(c[3], "build", "Desgaste elevado", f"{ui.fint(k['componentes_alerta'])} comp.",
           f"{k['componentes_criticos']} acima de 90%",
           st_["critico"] if k["componentes_criticos"] else
           (st_["atencao"] if k["componentes_alerta"] else st_["ok"]))

    st.markdown("#### Situação atual das máquinas")
    if ultima.empty:
        ui.sem_dados("Sem telemetria disponível.")
    else:
        cols = st.columns(max(1, len(ultima)), gap="small")
        for col, (_, r) in zip(cols, ultima.sort_values("machine_code").iterrows()):
            classe = {"CRITICO": "card-alerta", "ATENCAO": "card-atencao"}.get(r["machine_status"], "card-ok")
            col.markdown(
                f'<div class="{classe}"><div class="maq-top"><b>{r["machine_code"]}</b>'
                f'{ui.badge(r["machine_status"])}</div><div class="sens">'
                f'<div>Temperatura<span>{ui.fnum(r["temperature_c"])} °C</span></div>'
                f'<div>Vibração<span>{ui.fnum(r["vibration_mm_s"], 2)} mm/s</span></div>'
                f'<div>Energia<span>{ui.fnum(r["energy_kw"])} kW</span></div></div></div>',
                unsafe_allow_html=True)

    alertas = desg[desg["situacao"] != "NORMAL"] if not desg.empty else desg
    if not alertas.empty:
        st.markdown("#### Componentes que exigem atenção")
        ui.nota("Ordenados pela menor vida útil restante estimada. Vermelho = acima de 90%; amarelo = acima de 75%.")
        maquinas_alerta = sorted(alertas["machine_code"].unique())
        cols = st.columns(max(1, len(maquinas_alerta)), gap="small")
        for col, maq in zip(cols, maquinas_alerta):
            itens = alertas[alertas["machine_code"] == maq].sort_values("estimated_remaining_hours")
            pior = "card-alerta" if (itens["situacao"] == "CRÍTICO").any() else "card-atencao"
            linhas = "".join(
                f'<div class="comp"><span><span class="dot" style="background:'
                f'{ui.COR_STATUS.get(r["situacao"], ui.COR["suave"])}"></span>{r["component_name"]}</span>'
                f'<span class="h">{ui.fnum(r["wear_pct"])}% · {ui.fnum(r["estimated_remaining_hours"])} h restantes</span></div>'
                for _, r in itens.iterrows())
            col.markdown(f'<div class="{pior}"><div class="maq-top"><b>{maq}</b>'
                         f'<span class="nota">{len(itens)} comp.</span></div>{linhas}</div>',
                         unsafe_allow_html=True)

    st.markdown("#### Evolução no período")
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
