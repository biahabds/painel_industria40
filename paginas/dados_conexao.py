import re

import pandas as pd

import streamlit as st

from core import db, ui
from core.transform import BR_TZ


def _host_mascarado() -> str:
    url = db._database_url() or ""
    m = re.search(r"@([^:/]+)", url)
    return m.group(1) if m else "—"


def render(ctx):
    ui.cabecalho("🗄️ Dados e conexão com o Supabase",
                 "Evidência de conexão, estrutura das seis tabelas, relacionamentos e consultas utilizadas")

    with st.container(border=True):
        c = st.columns(3)
        c[0].markdown(f"**Status:** {ui.badge('OPERANDO')} conectado", unsafe_allow_html=True)
        c[1].markdown(f"**Servidor:** `{_host_mascarado()}`")
        usuario = re.search(r"//([^:.@]+)", db._database_url() or "")
        c[2].markdown(f"**Usuário:** `{usuario.group(1) if usuario else '—'}` · painel executa apenas "
                      "consultas SELECT · senha fora do código (secrets)")
        p = db.pulso().iloc[0]
        ui.nota(f"Hora do servidor PostgreSQL: {p['agora_banco']} · "
                f"lotes de produção nos últimos 5 min: {int(p['producao_5min'])}")

    st.markdown("#### As seis tabelas")
    cont = db.contagens()
    cols = st.columns(6)
    for col, (_, r) in zip(cols, cont.iterrows()):
        col.metric(r["tabela"], ui.fint(r["registros"]))

    st.markdown("#### Relacionamentos")
    st.code("""machines (machine_id PK)
 ├──< production_events.machine_id      (1 máquina → N lotes de produção)
 │        └──< sales_orders.batch_id     (1 lote → 0..N pedidos de venda)
 ├──< machine_telemetry.machine_id      (1 máquina → milhares de leituras)
 ├──< wear_events.machine_id            (histórico de medições de desgaste)
 └──< parts_wear.machine_id             (estado ATUAL: 1 linha por máquina+componente)""", language="text")
    fks = db.chaves_estrangeiras()
    if not fks.empty:
        ui.tabela(fks.drop_duplicates())

    st.markdown("#### Campos e tipos de dados")
    colunas = db.colunas()
    tab = st.tabs(db.TABELAS)
    for t, nome in zip(tab, db.TABELAS):
        with t:
            ui.tabela(colunas[colunas["tabela"] == nome].drop(columns="tabela"))
            st.caption("Registros mais recentes:")
            st.dataframe(db.amostra(nome, 8), use_container_width=True, hide_index=True)

    st.markdown("#### 🔴 Chegada de dados em tempo real")
    ultimas = db.amostra("machine_telemetry", 12)
    if not ultimas.empty:
        ultimas["recorded_at"] = (pd.to_datetime(ultimas["recorded_at"], utc=True)
                                  .dt.tz_convert(BR_TZ).dt.strftime("%d/%m %H:%M:%S"))
    st.dataframe(ultimas, use_container_width=True, hide_index=True)
    ui.nota("Com o simulador ligado, novas linhas aparecem aqui a cada ~5 s sem recarregar a página. "
            "Mecanismo: polling (st.fragment com run_every) + cache de poucos segundos.")

    st.markdown("#### Consultas SQL utilizadas")
    for nome, sql in db.SQL.items():
        with st.expander(nome):
            st.code(sql.strip(), language="sql")
