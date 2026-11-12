import plotly.express as px
import plotly.graph_objects as go
import streamlit as st

from core import dados, kpis, ui


def render(ctx):
    ui.cabecalho("💰 Análise financeira", "Receitas, custos estimados e margem estimada por produto")
    with st.expander("📌 Premissas adotadas pela equipe (leia antes de interpretar)", expanded=False):
        st.markdown("""
- **Receita** = soma de `total_amount` dos pedidos **não cancelados** (`order_status ≠ CANCELADO`).
- **Custo estimado de produção** = `qty_produced × unit_cost` de cada lote (inclui as peças rejeitadas).
- **Custo dos rejeitados** = `qty_rejected × unit_cost` — perda direta por refugo.
- **CPV estimado** (custo do que foi vendido) = `qty_sold × unit_cost do lote` ligado pelo `batch_id`;
  se o lote estiver fora do período, usa o custo médio ponderado do produto.
- **Margem bruta estimada** = receita − CPV estimado. **Não é lucro líquido**: o banco não traz
  impostos, frete, comissões, salários, despesas administrativas nem depreciação.
- **Custo de energia** (opcional) = `energy_kwh × tarifa` informada abaixo; mostrado à parte, pois
  `unit_cost` pode já incluir energia.
""")
    tarifa = st.number_input("Tarifa de energia para estimativa (R$/kWh)", 0.0, 5.0, 0.85, 0.05,
                             key="tarifa_kwh")
    prod = dados.producao(ctx)
    vend = dados.vendas(ctx)
    if prod.empty and vend.empty:
        ui.sem_dados()
        return
    fp = kpis.financeiro_por_produto(prod, vend)

    receita = fp["faturamento"].sum()
    cpv = fp["cpv_estimado"].sum()
    c = st.columns(5)
    c[0].metric("Receita", ui.fbrl(receita))
    c[1].metric("Custo estimado de produção", ui.fbrl(fp["custo_producao"].sum()))
    c[2].metric("CPV estimado", ui.fbrl(cpv))
    c[3].metric("Margem bruta estimada", ui.fbrl(receita - cpv),
                ui.fpct((receita - cpv) / receita) if receita else None, delta_color="off")
    c[4].metric("Custo dos rejeitados", ui.fbrl(fp["custo_rejeitados"].sum()), delta_color="off",
                delta=ui.fpct(fp["custo_rejeitados"].sum() / fp["custo_producao"].sum())
                + " do custo" if fp["custo_producao"].sum() else None)

    a, b = st.columns(2)
    with a:
        fig = go.Figure()
        fig.add_bar(x=fp["product_name"], y=fp["faturamento"], name="Receita", marker_color=ui.COR["primaria"])
        fig.add_bar(x=fp["product_name"], y=fp["cpv_estimado"], name="CPV estimado", marker_color=ui.COR["secundaria"])
        fig.update_layout(barmode="group", title="Faturamento × custo do vendido por produto",
                          legend=dict(orientation="h", y=1.12))
        ui.grafico(fig)
    with b:
        d = fp.sort_values("margem_pct")
        fig = px.bar(d, x="margem_pct", y="product_name", orientation="h", title="Margem bruta estimada por produto",
                     text=d["margem_pct"].map(ui.fpct))
        fig.update_traces(marker_color=ui.COR["ok"], textposition="outside", cliponaxis=False)
        fig.update_layout(xaxis_tickformat=".0%", yaxis_title=None)
        ui.grafico(fig)

    a, b = st.columns(2)
    with a:
        vc = kpis.vendas_por(vend, "sales_channel")
        if not vc.empty:
            ui.grafico(ui.barra(vc, "sales_channel", "faturamento", "Receita por canal de venda (R$)",
                                color_discrete_sequence=[ui.COR["primaria"]]))
    with b:
        pm = kpis.producao_por(prod, "machine_code")
        if not pm.empty:
            pm["custo_energia"] = pm["energia_kwh"] * tarifa
            fig = px.bar(pm, x="machine_code", y=["custo_producao", "custo_rejeitados", "custo_energia"],
                         barmode="group", title="Custo estimado por máquina (R$)",
                         color_discrete_sequence=[ui.COR["secundaria"], ui.COR["critico"], ui.COR["primaria"]])
            fig.update_layout(xaxis_title=None, legend_title=None, legend=dict(orientation="h", y=1.12))
            ui.grafico(fig)

    ui.grafico(ui.barra(fp, "product_name", "custo_rejeitados", "Custo dos produtos rejeitados por produto (R$)",
                        color_discrete_sequence=[ui.COR["critico"]]), 300)

    st.markdown("#### Demonstrativo por produto")
    ui.tabela(fp[["product_name", "produzido", "custo_unit_medio", "custo_producao", "custo_rejeitados",
                  "qtd_vendida", "preco_medio", "faturamento", "cpv_estimado", "margem_bruta_estimada",
                  "margem_pct", "margem_apos_refugo"]]
              .rename(columns={"product_name": "Produto", "produzido": "Produzido",
                               "custo_unit_medio": "Custo unit. médio", "custo_producao": "Custo produção",
                               "custo_rejeitados": "Custo rejeitados", "qtd_vendida": "Vendido",
                               "preco_medio": "Preço médio", "faturamento": "Receita", "cpv_estimado": "CPV",
                               "margem_bruta_estimada": "Margem bruta", "margem_pct": "Margem %",
                               "margem_apos_refugo": "Margem − refugo"}),
              {"Produzido": "int", "Custo unit. médio": "brl", "Custo produção": "brl", "Custo rejeitados": "brl",
               "Vendido": "int", "Preço médio": "brl", "Receita": "brl", "CPV": "brl", "Margem bruta": "brl",
               "Margem %": "pct", "Margem − refugo": "brl"})
    ui.nota("Valores estimados com os campos disponíveis. Margem estimada ≠ lucro líquido.")
