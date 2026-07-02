"""Fuente: trends de X (Twitter) en Chile vía getdaytrends.com.

Scraping de página pública, SIN API key (la API oficial de X ya no tiene tier
gratuito útil — ver sección 6 del plan).

Contrato: expone `fetch() -> SourceResult`. Nunca lanza excepción hacia arriba;
si el scraping falla, devuelve un SourceResult con ok=False para que el tablero
siga mostrando el resto de fuentes (aislamiento de fallos).
"""

from __future__ import annotations

import sys
from pathlib import Path
from urllib.parse import quote

import requests
from bs4 import BeautifulSoup

# permite correr este archivo standalone (python sources/x_chile.py)
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from contract import SourceResult, TrendItem, error_item, now_iso  # noqa: E402
import config  # noqa: E402

FUENTE = "X Chile"
RAW_DIR = Path(__file__).resolve().parent.parent / "output" / "raw"


def _x_search_link(tema: str) -> str:
    """Link a la búsqueda del tema en X: lleva directo a la conversación,
    que es lo que el analista necesita para redactar contexto."""
    return f"https://x.com/search?q={quote(tema)}&src=trend_click"


def _save_raw(html: str) -> None:
    """Guarda el HTML crudo de la corrida. Cuando el scraper se rompa en el
    futuro, se puede ver qué cambió sin volver a pedir la página."""
    RAW_DIR.mkdir(parents=True, exist_ok=True)
    fecha = now_iso()[:10]
    (RAW_DIR / f"x_chile_{fecha}.html").write_text(html, encoding="utf-8")


def _es_sensible(tema: str) -> bool:
    t = tema.lower()
    return any(kw in t for kw in config.KEYWORDS_SENSIBLES)


def _parse(html: str) -> list[TrendItem]:
    soup = BeautifulSoup(html, "html.parser")
    items: list[TrendItem] = []
    vistos: set[str] = set()  # dedup entre la tabla visible y la colapsada

    for tabla in soup.select("table.trends"):
        for fila in tabla.find_all("tr"):
            enlace = fila.select_one("td.main a")
            if not enlace:
                continue
            tema = enlace.get_text(strip=True)
            if not tema or tema in vistos:
                continue
            vistos.add(tema)

            pos_celda = fila.select_one("th.pos")
            try:
                orden = int(pos_celda.get_text(strip=True)) if pos_celda else None
            except ValueError:
                orden = None

            items.append(
                TrendItem(
                    fuente=FUENTE,
                    tema=tema,
                    link=_x_search_link(tema),
                    volumen=None,  # no disponible en la página de listado
                    orden=orden,
                    sensible=_es_sensible(tema),
                )
            )

    items.sort(key=lambda it: it.orden if it.orden is not None else 9999)
    return items[: config.X_TOP_N]


def fetch() -> SourceResult:
    url = f"https://getdaytrends.com/es/{config.X_PAIS}/"
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
                items=[error_item(FUENTE, "0 trends parseados (¿cambió el HTML?)")],
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


if __name__ == "__main__":
    res = fetch()
    print(f"[{res.fuente}] ok={res.ok} items={len(res.items)}")
    for it in res.items:
        flag = " 🔶SENSIBLE" if it.sensible else ""
        print(f"  {it.orden:>2}. {it.tema}{flag}  -> {it.link}")
