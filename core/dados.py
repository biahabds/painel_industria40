"""Ponte entre banco, tratamento e filtros: cada página pede só o que precisa."""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime

import pandas as pd

from core import db
from core import transform as T


@dataclass
class Contexto:
    ini: datetime
    fim: datetime
    maquinas: list = field(default_factory=list)
    produtos: list = field(default_factory=list)
    turnos: list = field(default_factory=list)
    canais: list = field(default_factory=list)
    regioes: list = field(default_factory=list)

    @property
    def bucket_sql(self) -> str:
        horas = (self.fim - self.ini).total_seconds() / 3600
        if horas <= 2:
            return "1 minute"
        if horas <= 12:
            return "5 minutes"
        if horas <= 48:
            return "15 minutes"
        if horas <= 24 * 10:
            return "1 hour"
        return "6 hours"

    @property
    def freq_pandas(self) -> str:
        horas = (self.fim - self.ini).total_seconds() / 3600
        if horas <= 3:
            return "10min"
        if horas <= 48:
            return "1h"
        if horas <= 24 * 10:
            return "6h"
        return "1D"


def maquinas() -> pd.DataFrame:
    return T.tratar_maquinas(db.maquinas())


def producao(ctx: Contexto, filtrar=True) -> pd.DataFrame:
    df = T.tratar_producao(db.producao(ctx.ini, ctx.fim), maquinas())
    if filtrar:
        df = T.aplicar_filtros(df, ctx.maquinas, ctx.produtos, ctx.turnos)
    return df


def vendas(ctx: Contexto) -> pd.DataFrame:
    prod_total = producao(ctx, filtrar=False)  # relacionamento por batch_id usa todos os lotes
    df = T.tratar_vendas(db.vendas(ctx.ini, ctx.fim), prod_total)
    return T.aplicar_filtros(df, ctx.maquinas, ctx.produtos, ctx.turnos, ctx.canais,
                             ctx.regioes, col_turno="turno_lote")


def telemetria_resumo(ctx: Contexto) -> pd.DataFrame:
    df = T.tratar_telemetria(db.telemetria_resumo(ctx.ini, ctx.fim), maquinas())
    return T.aplicar_filtros(df, ctx.maquinas)


def telemetria_serie(ctx: Contexto) -> pd.DataFrame:
    df = T.tratar_telemetria(db.telemetria_serie(ctx.ini, ctx.fim, ctx.bucket_sql), maquinas())
    return T.aplicar_filtros(df, ctx.maquinas)


def telemetria_ultima(ctx: Contexto) -> pd.DataFrame:
    df = T.tratar_telemetria(db.telemetria_ultima(), maquinas())
    return T.aplicar_filtros(df, ctx.maquinas)


def desgaste_atual(ctx: Contexto) -> pd.DataFrame:
    return T.aplicar_filtros(T.tratar_desgaste_atual(db.desgaste_atual(), maquinas()), ctx.maquinas)


def desgaste_historico(ctx: Contexto) -> pd.DataFrame:
    df = T.tratar_historico_desgaste(db.desgaste_historico(ctx.ini, ctx.fim, ctx.bucket_sql),
                                     maquinas())
    return T.aplicar_filtros(df, ctx.maquinas)
