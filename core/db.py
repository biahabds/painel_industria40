"""Conexão com o PostgreSQL do Supabase e consultas SQL.

- A string de conexão vem de st.secrets["DATABASE_URL"] ou da variável de
  ambiente DATABASE_URL (nunca fica no código).
- Consultas pesadas (telemetria, histórico de desgaste) são AGREGADAS no
  próprio banco (GROUP BY / date_bin / DISTINCT ON) para trafegar pouco dado.
- Resultados ficam em cache por poucos segundos (st.cache_data com ttl), o que
  combina com a atualização automática por polling.
"""
from __future__ import annotations

import os
import time

import pandas as pd
import streamlit as st
from sqlalchemy import create_engine, text
from sqlalchemy.exc import SQLAlchemyError

TABELAS = ["machines", "production_events", "sales_orders",
           "machine_telemetry", "wear_events", "parts_wear"]


class ErroBanco(Exception):
    """Erro amigável de conexão/consulta."""


def _database_url() -> str | None:
    try:
        url = st.secrets.get("DATABASE_URL")  # Streamlit Cloud / .streamlit/secrets.toml
    except Exception:
        url = None
    return url or os.getenv("DATABASE_URL")


@st.cache_resource(show_spinner=False)
def get_engine():
    url = _database_url()
    if not url:
        raise ErroBanco(
            "DATABASE_URL não configurada. Crie .streamlit/secrets.toml (veja o exemplo) "
            "ou defina a variável de ambiente DATABASE_URL.")
    return create_engine(
        url,
        pool_pre_ping=True,      # testa a conexão antes de usar (evita conexões mortas)
        pool_size=2, max_overflow=1, pool_recycle=300,
        connect_args={"connect_timeout": 10, "sslmode": "require"},
    )


def consultar(sql: str, params: dict | None = None, tentativas: int = 2) -> pd.DataFrame:
    """Executa SQL somente-leitura e devolve DataFrame; tenta de novo uma vez em falha."""
    ultimo_erro = None
    for i in range(tentativas):
        try:
            with get_engine().connect() as conn:
                return pd.read_sql(text(sql), conn, params=params or {})
        except SQLAlchemyError as e:
            ultimo_erro = e
            time.sleep(0.8 * (i + 1))
    raise ErroBanco(f"Falha ao consultar o Supabase: {type(ultimo_erro).__name__}: "
                    f"{str(ultimo_erro).splitlines()[0][:220]}")


# ---------------------------------------------------------------------------
# Consultas (o texto SQL fica em constantes para ser exibido na página "Dados")
# ---------------------------------------------------------------------------
SQL = {
    "maquinas": "SELECT * FROM public.machines ORDER BY machine_code",

    "producao": """
        SELECT * FROM public.production_events
        WHERE ended_at >= :ini AND ended_at < :fim
        ORDER BY ended_at""",

    "vendas": """
        SELECT * FROM public.sales_orders
        WHERE created_at >= :ini AND created_at < :fim
        ORDER BY created_at""",

    "telemetria_resumo": """
        SELECT m.machine_code,
               COUNT(*)                         AS n_leituras,
               AVG(t.temperature_c)             AS temp_media,
               MAX(t.temperature_c)             AS temp_max,
               AVG(t.vibration_mm_s)            AS vib_media,
               MAX(t.vibration_mm_s)            AS vib_max,
               AVG(t.energy_kw)                 AS energia_media_kw,
               AVG(t.pressure_bar)              AS pressao_media,
               AVG(t.rpm)                       AS rpm_medio,
               SUM(CASE WHEN t.machine_status = 'ATENCAO' THEN 1 ELSE 0 END) AS n_atencao,
               SUM(CASE WHEN t.machine_status = 'CRITICO' THEN 1 ELSE 0 END) AS n_critico
        FROM public.machine_telemetry t
        JOIN public.machines m ON m.machine_id = t.machine_id
        WHERE t.recorded_at >= :ini AND t.recorded_at < :fim
        GROUP BY m.machine_code
        ORDER BY m.machine_code""",

    "telemetria_serie": """
        SELECT m.machine_code,
               date_bin(CAST(:bucket AS interval), t.recorded_at, TIMESTAMPTZ '2000-01-01') AS bucket,
               AVG(t.temperature_c)  AS temperature_c,
               AVG(t.vibration_mm_s) AS vibration_mm_s,
               AVG(t.energy_kw)      AS energy_kw,
               AVG(t.pressure_bar)   AS pressure_bar,
               AVG(t.rpm)            AS rpm
        FROM public.machine_telemetry t
        JOIN public.machines m ON m.machine_id = t.machine_id
        WHERE t.recorded_at >= :ini AND t.recorded_at < :fim
        GROUP BY 1, 2
        ORDER BY 2""",

    "telemetria_ultima": """
        SELECT DISTINCT ON (t.machine_id)
               m.machine_code, m.machine_name, t.temperature_c, t.vibration_mm_s,
               t.energy_kw, t.pressure_bar, t.rpm, t.machine_status, t.recorded_at
        FROM public.machine_telemetry t
        JOIN public.machines m ON m.machine_id = t.machine_id
        ORDER BY t.machine_id, t.recorded_at DESC""",

    "desgaste_atual": "SELECT * FROM public.parts_wear",

    "desgaste_historico": """
        SELECT machine_id, component_code, component_name,
               date_bin(CAST(:bucket AS interval), measured_at, TIMESTAMPTZ '2000-01-01') AS measured_at,
               MAX(wear_pct)                  AS wear_pct,
               MIN(estimated_remaining_hours) AS estimated_remaining_hours
        FROM public.wear_events
        WHERE measured_at >= :ini AND measured_at < :fim
        GROUP BY 1, 2, 3, 4
        ORDER BY 4""",

    "pulso": """
        SELECT
          (SELECT MAX(recorded_at) FROM public.machine_telemetry) AS ultima_telemetria,
          (SELECT COUNT(*) FROM public.machine_telemetry
             WHERE recorded_at > now() - interval '1 minute')      AS telemetria_1min,
          (SELECT MAX(ended_at) FROM public.production_events)     AS ultima_producao,
          (SELECT COUNT(*) FROM public.production_events
             WHERE recorded_at > now() - interval '5 minutes')     AS producao_5min,
          (SELECT MAX(created_at) FROM public.sales_orders)        AS ultima_venda,
          (SELECT MAX(measured_at) FROM public.wear_events)        AS ultimo_desgaste,
          now() AS agora_banco""",

    "contagens": """
        SELECT 'machines' AS tabela, COUNT(*) AS registros FROM public.machines
        UNION ALL SELECT 'production_events', COUNT(*) FROM public.production_events
        UNION ALL SELECT 'sales_orders', COUNT(*) FROM public.sales_orders
        UNION ALL SELECT 'machine_telemetry', COUNT(*) FROM public.machine_telemetry
        UNION ALL SELECT 'wear_events', COUNT(*) FROM public.wear_events
        UNION ALL SELECT 'parts_wear', COUNT(*) FROM public.parts_wear""",

    "colunas": """
        SELECT table_name AS tabela, column_name AS coluna, data_type AS tipo,
               is_nullable AS aceita_nulo
        FROM information_schema.columns
        WHERE table_schema = 'public' AND table_name IN :tabelas
        ORDER BY table_name, ordinal_position""",

    "chaves_estrangeiras": """
        SELECT tc.table_name AS tabela, kcu.column_name AS coluna,
               ccu.table_name AS referencia, ccu.column_name AS coluna_referencia
        FROM information_schema.table_constraints tc
        JOIN information_schema.key_column_usage kcu
          ON tc.constraint_name = kcu.constraint_name AND tc.table_schema = kcu.table_schema
        JOIN information_schema.constraint_column_usage ccu
          ON ccu.constraint_name = tc.constraint_name AND ccu.table_schema = tc.table_schema
        WHERE tc.constraint_type = 'FOREIGN KEY' AND tc.table_schema = 'public'""",
}


@st.cache_data(ttl=60, show_spinner=False)
def maquinas():
    return consultar(SQL["maquinas"])


@st.cache_data(ttl=8, show_spinner=False)
def producao(ini, fim):
    return consultar(SQL["producao"], {"ini": ini, "fim": fim})


@st.cache_data(ttl=8, show_spinner=False)
def vendas(ini, fim):
    return consultar(SQL["vendas"], {"ini": ini, "fim": fim})


@st.cache_data(ttl=8, show_spinner=False)
def telemetria_resumo(ini, fim):
    return consultar(SQL["telemetria_resumo"], {"ini": ini, "fim": fim})


@st.cache_data(ttl=8, show_spinner=False)
def telemetria_serie(ini, fim, bucket):
    return consultar(SQL["telemetria_serie"], {"ini": ini, "fim": fim, "bucket": bucket})


@st.cache_data(ttl=4, show_spinner=False)
def telemetria_ultima():
    return consultar(SQL["telemetria_ultima"])


@st.cache_data(ttl=8, show_spinner=False)
def desgaste_atual():
    return consultar(SQL["desgaste_atual"])


@st.cache_data(ttl=15, show_spinner=False)
def desgaste_historico(ini, fim, bucket):
    return consultar(SQL["desgaste_historico"], {"ini": ini, "fim": fim, "bucket": bucket})


@st.cache_data(ttl=4, show_spinner=False)
def pulso():
    return consultar(SQL["pulso"])


@st.cache_data(ttl=30, show_spinner=False)
def contagens():
    return consultar(SQL["contagens"])


@st.cache_data(ttl=600, show_spinner=False)
def colunas():
    from sqlalchemy import bindparam
    sql = text(SQL["colunas"]).bindparams(bindparam("tabelas", expanding=True))
    with get_engine().connect() as conn:
        return pd.read_sql(sql, conn, params={"tabelas": TABELAS})


@st.cache_data(ttl=600, show_spinner=False)
def chaves_estrangeiras():
    return consultar(SQL["chaves_estrangeiras"])


@st.cache_data(ttl=600, show_spinner=False)
def opcoes_filtros() -> dict:
    """Valores distintos usados nos filtros (lidos do banco, não fixos no código)."""
    q = {
        "produtos": "SELECT DISTINCT product_name AS v FROM public.production_events ORDER BY 1",
        "turnos": "SELECT DISTINCT shift_name AS v FROM public.production_events ORDER BY 1",
        "canais": "SELECT DISTINCT sales_channel AS v FROM public.sales_orders ORDER BY 1",
        "regioes": "SELECT DISTINCT customer_region AS v FROM public.sales_orders ORDER BY 1",
    }
    return {k: [str(x).strip() for x in consultar(s)["v"].dropna()] for k, s in q.items()}


@st.cache_data(ttl=30, show_spinner=False)
def amostra(tabela: str, n: int = 10):
    if tabela not in TABELAS:  # proteção contra SQL injection: só nomes conhecidos
        raise ErroBanco("Tabela inválida")
    col_tempo = {"machines": "created_at", "production_events": "recorded_at",
                 "sales_orders": "created_at", "machine_telemetry": "recorded_at",
                 "wear_events": "measured_at", "parts_wear": "last_inspection_at"}[tabela]
    return consultar(f"SELECT * FROM public.{tabela} ORDER BY {col_tempo} DESC LIMIT :n", {"n": n})
