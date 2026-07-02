"""Fuente: Google Trends (búsquedas en tendencia) vía RSS.

Usa el feed oficial `trends.google.com/trending/rss?geo=CL`. Es mucho más estable
que pytrends (que se rompe seguido con cambios de Google) y no requiere API key.

Contrato: expone `fetch() -> SourceResult`. Nunca lanza hacia arriba; si falla,
devuelve ok=False con un item de error visible (aislamiento de fallos).
"""

from __future__ import annotations

import sys
import xml.etree.ElementTree as ET
from pathlib import Path
from urllib.parse import quote

import requests

# permite correr este archivo standalone (python sources/google_trends.py)
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from contract import SourceResult, TrendItem, error_item, now_iso  # noqa: E402
import config  # noqa: E402

FUENTE = "Google Trends Chile"
RAW_DIR = Path(__file__).resolve().parent.parent / "output" / "raw"

# namespace de los tags ht: del feed
NS = {"ht": "https://trends.google.com/trending/rss"}


def _google_link(tema: str) -> str:
    """Link a la búsqueda en Google: lleva a ver de qué trata el tema."""
    return f"https://www.google.com/search?q={quote(tema)}"


def _save_raw(xml_text: str) -> None:
    RAW_DIR.mkdir(parents=True, exist_ok=True)
    fecha = now_iso()[:10]
    (RAW_DIR / f"google_trends_{fecha}.xml").write_text(xml_text, encoding="utf-8")


def _es_sensible(tema: str) -> bool:
    t = tema.lower()
    return any(kw in t for kw in config.KEYWORDS_SENSIBLES)


def _parse(xml_text: str) -> list[TrendItem]:
    root = ET.fromstring(xml_text)
    items: list[TrendItem] = []
    for orden, item in enumerate(root.iterfind(".//item"), start=1):
        titulo = item.findtext("title")
        if not titulo:
            continue
        tema = titulo.strip()
        traffic = item.findtext("ht:approx_traffic", namespaces=NS)
        items.append(
            TrendItem(
                fuente=FUENTE,
                tema=tema,
                link=_google_link(tema),
                volumen=traffic.strip() if traffic else None,
                orden=orden,
                sensible=_es_sensible(tema),
            )
        )
    return items


def fetch() -> SourceResult:
    url = f"https://trends.google.com/trending/rss?geo={config.GOOGLE_TRENDS_GEO}"
    try:
        resp = requests.get(
            url,
            headers={"User-Agent": config.USER_AGENT},
            timeout=config.REQUEST_TIMEOUT,
        )
        resp.raise_for_status()
        _save_raw(resp.text)
        items = _parse(resp.text)
        if not items:
            return SourceResult(
                fuente=FUENTE,
                items=[error_item(FUENTE, "0 trends parseados (¿cambió el feed?)")],
                ok=False,
                detalle="parseo vacío",
            )
        return SourceResult(fuente=FUENTE, items=items, ok=True)
    except requests.RequestException as exc:
        return SourceResult(
            fuente=FUENTE,
            items=[error_item(FUENTE, str(exc))],
            ok=False,
            detalle=str(exc),
        )
    except ET.ParseError as exc:
        return SourceResult(
            fuente=FUENTE,
            items=[error_item(FUENTE, f"XML inválido: {exc}")],
            ok=False,
            detalle=str(exc),
        )


if __name__ == "__main__":
    res = fetch()
    print(f"[{res.fuente}] ok={res.ok} items={len(res.items)}")
    for it in res.items:
        flag = " 🔶SENSIBLE" if it.sensible else ""
        vol = f" ({it.volumen})" if it.volumen else ""
        print(f"  {it.orden:>2}. {it.tema}{vol}{flag}  -> {it.link}")
