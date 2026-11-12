"""Formatação de números no padrão brasileiro (sem dependência do Streamlit)."""
import math


def _br(s: str) -> str:
    return s.replace(",", "X").replace(".", ",").replace("X", ".")


def _ok(v) -> bool:
    try:
        return v is not None and not math.isnan(float(v))
    except (TypeError, ValueError):
        return False


def fint(v) -> str:
    return _br(f"{float(v):,.0f}") if _ok(v) else "—"


def fnum(v, casas=1) -> str:
    return _br(f"{float(v):,.{casas}f}") if _ok(v) else "—"


def fbrl(v) -> str:
    return "R$ " + _br(f"{float(v):,.2f}") if _ok(v) else "—"


def fpct(v, casas=1) -> str:
    return _br(f"{float(v) * 100:,.{casas}f}") + "%" if _ok(v) else "—"
