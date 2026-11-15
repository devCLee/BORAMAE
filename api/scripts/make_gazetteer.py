"""Write content/gazetteer.json: the catalog places first, then KR and US Natural Earth.

Run from the repo root: uv run --directory api python -m scripts.make_gazetteer
[--work DIR]. The script downloads the Natural Earth 10m populated places and admin-1
files (public domain) into a new empty folder under DIR (default: the temp folder).
"""

import argparse
import json
import math
import tempfile
import urllib.request
from pathlib import Path

from pydantic import TypeAdapter

from boramae.contracts.content import Place
from boramae.services.places import normalize

NE_BASE = (
    "https://raw.githubusercontent.com/nvkelso/natural-earth-vector/v5.1.2/geojson/"
)
# File -> (kind, property names of: id, English name, other English name, Korean name,
# country, latitude, longitude). Populated places sort by POP_MAX, largest first.
NE_FILES = {
    "ne_10m_populated_places.geojson": (
        "city",
        ("NE_ID", "NAME_EN", "NAME", "NAME_KO", "ISO_A2", "LATITUDE", "LONGITUDE"),
    ),
    "ne_10m_admin_1_states_provinces.geojson": (
        "region",
        ("ne_id", "name", "name_en", "name_ko", "iso_a2", "latitude", "longitude"),
    ),
}
COUNTRIES = {"KR", "US"}
# ponytail: small towns named like a word a question holds ("lead to", "Arctic Circle")
# are left out, so the word finds no place. A longer list waits for TR-F-011 (P1).
WORD_TOWNS = {"Alpine", "Circle", "Lead", "Price", "Salmon"}
KO_CITY_SUFFIXES = ("특별자치시", "특별시", "광역시", "시")
DOWNLOAD_TIMEOUT_S = 120
# ponytail: a Natural Earth row with the same English name within this distance of a
# place already written is the same place (a metropolitan city in both files).
SAME_PLACE_KM = 25
KM_PER_DEGREE = 111.2
OUTPUT = Path(__file__).resolve().parents[2] / "content" / "gazetteer.json"

# Catalog places of PRD inputs 1-60: (id, en, ko, alt, country, kind, source). The
# source is a Natural Earth ID, whose point the place takes, or a hand point (lat, lon).
# A hand point is a Natural Earth polygon centroid, a named point (a peak, a river
# confluence, Lees Ferry, the US geographic center) or a chosen interior point. Each
# was checked inside its Natural Earth polygon (country, province, lake, sea, region).
# ponytail: a sea outside both countries takes the country of the input that names it.
# fmt: off
HAND_PLACES = [
    ("kr-seoul", "Seoul", "서울", [], "KR", "city", 1159151523),
    ("kr-busan", "Busan", "부산", [], "KR", "city", 1159149599),
    ("kr-daegu", "Daegu", "대구", [], "KR", "city", 1159146599),
    ("kr-daejeon", "Daejeon", "대전", [], "KR", "city", 1159149595),
    ("us-phoenix", "Phoenix", "피닉스", [], "US", "city", 1159151225),
    ("us-chicago", "Chicago", "시카고", [], "US", "city", 1159151491),
    ("us-new-york", "New York", "뉴욕", ["NYC"], "US", "city", 1159151575),
    ("us-boston", "Boston", "보스턴", ["New England", "뉴잉글랜드"], "US", "city", 1159151239),
    ("us-houston", "Houston", "휴스턴", [], "US", "city", 1159151485),
    ("us-seattle", "Seattle", "시애틀", ["Pacific Northwest", "미국 북서부"], "US", "city", 1159151223),
    ("us-los-angeles", "Los Angeles", "로스앤젤레스", [], "US", "city", 1159151569),
    ("us-washington-dc", "Washington, DC", "워싱턴 DC", ["Washington", "워싱턴"], "US", "city", 1159151573),
    ("us-denver", "Denver", "덴버", [], "US", "city", 1159151483),
    ("us-miami", "Miami", "마이애미", [], "US", "city", 1159151487),
    ("kr-gangwon", "Gangwon-do", "강원도", ["Gangwon State", "Gangwon Province", "강원", "강원특별자치도"], "KR", "region", 1159312111),
    ("kr-jeollanam", "Jeollanam-do", "전라남도", ["South Jeolla Province", "Jeonnam", "전남"], "KR", "region", 1159313529),
    ("kr-gyeongbuk", "Gyeongsangbuk-do", "경상북도", ["North Gyeongsang Province", "Gyeongbuk", "경북"], "KR", "region", 1159313537),
    ("kr-jeju", "Jeju", "제주", ["Jeju Island", "Jeju-do", "Jeju Province", "제주도"], "KR", "region", 1159313515),
    ("us-california", "California", "캘리포니아", [], "US", "region", 1159308415),
    ("us-iowa", "Iowa", "아이오와", [], "US", "region", 1159315357),
    ("kr-south-korea", "South Korea", "한국", ["Korea", "Republic of Korea", "대한민국", "남한"], "KR", "region", (36.46, 127.87)),
    ("kr-han-river-basin", "Han River basin", "한강 유역", ["Han River", "Hangang", "한강"], "KR", "region", (37.52, 127.28)),
    ("kr-seoraksan", "Seoraksan", "설악산", ["Mount Seorak", "Seorak", "설악"], "KR", "region", (38.119, 128.465)),
    ("kr-east-sea", "East Sea", "동해", [], "KR", "region", (41.28, 135.74)),
    ("kr-barents-kara", "Barents–Kara Sea", "바렌츠·카라해", ["Barents Sea", "Kara Sea", "바렌츠해", "카라해"], "KR", "region", (75.0, 50.0)),
    ("us-contiguous", "Contiguous United States", "미국 본토", ["contiguous US", "United States", "USA", "U.S.", "미국"], "US", "region", (39.83, -98.58)),
    ("us-north-slope", "Alaska's North Slope", "알래스카 노스슬로프", ["North Slope", "Alaska North Slope", "Alaska's tundra", "노스슬로프", "노스 슬로프", "알래스카 툰드라"], "US", "region", (69.6, -155.15)),
    ("us-chukchi-beaufort", "Chukchi and Beaufort Seas", "축치해·보퍼트해", ["Chukchi Sea", "Beaufort Sea", "off Alaska", "축치해", "추크치해", "보퍼트해", "알래스카 앞바다"], "US", "region", (71.6, -154.0)),
    ("us-gulf-of-alaska-glaciers", "Gulf of Alaska glaciers", "알래스카만 빙하", ["Gulf of Alaska", "Alaska's glaciers", "알래스카만", "알래스카 빙하"], "US", "region", (60.6, -144.5)),
    ("us-sierra-nevada", "Sierra Nevada", "시에라네바다", ["시에라네바다산맥"], "US", "region", (37.87, -119.73)),
    ("us-lake-erie", "Lake Erie", "이리호", ["Great Lakes", "오대호"], "US", "region", (42.16, -81.24)),
    ("us-colorado-rockies", "Colorado Rockies", "콜로라도 로키산맥", ["Rockies", "Rocky Mountains", "Colorado Rocky Mountains", "로키산맥", "로키 산맥"], "US", "region", (39.5, -106.0)),
    ("us-gulf-of-mexico", "Gulf of Mexico", "멕시코만", [], "US", "region", (25.49, -89.92)),
    ("us-colorado-river-basin", "Colorado River basin", "콜로라도강 유역", ["Colorado River", "콜로라도강", "콜로라도 강"], "US", "region", (36.87, -111.59)),
    ("us-great-salt-lake-basin", "Great Salt Lake basin", "그레이트솔트호 유역", ["Great Salt Lake", "그레이트솔트호"], "US", "region", (41.17, -112.5)),
    ("us-gulf-of-maine", "Gulf of Maine", "메인만", [], "US", "region", (43.33, -68.46)),
    ("us-subpolar-north-atlantic", "subpolar North Atlantic", "북대서양 아한대 해역", ["North Atlantic", "open Atlantic", "subpolar gyre", "북대서양", "대서양 먼바다"], "US", "region", (57.5, -35.0)),
]
# fmt: on


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="make_gazetteer", description=__doc__)
    parser.add_argument("--work", type=Path, default=Path(tempfile.gettempdir()))
    args = parser.parse_args(argv)
    work = Path(tempfile.mkdtemp(prefix="natural-earth-", dir=args.work))
    rows: dict[int, dict] = {}
    for file_name, (kind, fields) in NE_FILES.items():
        rows |= read_natural_earth(download(file_name, work), kind, fields)
    hand = [hand_place(row, rows) for row in HAND_PLACES]  # takes its rows out of rows
    places = merge(hand, rows.values())
    TypeAdapter(list[Place]).validate_python(places)
    lines = ",\n".join(json.dumps(place, ensure_ascii=False) for place in places)
    OUTPUT.write_text(f"[\n{lines}\n]\n", encoding="utf-8", newline="\n")
    print(f"gazetteer: {len(places)} places, {len(HAND_PLACES)} catalog places first")
    return 0


def download(file_name: str, work: Path) -> Path:
    path = work / file_name
    with urllib.request.urlopen(NE_BASE + file_name, timeout=DOWNLOAD_TIMEOUT_S) as r:
        path.write_bytes(r.read())
    return path


def read_natural_earth(path: Path, kind: str, fields: tuple[str, ...]) -> dict:
    """Return the KR and US features as gazetteer rows, keyed by Natural Earth ID."""
    ne_id, en, other, ko, country, lat, lon = fields
    features = json.loads(path.read_text(encoding="utf-8"))["features"]
    props = [
        f["properties"]
        for f in features
        if f["properties"][country] in COUNTRIES
        and f["properties"][en] not in WORD_TOWNS
    ]
    props.sort(key=lambda p: -p.get("POP_MAX", 0))
    rows = {}
    for p in props:
        short_ko = _strip_city_suffix(p[ko]) if p[country] == "KR" else p[ko]
        rows[p[ne_id]] = {
            "id": f"ne-{p[ne_id]}",
            "name": {"en": p[en], "ko": short_ko},
            "alt": _new_names([p[other], p[ko]], [p[en], short_ko]),
            "lat": p[lat],
            "lon": p[lon],
            "country": p[country],
            "kind": kind,
        }
    return rows


def hand_place(row: tuple, ne_rows: dict) -> dict:
    """Return a catalog place; a Natural Earth source gives its point and its names."""
    place_id, en, ko, alt, country, kind, source = row
    if isinstance(source, int):
        ne = ne_rows.pop(source)
        lat, lon = ne["lat"], ne["lon"]
        alt = alt + _new_names([*ne["name"].values(), *ne["alt"]], [en, ko, *alt])
    else:
        lat, lon = source
    return {
        "id": place_id,
        "name": {"en": en, "ko": ko},
        "alt": alt,
        "lat": lat,
        "lon": lon,
        "country": country,
        "kind": kind,
    }


def merge(hand: list[dict], ne_rows) -> list[dict]:
    """Append each Natural Earth row that is not already a written place."""
    places = list(hand)
    written: dict[tuple[str, str], list[dict]] = {}
    for place in places:
        written.setdefault(_key(place), []).append(place)
    for row in ne_rows:
        same = written.setdefault(_key(row), [])
        if not any(_km(row, place) <= SAME_PLACE_KM for place in same):
            same.append(row)
            places.append(row)
    return places


def _key(place: dict) -> tuple[str, str]:
    return place["country"], normalize(place["name"]["en"])


def _km(a: dict, b: dict) -> float:
    mean_lat = math.radians((a["lat"] + b["lat"]) / 2)
    dx = (a["lon"] - b["lon"]) * math.cos(mean_lat)
    return KM_PER_DEGREE * math.hypot(a["lat"] - b["lat"], dx)


def _strip_city_suffix(name: str) -> str:
    for suffix in KO_CITY_SUFFIXES:
        if name.endswith(suffix) and len(name) > len(suffix):
            return name.removesuffix(suffix)
    return name


def _new_names(names: list[str], known: list[str]) -> list[str]:
    """Return the names whose normalized form is not known yet, in order, once each."""
    seen = {normalize(name) for name in known}
    new = []
    for name in names:
        if normalize(name) not in seen:
            seen.add(normalize(name))
            new.append(name)
    return new


if __name__ == "__main__":
    raise SystemExit(main())
