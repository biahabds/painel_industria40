import plotly.express as px
import streamlit as st

from core import dados, kpis, ui


def render(ctx):
    ui.cabecalho("🛒 Análise de vendas",
                 "Pedidos de venda (sales_orders). Faturamento considera pedidos não cancelados.")
    v = dados.vendas(ctx)
    if v.empty:
        ui.sem_dados()
        return

    fat = v["receita_valida"].sum()
    validos = int(v["valido"].sum())
    c = st.columns(5)
    c[0].metric("Faturamento", ui.fbrl(fat))
    c[1].metric("Pedidos", ui.fint(len(v)), f"{ui.fint(len(v) - validos)} cancelados", delta_color="off")
    c[2].metric("Ticket médio", ui.fbrl(fat / validos if validos else float("nan")),
                help="Faturamento ÷ pedidos não cancelados")
    c[3].metric("Unidades vendidas", ui.fint(v["qtd_valida"].sum()))
    c[4].metric("Preço médio/unid.", ui.fbrl(fat / v["qtd_valida"].sum() if v["qtd_valida"].sum() else float("nan")))

    vp = kpis.vendas_por(v, "product_name")
    vr = kpis.vendas_por(v, "customer_region")
    vc = kpis.vendas_por(v, "sales_channel")
    vs = kpis.pedidos_por_status(v)

    a, b = st.columns(2)
    with a:
        ui.grafico(ui.barra(vp, "product_name", "faturamento", "Faturamento por produto (R$)", horizontal=True))
    with b:
        ui.grafico(ui.barra(vp, "product_name", "qtd_vendida", "Quantidade vendida por produto",
                            horizontal=True, color_discrete_sequence=[ui.COR["secundaria"]]))
    a, b, c3 = st.columns(3)
    with a:
        fig = px.bar(vr, x="customer_region", y="faturamento", title="Vendas por região (R$)",
                     color_discrete_sequence=[ui.COR["primaria"]])
        fig.update_layout(xaxis_title=None)
        ui.grafico(fig)
    with b:
        fig = px.pie(vc, names="sales_channel", values="faturamento", hole=.55, title="Vendas por canal")
        ui.grafico(fig)
    with c3:
        fig = px.bar(vs, x="order_status", y="pedidos", color="order_status", title="Pedidos por situação",
                     color_discrete_map={"FATURADO": ui.COR["ok"], "ENVIADO": ui.COR["secundaria"],
                                         "PENDENTE": ui.COR["atencao"], "CANCELADO": ui.COR["critico"]})
        fig.update_layout(showlegend=False, xaxis_title=None)
        ui.grafico(fig)

    st.markdown("#### 📈 Evolução das vendas")
    sv = kpis.serie_temporal(v, "created_at", {"faturamento": ("receita_valida", "sum"),
                                               "pedidos": ("order_number", "count")}, ctx.freq_pandas)
    fig = px.area(sv, x="created_at", y="faturamento", title="Faturamento ao longo do tempo (R$)")
    fig.update_traces(line_color=ui.COR["primaria"], fillcolor="rgba(245,165,36,.25)")
    fig.update_layout(xaxis_title=None)
    ui.grafico(fig, 340)

    st.markdown("#### Resumo por canal")
    ui.tabela(vc[["sales_channel", "pedidos", "qtd_vendida", "faturamento", "ticket_medio", "participacao"]]
              .rename(columns={"sales_channel": "Canal", "pedidos": "Pedidos", "qtd_vendida": "Unidades",
                               "faturamento": "Faturamento", "ticket_medio": "Ticket médio",
                               "participacao": "Participação"}),
              {"Pedidos": "int", "Unidades": "int", "Faturamento": "brl", "Ticket médio": "brl",
               "Participação": "pct"})
