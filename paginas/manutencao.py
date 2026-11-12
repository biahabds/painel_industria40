import plotly.express as px
import streamlit as st

from core import dados, kpis, ui


def render(ctx):
    ui.cabecalho("Manutenção e desgaste de componentes",
                 "Estado atual (parts_wear) e histórico de medições (wear_events)")
    atual = dados.desgaste_atual(ctx)
    if atual.empty:
        ui.sem_dados("Sem componentes cadastrados em parts_wear.")
        return
    acima75 = atual[atual["wear_pct"] >= atual["warning_threshold_pct"]]
    acima90 = atual[atual["wear_pct"] >= atual["critical_threshold_pct"]]

    c = st.columns(4)
    c[0].metric("Componentes monitorados", ui.fint(len(atual)))
    c[1].metric("Acima de 75% (atenção)", ui.fint(len(acima75)))
    c[2].metric("Acima de 90% (crítico)", ui.fint(len(acima90)))
    c[3].metric("Menor vida restante", f"{ui.fint(atual['estimated_remaining_hours'].min())} h",
                atual.loc[atual["estimated_remaining_hours"].idxmin(), "componente"], delta_color="off")

    if not acima90.empty:
        urgente = acima90.sort_values("estimated_remaining_hours").iloc[0]
        st.error(f"**{len(acima90)} componente(s) em situação crítica (≥ 90%)** — substituir com prioridade. "
                 f"Mais urgente: {urgente['componente']}, com ~{ui.fnum(urgente['estimated_remaining_hours'])} h "
                 "de vida estimada. Lista completa na tabela abaixo.", icon=":material/emergency_home:")
    atencao = acima75[acima75["wear_pct"] < acima75["critical_threshold_pct"]]
    if not atencao.empty:
        st.warning(f"**{len(atencao)} componente(s) em atenção (≥ 75%)** — programar manutenção: " +
                   ", ".join(f"{r.componente} ({ui.fnum(r.wear_pct)}%)" for r in atencao.itertuples()),
                   icon=":material/warning:")
    if acima75.empty:
        st.success("Nenhum componente acima de 75% de desgaste.", icon=":material/check_circle:")

    d = atual.sort_values("wear_pct")
    fig = px.bar(d, x="wear_pct", y="componente", orientation="h", color="situacao",
                 color_discrete_map=ui.COR_STATUS, title="Desgaste por componente (%)",
                 text=d["wear_pct"].map(lambda v: f"{ui.fnum(v)}%"))
    fig.add_vline(x=75, line_dash="dot", line_color=ui.COR["atencao"], annotation_text="75%")
    fig.add_vline(x=90, line_dash="dot", line_color=ui.COR["critico"], annotation_text="90%")
    fig.update_traces(textposition="outside", cliponaxis=False)
    fig.update_layout(xaxis_range=[0, 105], yaxis_title=None, legend_title=None)
    ui.grafico(fig, 420)

    a, b = st.columns(2)
    with a:
        pm = atual.groupby("machine_code").agg(desgaste_medio=("wear_pct", "mean"),
                                               desgaste_max=("wear_pct", "max")).reset_index()
        fig = px.bar(pm, x="machine_code", y=["desgaste_medio", "desgaste_max"], barmode="group",
                     title="Desgaste por máquina (%)")
        fig.update_layout(xaxis_title=None, legend_title=None)
        ui.grafico(fig)
    with b:
        pc = atual.groupby("component_name").agg(desgaste_medio=("wear_pct", "mean")).reset_index()
        ui.grafico(ui.barra(pc, "component_name", "desgaste_medio", "Desgaste médio por tipo de componente (%)",
                            color_discrete_sequence=[ui.COR["primaria"]]))

    fig = px.bar(atual.sort_values("estimated_remaining_hours"), x="componente", y="estimated_remaining_hours",
                 color="situacao", color_discrete_map=ui.COR_STATUS, title="Estimativa de horas restantes")
    fig.update_layout(xaxis_title=None, legend_title=None)
    ui.grafico(fig)

    st.markdown("#### Histórico de evolução do desgaste")
    hist = dados.desgaste_historico(ctx)
    if hist.empty:
        ui.sem_dados("Sem medições de desgaste no período.")
    else:
        opcoes = sorted(hist["componente"].unique())
        padrao = [c for c in atual["componente"].head(4) if c in opcoes] or opcoes[:4]
        sel = st.multiselect("Componentes", opcoes, default=padrao, key="comp_hist")
        h = hist[hist["componente"].isin(sel)] if sel else hist
        fig = px.line(h, x="measured_at", y="wear_pct", color="componente", title="Desgaste (%) ao longo do tempo")
        fig.add_hline(y=75, line_dash="dot", line_color=ui.COR["atencao"])
        fig.add_hline(y=90, line_dash="dot", line_color=ui.COR["critico"])
        fig.update_layout(xaxis_title=None, legend_title=None)
        ui.grafico(fig, 380)

        prev = kpis.taxa_desgaste_por_hora(hist)
        if not prev.empty:
            st.markdown("#### Previsão simples: horas até 90% no ritmo atual")
            ui.tabela(prev.rename(columns={"componente": "Componente", "pp_por_hora": "Desgaste (p.p./h)",
                                           "desgaste_atual": "Desgaste atual (%)",
                                           "horas_ate_90pct": "Horas até 90%"}),
                      {"Desgaste (p.p./h)": "num", "Desgaste atual (%)": "num", "Horas até 90%": "int"})
            ui.nota("Taxa = (último desgaste − primeiro desgaste) ÷ horas entre as medições no período. "
                    "Projeção linear; complementa a coluna estimated_remaining_hours do banco.")

    st.markdown("#### Tabela de componentes")
    ui.tabela(atual[["machine_code", "component_name", "wear_pct", "situacao", "estimated_remaining_hours",
                     "last_inspection_at"]]
              .assign(last_inspection_at=atual["last_inspection_at"].dt.strftime("%d/%m %H:%M"))
              .rename(columns={"machine_code": "Máquina", "component_name": "Componente",
                               "wear_pct": "Desgaste (%)", "situacao": "Situação",
                               "estimated_remaining_hours": "Horas restantes",
                               "last_inspection_at": "Última inspeção"}),
              {"Desgaste (%)": "num", "Horas restantes": "int"})
