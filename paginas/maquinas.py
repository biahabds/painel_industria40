import pandas as pd
import plotly.express as px
import streamlit as st

from core import dados, kpis, ui

METRICAS = {
    "Temperatura (°C)": "temperature_c",
    "Vibração (mm/s)": "vibration_mm_s",
    "Consumo de energia (kW)": "energy_kw",
    "Pressão (bar)": "pressure_bar",
    "Rotação (RPM)": "rpm",
}
LIMITES = {"temperature_c": (80, 90), "vibration_mm_s": (4.5, 7)}  # atenção, crítico (regra do simulador)


def render(ctx):
    ui.cabecalho("Monitoramento de máquinas",
                 "Telemetria (machine_telemetry) agregada no banco por máquina e por intervalo de tempo")
    ultima = dados.telemetria_ultima(ctx)
    resumo = kpis.resumo_telemetria(dados.telemetria_resumo(ctx))

    st.markdown("#### Leitura mais recente")
    if ultima.empty:
        ui.sem_dados("Sem leituras de telemetria.")
    else:
        for _, r in ultima.sort_values("machine_code").iterrows():
            with st.container(border=True):
                h = st.columns([1.3, 2, 2, 1.2, 1.2, 1.2])
                hora = r["recorded_at"].strftime("%d/%m %H:%M:%S") if pd.notna(r["recorded_at"]) else "—"
                h[0].markdown(f"**{r['machine_code']}**<br>{ui.badge(r['machine_status'])}<br>"
                              f"<span class='nota'>{hora}</span>", unsafe_allow_html=True)
                with h[1]:
                    ui.grafico(ui.gauge(r["temperature_c"], "Temperatura", 40, 100, 80, 90, " °C"), 190)
                with h[2]:
                    ui.grafico(ui.gauge(r["vibration_mm_s"], "Vibração", 0, 9, 4.5, 7, " mm/s"), 190)
                h[3].metric("Energia", f"{ui.fnum(r['energy_kw'])} kW")
                h[4].metric("Pressão", f"{ui.fnum(r['pressure_bar'])} bar")
                h[5].metric("RPM", ui.fint(r["rpm"]))
    ui.nota("Faixas: temperatura ≥ 80 °C ou vibração ≥ 4,5 mm/s = ATENÇÃO; ≥ 90 °C ou ≥ 7 mm/s = CRÍTICO.")

    if resumo.empty:
        ui.sem_dados()
        return

    st.markdown("#### Situação operacional no período")
    sit = resumo.assign(OPERANDO=resumo["n_leituras"] - resumo["n_atencao"] - resumo["n_critico"])
    sit = sit.rename(columns={"n_atencao": "ATENCAO", "n_critico": "CRITICO"})
    longo = sit.melt(id_vars="machine_code", value_vars=["OPERANDO", "ATENCAO", "CRITICO"],
                     var_name="status", value_name="leituras")
    fig = px.bar(longo, x="leituras", y="machine_code", color="status", orientation="h",
                 color_discrete_map=ui.COR_STATUS, title="% das leituras por status")
    fig.update_layout(barnorm="percent", yaxis_title=None, xaxis_title="%", legend=dict(orientation="h", y=1.15))
    ui.grafico(fig, 300)

    ui.tabela(resumo[["machine_code", "n_leituras", "temp_media", "temp_max", "vib_media", "vib_max",
                      "energia_media_kw", "pressao_media", "rpm_medio", "pct_alerta"]]
              .rename(columns={"machine_code": "Máquina", "n_leituras": "Leituras", "temp_media": "Temp. média",
                               "temp_max": "Temp. máx.", "vib_media": "Vibr. média", "vib_max": "Vibr. máx.",
                               "energia_media_kw": "Energia média (kW)", "pressao_media": "Pressão média",
                               "rpm_medio": "RPM médio", "pct_alerta": "% leituras em alerta"}),
              {"Leituras": "int", "Temp. média": "num", "Temp. máx.": "num", "Vibr. média": "num",
               "Vibr. máx.": "num", "Energia média (kW)": "num", "Pressão média": "num",
               "RPM médio": "int", "% leituras em alerta": "pct"})

    st.markdown("#### Evolução dos indicadores")
    serie = dados.telemetria_serie(ctx)
    if serie.empty:
        ui.sem_dados()
        return
    escolha = st.radio("Indicador", list(METRICAS), horizontal=True, key="metrica_maq")
    col = METRICAS[escolha]
    fig = px.line(serie, x="bucket", y=col, color="machine_code",
                  title=f"{escolha} — média por intervalo de {ctx.bucket_sql}")
    if col in LIMITES:
        at, cr = LIMITES[col]
        fig.add_hline(y=at, line_dash="dot", line_color=ui.COR["atencao"], annotation_text="atenção")
        fig.add_hline(y=cr, line_dash="dot", line_color=ui.COR["critico"], annotation_text="crítico")
    fig.update_layout(xaxis_title=None, legend_title=None)
    ui.grafico(fig, 380)

    a, b = st.columns(2)
    with a:
        ui.grafico(ui.barra(resumo, "machine_code", "energia_media_kw", "Consumo médio de energia (kW)",
                            color_discrete_sequence=[ui.COR["primaria"]]))
    with b:
        ui.grafico(ui.barra(resumo, "machine_code", "vib_media", "Vibração média (mm/s)",
                            color_discrete_sequence=[ui.COR["secundaria"]]))
