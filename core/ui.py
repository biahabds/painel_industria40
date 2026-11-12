"""Identidade visual, tema claro/escuro, formatação pt-BR e componentes reutilizáveis."""
from __future__ import annotations

import json

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import plotly.io as pio
import streamlit as st

# ---------------------------------------------------------------------------
# Paletas da equipe (verde-petróleo + índigo). As cores de status são as mesmas
# nos dois temas, para o significado não mudar.
# ---------------------------------------------------------------------------
PALETAS = {
    "light": {
        "fundo": "#F4F6F8", "painel": "#FFFFFF", "borda": "#D3DCE4",
        "texto": "#1B2430", "suave": "#5B6B7C", "grade": "#E3E9EE",
        "primaria": "#0F8B8D", "secundaria": "#4F5BD5",
        "faixa": "linear-gradient(120deg, #0F8B8D 0%, #2E6F9E 55%, #4F5BD5 100%)",
    },
    "dark": {
        "fundo": "#10161D", "painel": "#18212B", "borda": "#2A3644",
        "texto": "#E4EAF0", "suave": "#93A3B4", "grade": "#243040",
        "primaria": "#2CC1B4", "secundaria": "#8F9BFF",
        "faixa": "linear-gradient(120deg, #0F6E70 0%, #24507A 55%, #3A43A8 100%)",
    },
}
STATUS = {"ok": "#2E9E5B", "atencao": "#D99A00", "critico": "#E5484D"}

# COR é atualizado em aplicar_estilo() conforme o tema; as páginas usam ui.COR[...]
COR: dict = {**PALETAS["light"], **STATUS}
SEQ_CLARO = ["#0F8B8D", "#4F5BD5", "#D97706", "#9D4EDD", "#2E9E5B", "#C2417A", "#0EA5E9"]
SEQ_ESCURO = ["#2CC1B4", "#8F9BFF", "#F2A541", "#C084FC", "#4ADE80", "#F472B6", "#38BDF8"]
SEQ = SEQ_CLARO
COR_STATUS = {"OPERANDO": STATUS["ok"], "NORMAL": STATUS["ok"], "ATENCAO": STATUS["atencao"],
              "ATENÇÃO": STATUS["atencao"], "CRITICO": STATUS["critico"], "CRÍTICO": STATUS["critico"]}


def _template(tema: str) -> go.layout.Template:
    p = PALETAS[tema]
    base = pio.templates["plotly_white" if tema == "light" else "plotly_dark"]
    t = go.layout.Template(base)
    t.layout.update(
        font=dict(family="Inter, Segoe UI, sans-serif", color=p["texto"], size=13),
        paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
        colorway=SEQ_CLARO if tema == "light" else SEQ_ESCURO,
        xaxis=dict(gridcolor=p["grade"], zerolinecolor=p["borda"], linecolor=p["borda"]),
        yaxis=dict(gridcolor=p["grade"], zerolinecolor=p["borda"], linecolor=p["borda"]),
        legend=dict(bgcolor="rgba(0,0,0,0)"),
        title=dict(font=dict(size=15, color=p["texto"]), x=0.01, xanchor="left"),
        margin=dict(l=10, r=10, t=56, b=10),
        hoverlabel=dict(bgcolor=p["painel"], bordercolor=p["borda"], font=dict(color=p["texto"])),
        separators=",.",
    )
    return t


TEMPLATES = {"light": _template("light"), "dark": _template("dark")}
pio.templates["radar_light"] = TEMPLATES["light"]
pio.templates["radar_dark"] = TEMPLATES["dark"]
pio.templates.default = "radar_light"


def tema_atual() -> str:
    """'light' ou 'dark', conforme o tema que o navegador está mostrando."""
    try:
        tipo = st.context.theme.type
    except Exception:  # noqa: BLE001
        tipo = None
    return "dark" if tipo == "dark" else "light"


from core.formatos import fbrl, fcurto, fint, fnum, fpct  # noqa: E402,F401


# ---------------------------------------------------------------------------
# Estilo
# ---------------------------------------------------------------------------
def _css(p: dict) -> str:
    return f"""
<style>
.block-container {{max-width: 1400px; padding-top: 3.6rem;}}
.aovivo {{display:flex; flex-wrap:wrap; gap:6px; margin: 0 0 12px;}}
.chip {{display:inline-flex; align-items:center; gap:5px; background:{p['painel']}; border:1px solid {p['borda']};
  color:{p['suave']}; border-radius:999px; padding:3px 10px; font-size:.76rem; white-space:nowrap;}}
.chip.ok {{color:{STATUS['ok']}; border-color:{STATUS['ok']}66; font-weight:600;}}
.chip.off {{color:{STATUS['atencao']}; border-color:{STATUS['atencao']}66; font-weight:600;}}
div[data-testid="stMetric"] {{
  background: {p['painel']}; border: 1px solid {p['borda']};
  border-top: 3px solid {p['primaria']};
  border-radius: 14px; padding: 12px 16px;
}}
div[data-testid="stMetricLabel"] p {{color: {p['suave']}; font-size: .8rem;
  text-transform: uppercase; letter-spacing: .04em;}}
div[data-testid="stMetricValue"] {{font-weight: 700; font-size: 1.55rem !important; letter-spacing: -.01em;
  font-variant-numeric: tabular-nums;}}
div[data-testid="stMetricValue"] > div {{overflow: visible !important;}}
h4 {{border-left: 3px solid {p['primaria']}; padding-left: .6rem; margin: 1.6rem 0 .4rem;
  font-size: 1.08rem !important; font-weight: 600 !important; letter-spacing: -.005em;}}
.faixa {{background: {p['faixa']}; color: #FFFFFF; border-radius: 16px;
  padding: 18px 22px; margin-bottom: 14px;}}
.faixa h2 {{color: #FFFFFF; margin: 0; padding: 0; font-size: 1.55rem; font-weight: 700;}}
.faixa p {{color: rgba(255,255,255,.88); margin: 4px 0 0; font-size: .92rem;}}
.faixa .selo {{float: right; background: rgba(255,255,255,.16); border: 1px solid rgba(255,255,255,.35);
  border-radius: 999px; padding: 3px 12px; font-size: .75rem; font-weight: 600; color: #FFFFFF;}}
.kpi {{background: {p['painel']}; border: 1px solid {p['borda']}; border-radius: 14px;
  padding: 14px 16px; min-height: 104px; display: flex; gap: 12px; align-items: flex-start;}}
.kpi > div:last-child {{min-width: 0;}}
.kpi .ic {{font-family: "Material Symbols Rounded"; font-size: 22px; font-weight: 400; line-height: 1;
  font-feature-settings: "liga"; -webkit-font-smoothing: antialiased;
  width: 40px; height: 40px; border-radius: 10px;
  display: flex; align-items: center; justify-content: center; flex: none;}}
.kpi .rot {{color: {p['suave']}; font-size: .72rem; font-weight: 600; text-transform: uppercase; letter-spacing: .05em;
  white-space: nowrap; overflow: hidden; text-overflow: ellipsis;}}
.kpi .val {{color: {p['texto']}; font-size: 1.5rem; font-weight: 700; line-height: 1.3; white-space: nowrap;
  font-variant-numeric: tabular-nums; letter-spacing: -.01em;}}
.kpi .sub {{color: {p['suave']}; font-size: .78rem; white-space: nowrap; overflow: hidden; text-overflow: ellipsis;}}
.badge {{display:inline-block; padding:2px 10px; border-radius:999px;
  font-size:.74rem; font-weight:700; color:#FFFFFF; letter-spacing:.02em;}}
.card-alerta, .card-atencao, .card-ok {{background:{p['painel']}; border:1px solid {p['borda']};
  padding:10px 14px; border-radius:12px; margin-bottom:8px; color:{p['texto']};}}
.card-alerta {{border-left: 5px solid {STATUS['critico']};}}
.card-atencao {{border-left: 5px solid {STATUS['atencao']};}}
.card-ok {{border-left: 5px solid {STATUS['ok']};}}
.nota {{color:{p['suave']}; font-size:.85rem;}}
.maq-top {{display:flex; justify-content:space-between; align-items:center; margin-bottom:8px;}}
.maq-top b {{font-size:1rem;}}
.sens {{display:flex; flex-direction:column; gap:2px;}}
.sens div {{display:flex; justify-content:space-between; color:{p['suave']}; font-size:.82rem;}}
.sens span {{color:{p['texto']}; font-weight:600; font-variant-numeric: tabular-nums; white-space:nowrap;}}
.comp {{padding:6px 0; border-top:1px solid {p['borda']}; font-size:.86rem;}}
.comp:first-of-type {{border-top:none;}}
.comp .h {{display:block; color:{p['suave']}; font-size:.78rem; padding-left:14px; white-space:nowrap;
  font-variant-numeric: tabular-nums;}}
.dot {{display:inline-block; width:8px; height:8px; border-radius:50%; margin-right:6px; vertical-align:1px;}}
.pulso {{display:inline-block; width:9px; height:9px; border-radius:50%;
  background:{STATUS['ok']}; margin-right:6px; animation: pisca 1.4s infinite;}}
@keyframes pisca {{0%{{opacity:1}} 50%{{opacity:.25}} 100%{{opacity:1}}}}
.marca {{display:flex; gap:10px; align-items:center; margin: 2px 0 6px;}}
.marca .ic {{font-family:"Material Symbols Rounded"; font-size:26px; line-height:1; font-feature-settings:"liga";
  color:#FFFFFF; background:{p['faixa']}; border-radius:10px; width:40px; height:40px;
  display:flex; align-items:center; justify-content:center; flex:none;}}
.marca b {{display:block; font-size:1.02rem; color:{p['texto']};}}
.marca small {{display:block; color:{p['suave']}; font-size:.75rem;}}
.ms {{font-family:"Material Symbols Rounded"; font-size:1.05em; vertical-align:-0.18em;
  font-feature-settings:"liga"; line-height:1;}}
.faixa {{box-shadow: 0 6px 18px rgba(16,22,29,.12);}}
.perg {{color:{p['primaria']}; font-size:.72rem; font-weight:700; text-transform:uppercase; letter-spacing:.06em;}}
.perg-txt {{color:{p['suave']}; font-size:.9rem; margin:2px 0 6px;}}
.resp {{color:{p['texto']}; font-size:1.35rem; font-weight:700; margin-bottom:4px;}}
.rec {{display:flex; gap:14px; background:{p['painel']}; border:1px solid {p['borda']};
  border-radius:14px; padding:14px 16px; margin-bottom:10px; color:{p['texto']};}}
.rec .num {{flex:none; width:32px; height:32px; border-radius:50%; background:{p['primaria']};
  color:#FFFFFF; font-weight:700; display:flex; align-items:center; justify-content:center;}}
.rec p {{margin:6px 0 0; color:{p['suave']}; font-size:.9rem;}}
.rec p b {{color:{p['texto']};}}
.kpi {{box-shadow: 0 1px 2px rgba(16,22,29,.06);}}
</style>
"""


def aplicar_estilo():
    """Aplica o CSS e as cores do tema que está ativo no navegador."""
    global SEQ
    tema = tema_atual()
    COR.clear()
    COR.update({**PALETAS[tema], **STATUS})
    SEQ = SEQ_CLARO if tema == "light" else SEQ_ESCURO
    # gráficos px sem cor definida pegam a paleta do tema no momento da criação
    pio.templates.default = f"radar_{tema}"
    st.markdown(_css(COR), unsafe_allow_html=True)


def seletor_tema(slugs: list[str]):
    """Botões Claro/Escuro na barra lateral.

    O Streamlit guarda o tema escolhido no navegador (localStorage, chave
    stActiveTheme-<caminho>-v2). O botão grava a escolha para todas as páginas
    do painel e recarrega a página, então menus, tabelas e gráficos mudam juntos.
    """
    atual = "Escuro" if tema_atual() == "dark" else "Claro"
    escolha = st.segmented_control("Tema", ["Claro", "Escuro"], default=atual,
                                   key="tema_painel", width="stretch",
                                   format_func=lambda t: (":material/light_mode: " if t == "Claro" else ":material/dark_mode: ") + t)
    if escolha and escolha != atual:
        valor = json.dumps("Dark" if escolha == "Escuro" else "Light")
        st.html(f"""<script>
(() => {{
  const slugs = {json.dumps(slugs)};
  const partes = window.location.pathname.replace(/\\/+$/, "").split("/");
  if (slugs.includes(partes[partes.length - 1])) partes.pop();
  const base = partes.join("/");
  const caminhos = new Set([window.location.pathname, base || "/", base + "/"]);
  slugs.forEach(s => caminhos.add(base + "/" + s));
  caminhos.forEach(c => window.localStorage.setItem("stActiveTheme-" + c + "-v2", {json.dumps(valor)}));
  window.location.reload();
}})();
</script>""", unsafe_allow_javascript=True)


# ---------------------------------------------------------------------------
# Componentes
# ---------------------------------------------------------------------------
ROTULO_STATUS = {"OPERANDO": "OPERANDO", "NORMAL": "NORMAL", "ATENCAO": "ATENÇÃO", "ATENÇÃO": "ATENÇÃO",
                 "CRITICO": "CRÍTICO", "CRÍTICO": "CRÍTICO"}


def badge(texto: str) -> str:
    chave = str(texto).upper()
    cor = COR_STATUS.get(chave, COR["suave"])
    return f'<span class="badge" style="background:{cor}">{ROTULO_STATUS.get(chave, texto)}</span>'


def marca():
    """Bloco de identidade no topo da barra lateral."""
    st.markdown(
        f'<div class="marca"><span class="ic">radar</span><div><b>Radar Industrial 4.0</b>'
        f'<small>Painel de BI · Indústria 4.0</small></div></div>', unsafe_allow_html=True)


def cabecalho(titulo: str, subtitulo: str = "", selo: str = "Radar Industrial 4.0"):
    """Faixa colorida no topo de cada página."""
    sel = f'<span class="selo">{selo}</span>' if selo else ""
    sub = f"<p>{subtitulo}</p>" if subtitulo else ""
    st.markdown(f'<div class="faixa">{sel}<h2>{titulo}</h2>{sub}</div>', unsafe_allow_html=True)


def kpi(col, icone: str, rotulo: str, valor: str, sub: str = "", cor: str | None = None):
    """Cartão de indicador. `icone` = nome de um ícone Material Symbols (ex.: 'factory')."""
    c = cor or COR["primaria"]
    col.markdown(
        f'<div class="kpi"><div class="ic" style="background:{c}22;color:{c}">{icone}</div>'
        f'<div><div class="rot">{rotulo}</div><div class="val">{valor}</div>'
        f'<div class="sub">{sub}</div></div></div>', unsafe_allow_html=True)


def sem_dados(msg="Nenhum registro encontrado para os filtros selecionados."):
    st.info(f"{msg} Tente ampliar o período ou remover filtros.", icon=":material/filter_alt_off:")


def nota(texto: str):
    st.markdown(f'<p class="nota">{texto}</p>', unsafe_allow_html=True)


# Nomes de colunas do banco → rótulos para eixos, legendas e hover dos gráficos
ROTULOS = {
    "wear_pct": "Desgaste (%)", "estimated_remaining_hours": "Horas restantes",
    "machine_code": "Máquina", "product_name": "Produto", "shift_name": "Turno",
    "customer_region": "Região", "sales_channel": "Canal", "order_status": "Situação",
    "produzido": "Produzido (un.)", "vendido": "Vendido (un.)", "aprovado": "Aprovado (un.)",
    "rejeitado": "Rejeitado (un.)", "aprovadas_por_hora": "Aprovadas por hora",
    "cycle_time_seconds": "Tempo de ciclo (s)", "parada_total_min": "Parada total (min)",
    "faturamento": "Faturamento (R$)", "pedidos": "Pedidos", "giro_venda": "Giro de venda",
    "margem_pct": "Margem estimada (%)", "leituras": "Leituras", "componente": "Componente",
    "situacao": "Situação", "status": "Status", "hora": "Hora do dia", "created_at": "Data",
    "measured_at": "Data da medição", "taxa_rejeicao": "Taxa de rejeição", "comp_hist": "Componente",
    "temperature_c": "Temperatura (°C)", "vibration_mm_s": "Vibração (mm/s)", "energy_kw": "Energia (kW)",
    "pressure_bar": "Pressão (bar)", "rpm": "RPM", "recorded_at": "Horário", "ended_at": "Data",
}
# Valores gravados sem acento no banco → como aparecem no painel
VALORES = {"aprovado": "Aprovado", "rejeitado": "Rejeitado", "vendido": "Vendido", "produzido": "Produzido",
           "MANHA": "Manhã", "TARDE": "Tarde", "NOITE": "Noite", "OPERANDO": "Operando",
           "ATENCAO": "Atenção", "CRITICO": "Crítico", "NORMAL": "Normal", "ATENÇÃO": "Atenção",
           "CRÍTICO": "Crítico", "VENDA_DIRETA": "Venda direta", "E-COMMERCE": "E-commerce",
           "DISTRIBUIDOR": "Distribuidor", "REPRESENTANTE": "Representante"}


def rotulo(v):
    return VALORES.get(v, v) if isinstance(v, str) else v


def _humanizar(fig):
    """Troca nomes técnicos por rótulos legíveis, depois que as cores já foram atribuídas."""
    def eixo(ax):
        t = ax.title.text if ax.title else None
        if t in ROTULOS:
            ax.title.text = ROTULOS[t]
    fig.for_each_xaxis(eixo)
    fig.for_each_yaxis(eixo)
    if fig.layout.legend.title and fig.layout.legend.title.text in ROTULOS:
        fig.layout.legend.title.text = ROTULOS[fig.layout.legend.title.text]

    def trace(t):
        if getattr(t, "name", None):
            t.name = rotulo(t.name)
        if getattr(t, "legendgroup", None):
            t.legendgroup = rotulo(t.legendgroup)
        ht = getattr(t, "hovertemplate", None)
        if ht:
            for k, v in ROTULOS.items():
                ht = ht.replace(f"{k}=", f"{v}=")
            for k, v in VALORES.items():
                ht = ht.replace(f"={k}<", f"={v}<")
            t.hovertemplate = ht
        # valores sobre as barras com separador de milhar (656895 → 656.895)
        txt = getattr(t, "text", None)
        if (t.type == "bar" and txt is not None and getattr(t, "texttemplate", None) is None
                and len(txt) and all(isinstance(v, (int, float)) for v in txt)
                and max(abs(float(v)) for v in txt) >= 1000):
            t.texttemplate = "%{text:,.0f}"
        for eixo_dados in ("x", "y"):
            vals = getattr(t, eixo_dados, None)
            if vals is not None and len(vals) and isinstance(vals[0], str):
                setattr(t, eixo_dados, [rotulo(v) for v in vals])
    fig.for_each_trace(trace)


def grafico(fig, altura=360):
    _humanizar(fig)
    fig.update_layout(template=TEMPLATES[tema_atual()], height=altura)
    st.plotly_chart(fig, width="stretch", config={"displaylogo": False})


def barra(df, x, y, titulo, cor=None, horizontal=False, texto=None, **kw):
    kw.setdefault("color_discrete_sequence", SEQ)
    if horizontal:
        fig = px.bar(df, x=y, y=x, orientation="h", title=titulo, color=cor, text=texto, **kw)
        fig.update_yaxes(categoryorder="total ascending", title=None)
    else:
        fig = px.bar(df, x=x, y=y, title=titulo, color=cor, text=texto, **kw)
        fig.update_xaxes(title=None)
    fig.update_traces(marker_line_width=0)
    if texto:
        fig.update_traces(textposition="outside", cliponaxis=False)
    return fig


def gauge(valor, titulo, minimo, maximo, atencao, critico, sufixo=""):
    fig = go.Figure(go.Indicator(
        mode="gauge+number", value=valor,
        number={"suffix": sufixo, "valueformat": ".1f"},
        title={"text": titulo, "font": {"size": 13}},
        gauge={"axis": {"range": [minimo, maximo]},
               "bar": {"color": COR["primaria"], "thickness": 0.3},
               "steps": [{"range": [minimo, atencao], "color": "rgba(46,158,91,.28)"},
                         {"range": [atencao, critico], "color": "rgba(217,154,0,.35)"},
                         {"range": [critico, maximo], "color": "rgba(229,72,77,.38)"}]}))
    fig.update_layout(height=190, margin=dict(l=15, r=15, t=40, b=5))
    return fig


def tabela(df: pd.DataFrame, formatos: dict | None = None, altura=None):
    """Mostra DataFrame com colunas formatadas no padrão brasileiro."""
    if df is None or df.empty:
        sem_dados()
        return
    d = df.copy()
    for col in d.columns:
        if d[col].dtype == object:
            d[col] = d[col].map(rotulo)
    for col, f in (formatos or {}).items():
        if col in d.columns:
            d[col] = d[col].map({"int": fint, "brl": fbrl, "pct": fpct,
                                 "num": fnum}.get(f, str))
    extra = {"height": altura} if altura else {}
    st.dataframe(d, width="stretch", hide_index=True, **extra)
