import plotly.express as px
import streamlit as st

from core import dados, kpis, ui


def _graficos(prod, vend, desg, risco):
    """Gráfico de evidência para cada pergunta (n → figura)."""
    pm = kpis.produtividade_maquinas(prod)
    pt = kpis.producao_por(prod, "shift_name")
    ph = kpis.producao_por(prod, "hora")
    vp = kpis.vendas_por(vend, "product_name")
    vr = kpis.vendas_por(vend, "customer_region")
    vc = kpis.vendas_por(vend, "sales_channel")
    pv = kpis.producao_vs_vendas(prod, vend)
    fp = kpis.financeiro_por_produto(prod, vend)
    g = {}
    if not pm.empty:
        g[1] = ui.barra(pm, "machine_code", "aprovadas_por_hora", "Aprovadas por hora operando")
        g[2] = ui.barra(pm.assign(r=pm["taxa_rejeicao"] * 100), "machine_code", "r", "Taxa de rejeição (%)",
                        color_discrete_sequence=[ui.COR["critico"]])
    if not pt.empty:
        g[3] = px.bar(pt, x="shift_name", y="aprovadas_por_hora", title="Aprovadas/h por turno",
                      text=pt["taxa_rejeicao"].map(lambda v: f"rej. {ui.fpct(v, 2)}"))
    if not ph.empty:
        g[4] = ui.barra(ph, "hora", "produzido", "Produção por hora (Brasília)")
        g[5] = ui.barra(ph.assign(r=ph["taxa_rejeicao"] * 100), "hora", "r", "Rejeição por hora (%)",
                        color_discrete_sequence=[ui.COR["critico"]])
    if not vp.empty:
        g[6] = ui.barra(vp, "product_name", "faturamento", "Faturamento por produto", horizontal=True)
    if not vr.empty:
        g[7] = ui.barra(vr, "customer_region", "faturamento", "Faturamento por região")
    if not vc.empty:
        g[8] = ui.barra(vc, "sales_channel", "faturamento", "Faturamento por canal")
    if not pv.empty:
        g[9] = px.bar(pv, x="product_name", y=["aprovado", "vendido"], barmode="group",
                      title="Aprovado × vendido")
    if risco is not None and not risco.empty:
        g[10] = ui.barra(risco, "machine_code", "indice_risco", "Índice de risco (0–100)",
                         color_discrete_sequence=[ui.COR["atencao"]])
    if not desg.empty:
        g[11] = px.bar(desg.head(8), x="wear_pct", y="componente", orientation="h", color="situacao",
                       color_discrete_map=ui.COR_STATUS, title="Componentes mais desgastados (%)")
    if not fp.empty and "custo_unit_medio" in fp:
        g[12] = ui.barra(fp, "product_name", "custo_unit_medio", "Custo unitário médio (R$)", horizontal=True)
    return g


def render(ctx):
    ui.cabecalho("🎯 Respostas gerenciais e recomendações",
                 "Calculadas automaticamente a partir do banco, para o período e filtros selecionados")
    prod = dados.producao(ctx)
    vend = dados.vendas(ctx)
    desg = dados.desgaste_atual(ctx)
    tele = kpis.resumo_telemetria(dados.telemetria_resumo(ctx))
    risco = kpis.indice_risco_maquinas(tele, desg, kpis.producao_por(prod, "machine_code"))
    if prod.empty and vend.empty:
        ui.sem_dados()
        return

    resp = kpis.responder_perguntas(prod, vend, tele, desg, risco)
    graf = _graficos(prod, vend, desg, risco)
    cols = st.columns(2)
    for i, r in enumerate(resp):
        with cols[i % 2]:
            with st.container(border=True):
                st.markdown(f"**{r['n']}. {r['pergunta']}**")
                st.markdown(f"### {r['resposta']}")
                ui.nota(r["evidencia"])
                if r["n"] in graf:
                    with st.expander("Ver evidência"):
                        fig = graf[r["n"]]
                        fig.update_layout(showlegend=r["n"] in (9, 11))
                        ui.grafico(fig, 260)

    st.markdown("#### Índice de risco por máquina")
    ui.tabela(risco.rename(columns={"machine_code": "Máquina", "desgaste_max": "Desgaste máx. (%)",
                                    "menor_vida_h": "Menor vida (h)", "pct_alerta": "% leituras em alerta",
                                    "vib_media": "Vibr. média", "temp_media": "Temp. média",
                                    "taxa_rejeicao": "Rejeição", "indice_risco": "Índice de risco"}),
              {"Desgaste máx. (%)": "num", "Menor vida (h)": "int", "% leituras em alerta": "pct",
               "Vibr. média": "num", "Temp. média": "num", "Rejeição": "pct", "Índice de risco": "num"})
    ui.nota("Índice de risco (premissa da equipe) = 40% desgaste máximo + 30% % de leituras em alerta + "
            "15% vibração média (7 mm/s = 100%) + 15% taxa de rejeição (10% = 100%).")

    st.markdown("### 📋 Recomendações para a direção")
    for i, r in enumerate(kpis.gerar_recomendacoes(prod, vend, desg, risco), 1):
        st.markdown(f'<div class="card-ok"><b>{i}. {r["titulo"]}</b><br>'
                    f'<span class="nota">📊 Evidência: {r["base"]}</span><br>✅ {r["acao"]}</div>',
                    unsafe_allow_html=True)
