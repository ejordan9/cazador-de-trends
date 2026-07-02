"""Fuente: feed de noticias de medios vía RSS, con imágenes.

A diferencia de la app eReader (que lee RSS desde el navegador y necesita proxies
CORS), acá se lee server-side con requests → sin proxies. Extrae título, link,
medio e imagen (media:content / media:thumbnail / enclosure / <img> en el cuerpo).

Contrato: expone `fetch() -> SourceResult`. Nunca lanza hacia arriba; cada feed
falla aislado.
"""

from __future__ import annotations

import re
import sys
import xml.etree.ElementTree as ET
from pathlib import Path

import requests

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from contract import SourceResult, TrendItem, error_item, now_iso  # noqa: E402
import config  # noqa: E402

FUENTE = "Noticias"
RAW_DIR = Path(__file__).resolve().parent.parent / "output" / "raw"
NS = {
    "media": "http://search.yahoo.com/mrss/",
    "content": "http://purl.org/rss/1.0/modules/content/",
}
_IMG_RE = re.compile(r'<img[^>]+src=["\']([^"\']+)["\']', re.I)


def _save_raw(medio: str, xml_text: str) -> None:
    RAW_DIR.mkdir(parents=True, exist_ok=True)
    slug = re.sub(r"[^a-z0-9]+", "_", medio.lower()).strip("_")
    (RAW_DIR / f"noticias_{slug}_{now_iso()[:10]}.xml").write_text(xml_text, encoding="utf-8")


def _imagen_de(item: ET.Element) -> str | None:
    # media:content / media:thumbnail
    for tag in ("media:content", "media:thumbnail"):
        el = item.find(tag, NS)
        if el is not None and el.get("url"):
            return el.get("url")
    # enclosure tipo imagen
    enc = item.find("enclosure")
    if enc is not None and (enc.get("type", "").startswith("image") or
                            re.search(r"\.(jpg|jpeg|png|webp)", enc.get("url", ""), re.I)):
        return enc.get("url")
    # primer <img> dentro de content:encoded o description
    for tag in ("content:encoded", "description"):
        el = item.find(tag, NS) if ":" in tag else item.find(tag)
        if el is not None and el.text:
            m = _IMG_RE.search(el.text)
            if m:
                return m.group(1)
    return None


def _parse_feed(medio: str, xml_text: str) -> list[TrendItem]:
    root = ET.fromstring(xml_text)
    items: list[TrendItem] = []
    for orden, item in enumerate(root.iterfind(".//item"), start=1):
        titulo = (item.findtext("title") or "").strip()
        link = (item.findtext("link") or "").strip()
        if not titulo or not link:
            continue
        items.append(
            TrendItem(
                fuente=medio,
                tema=titulo,
                link=link,
                orden=orden,
                imagen=_imagen_de(item),
            )
        )
        if len(items) >= config.NOTICIAS_POR_FEED:
            break
    return items


def fetch() -> SourceResult:
    todos: list[TrendItem] = []
    caidos: list[str] = []
    feeds = config.NOTICIAS_FEEDS
    for medio, url in feeds.items():
        try:
            resp = requests.get(
                url,
                headers={"User-Agent": config.USER_AGENT},
                timeout=config.REQUEST_TIMEOUT,
            )
            resp.raise_for_status()
            _save_raw(medio, resp.text)
            todos.extend(_parse_feed(medio, resp.text))
        except (requests.RequestException, ET.ParseError) as exc:
            caidos.append(medio)
            it = error_item(FUENTE, f"{medio}: {exc}")
            it.grupo = medio
            todos.append(it)

    ok = len(caidos) < len(feeds) if feeds else False
    detalle = f"feeds caídos: {', '.join(caidos)}" if caidos else ""
    return SourceResult(fuente=FUENTE, items=todos, ok=ok, detalle=detalle)


if __name__ == "__main__":
    res = fetch()
    print(f"[{res.fuente}] ok={res.ok} items={len(res.items)} {res.detalle}")
    for it in res.items:
        img = "🖼" if it.imagen else "  "
        print(f"  {img} [{it.fuente}] {it.tema[:60]}")
