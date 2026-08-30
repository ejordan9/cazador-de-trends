"""Configuración editable sin tocar la lógica.

Edita este archivo para ajustar país, subreddits, top-N y la lista de keywords
sensibles. La idea (auditoría): iterar la lista de monitoreo sin meter mano al
código de scraping.
"""

from pathlib import Path

# --- X / getdaytrends ---
X_PAIS = "chile"          # slug del país en getdaytrends.com/es/<pais>/
X_TOP_N = 10              # top 10 trends de X Chile (equilibra el layout)

# --- Reddit ---
# Cada entrada es un feed `hot.rss`. Se puede combinar varios subreddits en uno
# solo con `+` (multireddit): una request para todos -> menos tiempo y menos 429.
# El RSS de Reddit limita a ~1 request/12s, así que menos entradas = más rápido.
#
# Estrategia HÍBRIDA: lo relevante para el trabajo (Chile, Marketing, OutOfTheLoop)
# va separado con cuota garantizada; subs de escala parecida se agrupan para
# ahorrar requests. Total ~5 requests ≈ 1 min.
#
# Formato: {etiqueta de grupo: query de subreddit(s)}. La etiqueta es lo que se
# muestra como encabezado en el tablero; dentro, los posts se agrupan por su
# subreddit real. Varios subs en un valor se combinan con `+` (multireddit).
SUBREDDITS = {
    "Chile": "chile+RepublicaDeChile+FutbolChileno",
    "Marketing": "Marketing",
    "Out of the Loop": "OutOfTheLoop",
    "Viral": "memes+TikTokCringe",
    "Cultura & Generaciones": "GenZ+Millennials+popculturechat",
}

# --- Google Trends (Fase 1.3, vía RSS, aún no implementada) ---
GOOGLE_TRENDS_GEO = "CL"

# --- Feed de noticias (RSS de medios, leído server-side, con imágenes) ---
NOTICIAS_FEEDS = {
    "Think with Google": "https://www.thinkwithgoogle.com/rss.xml",
    "La Criatura Creativa": "https://lacriaturacreativa.com/feed/",
    "JF Digital": "https://jfdigital.es/feed/",
    "Puro Merca": "https://puromerca.com/feed/",
    "Mercado Negro PE": "https://www.mercadonegro.pe/feed/",
    "RoastBrief": "https://roastbrief.com.mx/feed/",
}
NOTICIAS_POR_FEED = 4   # cuántas noticias traer por medio

# --- Efemérides de la semana (Wikipedia "On this day", español, sin API key) ---
EFEMERIDES_DIAS = 7       # hoy + siguientes (la semana)
EFEMERIDES_EVENTOS = 2    # eventos notables ("tal día como hoy…") por día
EFEMERIDES_CONMEMORA = 2  # días conmemorativos ("Día de…") por día

# --- Cuentas a revisar manualmente ---
# Lista curada de perfiles/newsletters (ej. LinkedIn) que NO se scrapean pero que
# conviene tener a mano para no olvidarse de revisarlos. Se muestran como panel
# de marcadores en el tablero. Para sumar/quitar: edita este dict.
# Formato: {categoría: [(nombre, url), ...]}
CUENTAS = {
    "Marketing (general)": [
        ("This Week in Marketing (newsletter)",
         "https://www.linkedin.com/newsletters/this-week-in-marketing-7029849494275919873/"),
    ],
    "Instagram": [
        ("Meganoticias CL", "https://www.instagram.com/meganoticiascl/"),
        ("Mercado Negro PE", "https://www.instagram.com/mercadonegrope/"),
        ("RoastBrief", "https://www.instagram.com/roastbrief/"),
        ("Goldfish Group", "https://www.instagram.com/goldfish.group/"),
        ("Revista PyM", "https://www.instagram.com/revistapym/"),
    ],
}

# Archivo de texto editable a mano (formato simple, ver cuentas.txt). Si existe,
# manda sobre el dict CUENTAS de arriba. Así sumas/quitas cuentas sin tocar código.
CUENTAS_FILE = Path(__file__).resolve().parent / "cuentas.txt"


def _nombre_desde_url(url: str) -> str:
    """Saca un nombre legible del último tramo de la URL (handle)."""
    handle = url.rstrip("/").split("/")[-1]
    return handle or url


def cargar_cuentas() -> dict:
    """Lee cuentas.txt si existe; si no, usa el dict CUENTAS como respaldo.

    Formato del archivo:
      # Categoría
      Nombre | https://...     (o solo la URL: el nombre se saca del enlace)
      // comentario / línea ignorada
    """
    if not CUENTAS_FILE.exists():
        return CUENTAS

    grupos: dict[str, list[tuple[str, str]]] = {}
    categoria = "Otros"
    for linea in CUENTAS_FILE.read_text(encoding="utf-8").splitlines():
        s = linea.strip()
        if not s or s.startswith("//"):
            continue
        if s.startswith("#"):
            categoria = s.lstrip("#").strip() or "Otros"
            grupos.setdefault(categoria, [])
            continue
        if "|" in s:
            nombre, url = (p.strip() for p in s.split("|", 1))
        else:
            url, nombre = s, _nombre_desde_url(s)
        if url:
            grupos.setdefault(categoria, []).append((nombre or url, url))

    # descarta categorías vacías; si todo quedó vacío, vuelve al respaldo
    grupos = {k: v for k, v in grupos.items() if v}
    return grupos or CUENTAS

# --- Keywords sensibles ---
# NO clasifican ni descartan nada: solo marcan visualmente el item (sensible=True)
# para que el analista lo revise con cuidado. Respeta "no automatizar criterio".
# Coincidencia case-insensitive por substring sobre el texto del tema.
# Lista vacía por defecto: el mecanismo queda disponible pero no marca nada.
# Cada quien define sus propias keywords según el contexto que esté monitoreando.
KEYWORDS_SENSIBLES: list[str] = []

# --- Navegador ---
# Binario del navegador para abrir el tablero. Si está vacío o no se encuentra,
# usa el navegador por defecto del sistema.
NAVEGADOR = "vivaldi"

# --- Red ---
# User-Agent realista: sin esto muchos sitios devuelven 403.
USER_AGENT = (
    "Mozilla/5.0 (X11; Linux x86_64; rv:128.0) "
    "Gecko/20100101 Firefox/128.0"
)
REQUEST_TIMEOUT = 15  # segundos
