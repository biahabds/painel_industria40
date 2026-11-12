import plotly.express as px
import streamlit as st

from core import dados, kpis, ui


def render(ctx):
    ui.cabecalho("Análise de produção",
                 "Volume, qualidade, tempo de ciclo, paradas e produtividade (production_events + machines)")
    prod = dados.producao(ctx)
    if prod.empty:
        ui.sem_dados()
        return

    c = st.columns(5)
    c[0].metric("Lotes", ui.fint(len(prod)))
    c[1].metric("Produzido", ui.fcurto(prod["qty_produced"].sum()),
                help=ui.fint(prod["qty_produced"].sum()) + " unidades")
    c[2].metric("Rejeitado", ui.fcurto(prod["qty_rejected"].sum()),
                f"{ui.fpct(prod['qty_rejected'].sum() / prod['qty_produced'].sum(), 2)} de rejeição",
                delta_color="off")
    c[3].metric("Tempo de ciclo médio", f"{ui.fnum(prod['cycle_time_seconds'].mean())} s")
    c[4].metric("Parada total", f"{ui.fcurto(prod['downtime_minutes'].sum())} min",
                f"média {ui.fnum(prod['downtime_minutes'].mean())} min/lote", delta_color="off")

    pm = kpis.producao_por(prod, "machine_code")
    pl = kpis.producao_por(prod, "production_line")
    pp = kpis.producao_por(prod, "product_name")
    pt = kpis.producao_por(prod, "shift_name")
    ph = kpis.producao_por(prod, "hora")

    a, b = st.columns(2)
    with a:
        fig = px.bar(pm, x="machine_code", y=["aprovado", "rejeitado"], title="Produção por máquina",
                     color_discrete_sequence=[ui.COR["secundaria"], ui.COR["critico"]])
        fig.update_layout(legend_title=None, xaxis_title=None, yaxis_title="Unidades")
        ui.grafico(fig)
    with b:
        ui.grafico(ui.barra(pl, "production_line", "produzido", "Produção por linha", texto="produzido"))

    a, b = st.columns(2)
    with a:
        ui.grafico(ui.barra(pp, "product_name", "produzido", "Produção por produto", horizontal=True))
    with b:
        fig = px.bar(pt, x="shift_name", y="produzido", title="Produção por turno",
                     text=pt["taxa_rejeicao"].map(lambda v: f"rejeição {ui.fpct(v, 2)}"))
        fig.update_traces(textposition="outside", cliponaxis=False)
        fig.update_layout(xaxis_title=None)
        ui.grafico(fig)
        ui.nota("Turno conforme gravado pelo sistema (shift_name). Observação da equipe: o simulador "
                "classifica o turno pela hora UTC, então NOITE corresponde a 19h–03h em Brasília.")

    fig = px.bar(ph, x="hora", y="produzido", title="Produção por hora do dia (horário de Brasília) × taxa de rejeição")
    fig.add_scatter(x=ph["hora"], y=ph["taxa_rejeicao"] * 100, name="Rejeição (%)", yaxis="y2",
                    mode="lines+markers", line=dict(color=ui.COR["critico"]))
    fig.update_layout(xaxis=dict(dtick=1, title="Hora"), yaxis_title="Unidades",
                      yaxis2=dict(title="% rejeição", overlaying="y", side="right", showgrid=False),
                      showlegend=False)
    ui.grafico(fig, 380)

    a, b = st.columns(2)
    with a:
        fig = px.box(prod, x="machine_code", y="cycle_time_seconds", title="Tempo de ciclo por máquina (s)",
                     color="machine_code")
        fig.update_layout(showlegend=False, xaxis_title=None)
        ui.grafico(fig)
    with b:
        fig = px.bar(pm, x="machine_code", y="parada_total_min", title="Tempo de parada por máquina (min)",
                     color_discrete_sequence=[ui.COR["primaria"]], text="parada_total_min")
        fig.update_traces(texttemplate="%{text:.0f}", textposition="outside", cliponaxis=False)
        fig.update_layout(xaxis_title=None)
        ui.grafico(fig)

    st.markdown("#### Comparação de produtividade entre máquinas")
    prodt = kpis.produtividade_maquinas(prod)
    ui.tabela(prodt[["machine_code", "lotes", "produzido", "aprovado", "taxa_rejeicao",
                     "aprovadas_por_hora", "capacidade_nominal_h", "uso_capacidade",
                     "ciclo_medio_s", "parada_total_min", "kwh_por_unidade", "oee_medio"]]
              .rename(columns={"machine_code": "Máquina", "lotes": "Lotes", "produzido": "Produzido",
                               "aprovado": "Aprovado", "taxa_rejeicao": "Rejeição",
                               "aprovadas_por_hora": "Aprovadas/h", "capacidade_nominal_h": "Capac. nominal/h",
                               "uso_capacidade": "Uso da capacidade", "ciclo_medio_s": "Ciclo médio (s)",
                               "parada_total_min": "Parada (min)", "kwh_por_unidade": "kWh/unid.",
                               "oee_medio": "OEE estimado"}),
              {"Produzido": "int", "Aprovado": "int", "Rejeição": "pct", "Aprovadas/h": "int",
               "Capac. nominal/h": "int", "Uso da capacidade": "pct", "Ciclo médio (s)": "num",
               "Parada (min)": "int", "kWh/unid.": "num", "OEE estimado": "pct"})
    ui.nota("Aprovadas/h = (produzido − rejeitado) ÷ horas efetivamente operando (duração do lote − parada). "
            "Uso da capacidade = produção por hora operando ÷ capacidade nominal (machines). "
            "OEE estimado = disponibilidade × desempenho × qualidade, por lote.")
