"""Fuente: efemérides de la semana vía Wikipedia "On this day" (español).

Para hoy + los siguientes días (config.EFEMERIDES_DIAS) trae:
  - eventos notables ("tal día como hoy salió/ocurrió…")  -> endpoint `selected`
  - días conmemorativos ("Día de…")                       -> endpoint `holidays`
Sin API key. Cada item se entrega como TrendItem con `grupo` = etiqueta del día.

Contrato: expone `fetch() -> SourceResult`. Nunca lanza hacia arriba.
"""

from __future__ import annotations

import re
import sys
from datetime import date, timedelta
from pathlib import Path

import requests

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from contract import SourceResult, TrendItem, error_item  # noqa: E402
import config  # noqa: E402

FUENTE = "Efemérides"
BASE = "https://es.wikipedia.org/api/rest_v1/feed/onthisday"
DIAS_ES = ["lunes", "martes", "miércoles", "jueves", "viernes", "sábado", "domingo"]
MESES_ES = ["", "ene", "feb", "mar", "abr", "may", "jun", "jul", "ago", "sep", "oct", "nov", "dic"]


def _etiqueta_dia(d: date, es_hoy: bool) -> str:
    if es_hoy:
        return f"Hoy · {d.day:02d}/{d.month:02d}"
    return f"{DIAS_ES[d.weekday()]} {d.day:02d}/{d.month:02d}"


def _get(tipo: str, d: date) -> list[dict]:
    url = f"{BASE}/{tipo}/{d.month:02d}/{d.day:02d}"
    resp = requests.get(
        url,
        headers={"User-Agent": config.USER_AGENT},
        timeout=config.REQUEST_TIMEOUT,
    )
    resp.raise_for_status()
    data = resp.json()
    return data.get(tipo) or data.get("selected") or []


def _thumb(entry: dict) -> str | None:
    for page in entry.get("pages", []) or []:
        th = page.get("thumbnail") or {}
        if th.get("source"):
            return th["source"]
    return None


def _link(entry: dict) -> str:
    for page in entry.get("pages", []) or []:
        url = (page.get("content_urls", {}).get("desktop", {}) or {}).get("page")
        if url:
            return url
    return ""


def fetch() -> SourceResult:
    items: list[TrendItem] = []
    hoy = date.today()
    fallos = 0
    for i in range(config.EFEMERIDES_DIAS):
        d = hoy + timedelta(days=i)
        etiqueta = _etiqueta_dia(d, es_hoy=(i == 0))
        try:
            eventos = _get("selected", d)[: config.EFEMERIDES_EVENTOS]
            for e in eventos:
                anio = e.get("year")
                items.append(
                    TrendItem(
                        fuente=str(anio) if anio else "evento",
                        tema=(e.get("text") or "").strip(),
                        link=_link(e),
                        grupo=etiqueta,
                        imagen=_thumb(e),
                    )
                )
            conmemora = _get("holidays", d)[: config.EFEMERIDES_CONMEMORA]
            for c in conmemora:
                texto = (c.get("text") or "").strip().replace("\n", " ")
                # viene como "Día de X.Descripción…" o "Naciones Unidas: Día de X…"
                m = re.search(r"(Día[^.]*)", texto)
                corto = (m.group(1) if m else texto.split(".")[0]).strip()
                items.append(
                    TrendItem(
                        fuente="conmemoración",
                        tema=corto or texto,
                        link=_link(c),
                        grupo=etiqueta,
                    )
                )
        except (requests.RequestException, ValueError) as exc:
            fallos += 1
            it = error_item(FUENTE, f"{etiqueta}: {exc}")
            it.grupo = etiqueta
            items.append(it)

    ok = fallos < config.EFEMERIDES_DIAS
    return SourceResult(fuente=FUENTE, items=items, ok=ok)


if __name__ == "__main__":
    res = fetch()
    print(f"[{res.fuente}] ok={res.ok} items={len(res.items)}")
    grupo = None
    for it in res.items:
        if it.grupo != grupo:
            grupo = it.grupo
            print(f"  ── {grupo} ──")
        print(f"     {it.fuente}: {it.tema[:70]}")
