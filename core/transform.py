"""Tratamento e organização dos dados com Pandas.

Este módulo NÃO depende do Streamlit: recebe os DataFrames vindos do banco
(Supabase/PostgreSQL), padroniza tipos, limpa textos, cria colunas derivadas
e faz os relacionamentos entre as tabelas.
"""
from __future__ import annotations

from datetime import timedelta, timezone

import numpy as np
import pandas as pd

BR_TZ = timezone(timedelta(hours=-3))  # Horário de Brasília

STATUS_CANCELADO = "CANCELADO"
ORDEM_TURNOS = ["MANHA", "TARDE", "NOITE"]
ORDEM_STATUS_MAQ = ["OPERANDO", "ATENCAO", "CRITICO"]


# ----------------------------------------------------------------------------
# Utilitários
# ----------------------------------------------------------------------------
def _to_br_datetime(df: pd.DataFrame, cols: list[str]) -> pd.DataFrame:
    for c in cols:
        if c in df.columns:
            df[c] = pd.to_datetime(df[c], utc=True, errors="coerce").dt.tz_convert(BR_TZ)
    return df


def _to_numeric(df: pd.DataFrame, cols: list[str]) -> pd.DataFrame:
    for c in cols:
        if c in df.columns:
            df[c] = pd.to_numeric(df[c], errors="coerce")
    return df


def _strip_text(df: pd.DataFrame, cols: list[str]) -> pd.DataFrame:
    """Remove espaços extras (ex.: machine_code ' CNC-01' no banco) e padroniza."""
    for c in cols:
        if c in df.columns:
            df[c] = df[c].astype("string").str.strip()
    return df


def _uuid_to_str(df: pd.DataFrame, cols: list[str]) -> pd.DataFrame:
    for c in cols:
        if c in df.columns:
            df[c] = df[c].astype(str)
    return df


def safe_div(a, b):
    """Divisão que devolve NaN em vez de erro/infinito quando o denominador é zero."""
    if isinstance(b, pd.Series):
        return a / b.replace(0, np.nan)
    if isinstance(b, np.ndarray):
        return a / np.where(b == 0, np.nan, b)
    if b is None or pd.isna(b) or b == 0:
        return a * np.nan if isinstance(a, pd.Series) else np.nan
    return a / b


# ----------------------------------------------------------------------------
# Tabelas
# ----------------------------------------------------------------------------
def tratar_maquinas(df: pd.DataFrame) -> pd.DataFrame:
    if df is None or df.empty:
        return pd.DataFrame(columns=["machine_id", "machine_code", "machine_name",
                                     "production_line", "machine_type",
                                     "nominal_capacity_per_hour", "machine_status"])
    df = df.copy()
    _uuid_to_str(df, ["machine_id"])
    _strip_text(df, ["machine_code", "machine_name", "production_line",
                     "machine_type", "machine_status"])
    _to_numeric(df, ["nominal_capacity_per_hour"])
    _to_br_datetime(df, ["created_at"])
    df["installed_at"] = pd.to_datetime(df.get("installed_at"), errors="coerce")
    return df.sort_values("machine_code").reset_index(drop=True)


def tratar_producao(df: pd.DataFrame, maquinas: pd.DataFrame) -> pd.DataFrame:
    """production_events + machines (machine_id) + colunas derivadas."""
    if df is None or df.empty:
        return pd.DataFrame()
    df = df.copy()
    _uuid_to_str(df, ["batch_id", "machine_id"])
    _strip_text(df, ["product_code", "product_name", "shift_name"])
    _to_numeric(df, ["qty_produced", "qty_rejected", "downtime_minutes",
                     "cycle_time_seconds", "energy_kwh", "unit_cost"])
    _to_br_datetime(df, ["started_at", "ended_at", "recorded_at"])

    cols_maq = ["machine_id", "machine_code", "machine_name", "production_line",
                "machine_type", "nominal_capacity_per_hour"]
    df = df.merge(maquinas[[c for c in cols_maq if c in maquinas.columns]],
                  on="machine_id", how="left")
    df["machine_code"] = df["machine_code"].fillna("SEM CADASTRO")

    # Colunas derivadas
    df["qty_approved"] = df["qty_produced"] - df["qty_rejected"]
    df["duracao_min"] = (df["ended_at"] - df["started_at"]).dt.total_seconds() / 60
    df["tempo_operando_min"] = (df["duracao_min"] - df["downtime_minutes"]).clip(lower=0.1)
    df["custo_producao"] = df["qty_produced"] * df["unit_cost"]
    df["custo_rejeitados"] = df["qty_rejected"] * df["unit_cost"]
    df["hora"] = df["ended_at"].dt.hour
    df["data"] = df["ended_at"].dt.floor("D")

    # Indicadores tipo OEE (estimados)
    df["disponibilidade"] = safe_div(df["tempo_operando_min"], df["duracao_min"])
    capacidade_no_tempo = df["nominal_capacity_per_hour"] * df["tempo_operando_min"] / 60
    df["desempenho"] = safe_div(df["qty_produced"], capacidade_no_tempo).clip(upper=1.5)
    df["qualidade"] = safe_div(df["qty_approved"], df["qty_produced"])
    df["oee"] = df["disponibilidade"] * df["desempenho"].clip(upper=1) * df["qualidade"]
    return df


def tratar_vendas(df: pd.DataFrame, producao: pd.DataFrame) -> pd.DataFrame:
    """sales_orders + production_events (batch_id) → máquina, turno e custo do lote."""
    if df is None or df.empty:
        return pd.DataFrame()
    df = df.copy()
    _uuid_to_str(df, ["batch_id"])
    _strip_text(df, ["order_number", "product_code", "product_name", "sales_channel",
                     "order_status", "customer_region"])
    df["order_status"] = df["order_status"].str.upper()
    _to_numeric(df, ["qty_sold", "unit_price", "total_amount"])
    _to_br_datetime(df, ["created_at"])
    df["valido"] = df["order_status"] != STATUS_CANCELADO
    df["receita_valida"] = np.where(df["valido"], df["total_amount"], 0.0)
    df["qtd_valida"] = np.where(df["valido"], df["qty_sold"], 0)
    df["hora"] = df["created_at"].dt.hour
    df["data"] = df["created_at"].dt.floor("D")

    # Relacionamento pedido → lote de produção
    if producao is not None and not producao.empty:
        lote = producao[["batch_id", "machine_code", "shift_name", "unit_cost"]].rename(
            columns={"shift_name": "turno_lote", "unit_cost": "custo_unit_lote"})
        df = df.merge(lote, on="batch_id", how="left")
        # Custo médio ponderado por produto (fallback quando o lote está fora do período)
        cmp = (producao.groupby("product_code")
               .apply(lambda g: safe_div((g["unit_cost"] * g["qty_produced"]).sum(),
                                         g["qty_produced"].sum()), include_groups=False)
               .rename("custo_medio_produto"))
        df = df.merge(cmp, left_on="product_code", right_index=True, how="left")
        df["custo_unit_estimado"] = df["custo_unit_lote"].fillna(df["custo_medio_produto"])
    else:
        df["machine_code"] = pd.NA
        df["turno_lote"] = pd.NA
        df["custo_unit_estimado"] = np.nan
    df["cpv_estimado"] = np.where(df["valido"], df["qty_sold"] * df["custo_unit_estimado"], 0.0)
    return df


def tratar_telemetria(df: pd.DataFrame, maquinas: pd.DataFrame) -> pd.DataFrame:
    if df is None or df.empty:
        return pd.DataFrame()
    df = df.copy()
    _uuid_to_str(df, ["machine_id"])
    _strip_text(df, ["machine_status"])
    _to_numeric(df, ["temperature_c", "vibration_mm_s", "energy_kw", "pressure_bar", "rpm",
                     "n_leituras", "n_atencao", "n_critico", "temp_media", "temp_max",
                     "vib_media", "vib_max", "energia_media_kw", "pressao_media", "rpm_medio"])
    _to_br_datetime(df, ["recorded_at", "bucket"])
    if "machine_code" not in df.columns:
        df = df.merge(maquinas[["machine_id", "machine_code"]], on="machine_id", how="left")
    else:
        _strip_text(df, ["machine_code"])
    return df


def tratar_desgaste_atual(df: pd.DataFrame, maquinas: pd.DataFrame) -> pd.DataFrame:
    """parts_wear: estado atual + classificação visual."""
    if df is None or df.empty:
        return pd.DataFrame()
    df = df.copy()
    _uuid_to_str(df, ["machine_id"])
    _strip_text(df, ["component_code", "component_name"])
    _to_numeric(df, ["wear_pct", "warning_threshold_pct", "critical_threshold_pct",
                     "estimated_remaining_hours"])
    _to_br_datetime(df, ["last_inspection_at"])
    df = df.merge(maquinas[["machine_id", "machine_code", "production_line"]],
                  on="machine_id", how="left")
    df["warning_threshold_pct"] = df["warning_threshold_pct"].fillna(75)
    df["critical_threshold_pct"] = df["critical_threshold_pct"].fillna(90)
    df["situacao"] = np.select(
        [df["wear_pct"] >= df["critical_threshold_pct"],
         df["wear_pct"] >= df["warning_threshold_pct"]],
        ["CRÍTICO", "ATENÇÃO"], default="NORMAL")
    df["componente"] = df["machine_code"].astype(str) + " · " + df["component_name"].astype(str)
    # Mais desgastado primeiro; em empate, o que tem menos horas restantes.
    return df.sort_values(["wear_pct", "estimated_remaining_hours"],
                          ascending=[False, True], na_position="last").reset_index(drop=True)


def tratar_historico_desgaste(df: pd.DataFrame, maquinas: pd.DataFrame) -> pd.DataFrame:
    if df is None or df.empty:
        return pd.DataFrame()
    df = df.copy()
    _uuid_to_str(df, ["machine_id"])
    _strip_text(df, ["component_code", "component_name"])
    _to_numeric(df, ["wear_pct", "estimated_remaining_hours", "vibration_mm_s", "temperature_c"])
    _to_br_datetime(df, ["measured_at", "bucket"])
    df = df.merge(maquinas[["machine_id", "machine_code"]], on="machine_id", how="left")
    df["componente"] = df["machine_code"].astype(str) + " · " + df["component_name"].astype(str)
    return df


# ----------------------------------------------------------------------------
# Filtros
# ----------------------------------------------------------------------------
def aplicar_filtros(df: pd.DataFrame, maquinas=None, produtos=None, turnos=None,
                    canais=None, regioes=None, col_maquina="machine_code",
                    col_turno="shift_name") -> pd.DataFrame:
    """Aplica filtros multiseleção; lista vazia/None = sem filtro."""
    if df is None or df.empty:
        return df if df is not None else pd.DataFrame()
    m = pd.Series(True, index=df.index)
    if maquinas and col_maquina in df.columns:
        m &= df[col_maquina].isin(maquinas)
    if produtos and "product_name" in df.columns:
        m &= df["product_name"].isin(produtos)
    if turnos and col_turno in df.columns:
        m &= df[col_turno].isin(turnos)
    if canais and "sales_channel" in df.columns:
        m &= df["sales_channel"].isin(canais)
    if regioes and "customer_region" in df.columns:
        m &= df["customer_region"].isin(regioes)
    return df[m]
