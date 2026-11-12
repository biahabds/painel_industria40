import plotly.express as px
import plotly.graph_objects as go
import streamlit as st

from core import dados, kpis, ui


def render(ctx):
    ui.cabecalho("⚖️ Produção × Vendas", "Quanto do que foi produzido e aprovado foi efetivamente vendido")
    st.warning("**Atenção:** a diferença entre produção aprovada e vendas **não representa estoque físico**. "
               "O banco não possui módulo de movimentação de estoque (entradas, saídas, devoluções, "
               "estoque inicial). O saldo é apenas um indicador de descompasso entre fabricar e vender.")
    prod = dados.producao(ctx)
    vend = dados.vendas(ctx)
    pv = kpis.producao_vs_vendas(prod, vend)
    if pv.empty:
        ui.sem_dados()
        return

    apr, ven = pv["aprovado"].sum(), pv["vendido"].sum()
    c = st.columns(4)
    c[0].metric("Produzido", ui.fint(pv["produzido"].sum()))
    c[1].metric("Aprovado", ui.fint(apr))
    c[2].metric("Vendido (não cancelado)", ui.fint(ven))
    c[3].metric("Giro de venda", ui.fpct(ven / apr if apr else float("nan")),
                help="Vendido ÷ aprovado. Abaixo de 100% = produção acima da venda no período.")

    fig = go.Figure()
    fig.add_bar(x=pv["product_name"], y=pv["aprovado"], name="Aprovado", marker_color=ui.COR["secundaria"])
    fig.add_bar(x=pv["product_name"], y=pv["vendido"], name="Vendido", marker_color=ui.COR["primaria"])
    fig.update_layout(barmode="group", title="Aprovado × vendido por produto",
                      legend=dict(orientation="h", y=1.12))
    ui.grafico(fig)

    a, b = st.columns(2)
    with a:
        maior_sobra = pv.sort_values("giro_venda")
        fig = px.bar(maior_sobra, x="giro_venda", y="product_name", orientation="h",
                     title="Giro de venda por produto (menor = mais produção sem venda)",
                     text=maior_sobra["giro_venda"].map(ui.fpct))
        fig.update_traces(marker_color=ui.COR["atencao"], textposition="outside", cliponaxis=False)
        fig.update_layout(yaxis_title=None, xaxis_tickformat=".0%")
        ui.grafico(fig)
    with b:
        dem = pv.sort_values("vendido", ascending=False)
        fig = px.bar(dem, x="product_name", y="vendido", title="Produtos com maior demanda (unidades vendidas)",
                     text=dem["participacao_demanda"].map(ui.fpct))
        fig.update_traces(marker_color=ui.COR["ok"], textposition="outside", cliponaxis=False)
        fig.update_layout(xaxis_title=None)
        ui.grafico(fig)

    st.markdown("#### Diferença por período")
    per = kpis.producao_vs_vendas_periodo(prod, vend, ctx.freq_pandas)
    if not per.empty:
        fig = go.Figure()
        fig.add_scatter(x=per["periodo"], y=per["aprovado"], name="Aprovado", line=dict(color=ui.COR["secundaria"]))
        fig.add_scatter(x=per["periodo"], y=per["vendido"], name="Vendido", line=dict(color=ui.COR["primaria"]))
        fig.add_bar(x=per["periodo"], y=per["diferenca"], name="Diferença", marker_color="rgba(167,139,250,.45)")
        fig.update_layout(title="Aprovado, vendido e diferença ao longo do tempo",
                          legend=dict(orientation="h", y=1.12))
        ui.grafico(fig, 360)

    ui.tabela(pv.rename(columns={"product_name": "Produto", "produzido": "Produzido", "aprovado": "Aprovado",
                                 "vendido": "Vendido", "saldo_aprovado_menos_vendido": "Aprovado − vendido",
                                 "giro_venda": "Giro de venda", "participacao_demanda": "Part. na demanda"}),
              {"Produzido": "int", "Aprovado": "int", "Vendido": "int", "Aprovado − vendido": "int",
               "Giro de venda": "pct", "Part. na demanda": "pct"})
    ui.nota("Vendas ligadas à produção pelo campo batch_id. Pedidos cancelados não entram em 'vendido'.")
