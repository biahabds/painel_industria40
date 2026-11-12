"""Radar Industrial 4.0 — painel gerencial de BI conectado ao Supabase.

Execução local:  streamlit run app.py
"""
from __future__ import annotations

from datetime import datetime, time as dtime, timedelta, timezone

import streamlit as st

st.set_page_config(page_title="Radar Industrial 4.0", page_icon=":material/precision_manufacturing:", layout="wide",
                   initial_sidebar_state="expanded")

from core import db, ui  # noqa: E402
from core.dados import Contexto  # noqa: E402
from core.transform import BR_TZ, ORDEM_TURNOS  # noqa: E402
from paginas import (dados_conexao, executivo, financeiro, manutencao, maquinas,  # noqa: E402
                     producao, producao_vendas, respostas, vendas)

NOME_EQUIPE = "Equipe: Beatriz Andrade Barbosa de Sousa e Pedro Henrique de Souza Pereira"

ui.aplicar_estilo()

PERIODOS = {
    "Última 1 hora": timedelta(hours=1),
    "Últimas 6 horas": timedelta(hours=6),
    "Últimas 24 horas": timedelta(hours=24),
    "Últimos 7 dias": timedelta(days=7),
    "Últimos 30 dias": timedelta(days=30),
    "Todo o histórico": None,
    "Personalizado": "custom",
}

# ---------------------------------------------------------------------------
# Barra lateral: filtros e atualização automática
# ---------------------------------------------------------------------------
SLUGS = ["executivo", "producao", "vendas", "producao-vendas", "maquinas", "manutencao",
         "financeiro", "respostas", "dados"]

with st.sidebar:
    ui.marca()
    st.caption(NOME_EQUIPE)
    ui.seletor_tema(SLUGS)
    st.divider()

    st.markdown("**Período**")
    periodo = st.selectbox("Período", list(PERIODOS), index=5, label_visibility="collapsed")
    datas = None
    if PERIODOS[periodo] == "custom":
        hoje = datetime.now(BR_TZ).date()
        datas = st.date_input("Intervalo", (hoje - timedelta(days=3), hoje), format="DD/MM/YYYY")

    try:
        maqs_df = db.maquinas()
        opc = db.opcoes_filtros()
        conexao_ok, erro_conexao = True, None
    except db.ErroBanco as e:
        maqs_df, opc = None, {"produtos": [], "turnos": ORDEM_TURNOS, "canais": [], "regioes": []}
        conexao_ok, erro_conexao = False, str(e)

    lista_maq = sorted(maqs_df["machine_code"].astype(str).str.strip()) if maqs_df is not None else []
    f_maq = st.multiselect("Máquina", lista_maq, placeholder="Todas")
    f_prod = st.multiselect("Produto", opc["produtos"], placeholder="Todos")
    turnos = [t for t in ORDEM_TURNOS if t in opc["turnos"]] or opc["turnos"]
    f_turno = st.multiselect("Turno", turnos, placeholder="Todos")
    with st.expander("Filtros comerciais"):
        f_canal = st.multiselect("Canal de venda", opc["canais"], placeholder="Todos")
        f_reg = st.multiselect("Região", opc["regioes"], placeholder="Todas")

    st.divider()
    st.markdown("**Atualização dos dados**")
    auto = st.toggle("Atualização automática", value=True)
    intervalo = st.select_slider("Intervalo (segundos)", [5, 10, 15, 30, 60], value=10,
                                 disabled=not auto)
    st.caption("Mecanismo: **polling** — consulta periódica automática ao PostgreSQL do "
               "Supabase (não é assinatura nativa Supabase Realtime).")
    if st.button("Limpar cache e recarregar", icon=":material/refresh:", width="stretch"):
        st.cache_data.clear()
        st.rerun()


def montar_contexto() -> Contexto:
    """Recalculado a cada ciclo de polling para que 'agora' avance junto com os dados."""
    agora = datetime.now(timezone.utc)
    agora = agora.replace(second=(agora.second // 5) * 5, microsecond=0) + timedelta(seconds=5)
    p = PERIODOS[periodo]
    if p == "custom" and datas and len(datas) == 2:
        ini = datetime.combine(datas[0], dtime.min, BR_TZ).astimezone(timezone.utc)
        fim = datetime.combine(datas[1] + timedelta(days=1), dtime.min, BR_TZ).astimezone(timezone.utc)
    elif p is None or p == "custom":
        ini, fim = datetime(2000, 1, 1, tzinfo=timezone.utc), agora
    else:
        ini, fim = agora - p, agora
    return Contexto(ini=ini, fim=fim, maquinas=f_maq, produtos=f_prod, turnos=f_turno,
                    canais=f_canal, regioes=f_reg)


def _ts(v):
    """Converte valor de data do banco em Timestamp com fuso (ou None)."""
    import pandas as pd
    if v is None or pd.isna(v):
        return None
    t = pd.Timestamp(v)
    return t.tz_localize("UTC") if t.tzinfo is None else t


def barra_ao_vivo():
    try:
        p = db.pulso().iloc[0]
        ult, agora_bd = _ts(p["ultima_telemetria"]), _ts(p["agora_banco"])
        ult_txt = ult.tz_convert(BR_TZ).strftime("%d/%m %H:%M:%S") if ult is not None else "—"
        atraso = (agora_bd - ult).total_seconds() if ult is not None and agora_bd is not None else None
        ativo = atraso is not None and atraso < 90
        estado = (f'<span class="chip ok"><span class="pulso"></span>Simulador enviando dados</span>' if ativo
                  else '<span class="chip off"><span class="ms">pause_circle</span> Sem dados novos no último 1,5 min</span>')
        modo = (f'<span class="ms">sync</span> Polling a cada {intervalo} s' if auto
                else '<span class="ms">sync_disabled</span> Atualização automática desligada')
        st.markdown(
            f'<div class="aovivo">{estado}<span class="chip">{modo}</span>'
            f'<span class="chip"><span class="ms">sensors</span> Última telemetria: {ult_txt}</span>'
            f'<span class="chip"><span class="ms">speed</span> {int(p["telemetria_1min"])} leituras/min</span>'
            f'<span class="chip"><span class="ms">schedule</span> Atualizado às '
            f'{datetime.now(BR_TZ).strftime("%H:%M:%S")}</span></div>', unsafe_allow_html=True)
    except db.ErroBanco:
        pass


def executar(render):
    def pagina():
        if not conexao_ok:
            st.error(icon=":material/cloud_off:", body=f"Não foi possível conectar ao banco de dados.\n\n{erro_conexao}")
            st.button("Tentar novamente", on_click=st.cache_resource.clear)
            return

        @st.fragment(run_every=intervalo if auto else None)
        def corpo():
            barra_ao_vivo()
            try:
                render(montar_contexto())
            except db.ErroBanco as e:
                st.error(icon=":material/sync_problem:", body=f"Erro de comunicação com o Supabase. O painel tentará de novo "
                         f"no próximo ciclo.\n\n`{e}`")
        corpo()
    pagina.__name__ = render.__module__.split(".")[-1]
    return pagina


# Menu no topo, agrupado por área; a barra lateral fica só com tema e filtros.
paginas = {
    "Visão geral": [
        st.Page(executar(executivo.render), title="Visão executiva", icon=":material/dashboard:",
                url_path="executivo", default=True),
    ],
    "Operação": [
        st.Page(executar(producao.render), title="Produção", icon=":material/factory:", url_path="producao"),
        st.Page(executar(maquinas.render), title="Monitoramento de máquinas", icon=":material/sensors:",
                url_path="maquinas"),
        st.Page(executar(manutencao.render), title="Manutenção e desgaste", icon=":material/build:",
                url_path="manutencao"),
    ],
    "Comercial": [
        st.Page(executar(vendas.render), title="Vendas", icon=":material/shopping_cart:", url_path="vendas"),
        st.Page(executar(producao_vendas.render), title="Produção × Vendas", icon=":material/compare_arrows:",
                url_path="producao-vendas"),
        st.Page(executar(financeiro.render), title="Financeiro", icon=":material/payments:", url_path="financeiro"),
    ],
    "Conclusões": [
        st.Page(executar(respostas.render), title="Respostas e recomendações", icon=":material/insights:",
                url_path="respostas"),
        st.Page(executar(dados_conexao.render), title="Dados e conexão", icon=":material/database:",
                url_path="dados"),
    ],
}
st.navigation(paginas, position="top").run()
