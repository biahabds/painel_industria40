"""Identidade visual, formatação pt-BR e componentes reutilizáveis."""
from __future__ import annotations

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import plotly.io as pio
import streamlit as st

# Paleta própria da equipe
COR = {
    "fundo": "#0B1220", "painel": "#131C2E", "borda": "#24314A",
    "texto": "#E6EDF7", "suave": "#8FA1BF",
    "primaria": "#F5A524",   # âmbar
    "secundaria": "#38BDF8", # azul
    "ok": "#22C55E", "atencao": "#F5A524", "critico": "#EF4444",
}
SEQ = ["#F5A524", "#38BDF8", "#A78BFA", "#22C55E", "#F472B6", "#FB923C", "#2DD4BF"]
COR_STATUS = {"OPERANDO": COR["ok"], "NORMAL": COR["ok"], "ATENCAO": COR["atencao"],
              "ATENÇÃO": COR["atencao"], "CRITICO": COR["critico"], "CRÍTICO": COR["critico"]}

pio.templates["radar"] = go.layout.Template(layout=go.Layout(
    font=dict(family="Inter, Segoe UI, sans-serif", color=COR["texto"], size=13),
    paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
    colorway=SEQ,
    xaxis=dict(gridcolor=COR["borda"], zerolinecolor=COR["borda"]),
    yaxis=dict(gridcolor=COR["borda"], zerolinecolor=COR["borda"]),
    legend=dict(bgcolor="rgba(0,0,0,0)"),
    margin=dict(l=10, r=10, t=50, b=10),
    hoverlabel=dict(bgcolor=COR["painel"]),
    separators=",.",
))
pio.templates.default = "plotly_dark+radar"


from core.formatos import fbrl, fint, fnum, fpct  # noqa: E402,F401


# ---------------------------------------------------------------------------
# Componentes
# ---------------------------------------------------------------------------
CSS = f"""
<style>
.block-container {{padding-top: 1.6rem;}}
div[data-testid="stMetric"] {{
  background: {COR['painel']}; border: 1px solid {COR['borda']};
  border-radius: 12px; padding: 12px 16px;
}}
div[data-testid="stMetricLabel"] p {{color: {COR['suave']}; font-size: .82rem;}}
.badge {{display:inline-block; padding:2px 10px; border-radius:999px;
  font-size:.78rem; font-weight:600; color:#0B1220;}}
.card-alerta {{border-left: 4px solid {COR['critico']}; background:{COR['painel']};
  padding:10px 14px; border-radius:8px; margin-bottom:8px;}}
.card-atencao {{border-left: 4px solid {COR['atencao']}; background:{COR['painel']};
  padding:10px 14px; border-radius:8px; margin-bottom:8px;}}
.card-ok {{border-left: 4px solid {COR['ok']}; background:{COR['painel']};
  padding:10px 14px; border-radius:8px; margin-bottom:8px;}}
.nota {{color:{COR['suave']}; font-size:.85rem;}}
.pulso {{display:inline-block; width:9px; height:9px; border-radius:50%;
  background:{COR['ok']}; margin-right:6px; animation: pisca 1.4s infinite;}}
@keyframes pisca {{0%{{opacity:1}} 50%{{opacity:.25}} 100%{{opacity:1}}}}
</style>
"""


def aplicar_estilo():
    st.markdown(CSS, unsafe_allow_html=True)


def badge(texto: str) -> str:
    cor = COR_STATUS.get(str(texto).upper(), COR["suave"])
    return f'<span class="badge" style="background:{cor}">{texto}</span>'


def cabecalho(titulo: str, subtitulo: str = ""):
    st.markdown(f"## {titulo}")
    if subtitulo:
        st.markdown(f'<span class="nota">{subtitulo}</span>', unsafe_allow_html=True)


def sem_dados(msg="Nenhum registro encontrado para os filtros selecionados."):
    st.info(f"ℹ️ {msg} Tente ampliar o período ou remover filtros.")


def nota(texto: str):
    st.markdown(f'<p class="nota">{texto}</p>', unsafe_allow_html=True)


def grafico(fig, altura=360):
    fig.update_layout(height=altura)
    st.plotly_chart(fig, use_container_width=True, config={"displaylogo": False})


def barra(df, x, y, titulo, cor=None, horizontal=False, texto=None, **kw):
    if horizontal:
        fig = px.bar(df, x=y, y=x, orientation="h", title=titulo, color=cor, text=texto, **kw)
        fig.update_yaxes(categoryorder="total ascending", title=None)
    else:
        fig = px.bar(df, x=x, y=y, title=titulo, color=cor, text=texto, **kw)
        fig.update_xaxes(title=None)
    if texto:
        fig.update_traces(textposition="outside", cliponaxis=False)
    return fig


def gauge(valor, titulo, minimo, maximo, atencao, critico, sufixo=""):
    fig = go.Figure(go.Indicator(
        mode="gauge+number", value=valor,
        number={"suffix": sufixo, "valueformat": ".1f"},
        title={"text": titulo, "font": {"size": 13}},
        gauge={"axis": {"range": [minimo, maximo]},
               "bar": {"color": COR["texto"]},
               "steps": [{"range": [minimo, atencao], "color": "rgba(34,197,94,.35)"},
                         {"range": [atencao, critico], "color": "rgba(245,165,36,.45)"},
                         {"range": [critico, maximo], "color": "rgba(239,68,68,.5)"}]}))
    fig.update_layout(height=190, margin=dict(l=15, r=15, t=40, b=5))
    return fig


def tabela(df: pd.DataFrame, formatos: dict | None = None, altura=None):
    """Mostra DataFrame com colunas formatadas no padrão brasileiro."""
    if df is None or df.empty:
        sem_dados()
        return
    d = df.copy()
    for col, f in (formatos or {}).items():
        if col in d.columns:
            d[col] = d[col].map({"int": fint, "brl": fbrl, "pct": fpct,
                                 "num": fnum}.get(f, str))
    extra = {"height": altura} if altura else {}
    st.dataframe(d, use_container_width=True, hide_index=True, **extra)
