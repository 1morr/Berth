"""Mikan / Nyaa / acg.rip 三個索引站 RSS 欄位事實的檢查（M3 票 07；`docs/research/rss-sources.md`
§7.4）。

一手資料是 `tests/fixtures/http/{mikan,nyaa,acgrip}/` 的 fixture（研究檔 §1 有取得方式）。
這支合併了原本四支互相獨立的檢查，各自對應研究檔裡的一個角度：

- feedparser 對每份 fixture 的解析結果整支印出來（研究檔 §7.3 的欄位表從這裡整理）；
- 用一個最小 bencode 解碼器直接讀 `.torrent`，核對 info hash 就是 guid / enclosure 用的那個；
- Mikan / acg.rip / Nyaa 逐項核對 guid、hash、大小、日期彼此一致（研究檔 §2–§4）；
- Mikan 與 acg.rip 的 pubDate 時區偏移、日期字串的小數位數與 size 換算精度（研究檔 §5、§10）；
- item 的元素樹形狀與「合集」標題掃描（研究檔 §6）。

`feedparser` 不是本專案依賴（只在這支腳本用得到，不值得為它動 `pyproject.toml` / `uv.lock`），
用 `uv run --no-project` 額外帶：

    uv run --no-project --python 3.13 --with feedparser python scripts/experiments/rss_sources.py

只讀 fixture、只印 stdout，不連網、不寫檔。
"""

from __future__ import annotations

import hashlib
import io
import re
import struct
import sys
import xml.etree.ElementTree as ET
from datetime import UTC, datetime
from email.utils import parsedate_to_datetime
from pathlib import Path
from typing import Any

# feedparser 沒有型別存根（不在 typeshed，也沒隨附 py.typed），而且刻意不進專案依賴，
# mypy 在專案環境裡本來就找不到它——上面的模組 docstring 已經說明只用 --with 帶。
import feedparser  # type: ignore[import-not-found]
from feedparser.datetimes import _parse_date  # type: ignore[import-not-found]

REPO_ROOT = Path(__file__).resolve().parents[2]
FIXTURES_ROOT = REPO_ROOT / "tests" / "fixtures" / "http"

MIKAN_NS = "{https://mikanani.me/0.1/}"
ACGRIP_NS = {"torrent": "http://xmlns.ezrss.it/0.1/", "media": "http://search.yahoo.com/mrss/"}
HEX40 = re.compile(r"^[0-9a-f]{40}$")
UNIT = {"KB": 1024, "MB": 1024**2, "GB": 1024**3, "TB": 1024**4}
# 原本三支腳本各自的「合集」正則其實不一樣（原始資料就是這樣，不是筆誤），不能合併成一個：
MIKAN_COLLECTION = re.compile(r"合集|\d{2}\s*-\s*\d{2}|Batch|全集")  # tags.py
ACGRIP_COLLECTION = re.compile(r"合集|\d{2}\s*-\s*\d{2}|Batch|Vol\.")  # analyze.py acg.rip 段
NYAA_COLLECTION = re.compile(r"Batch|\d{2}\s*-\s*\d{2}|合集")  # analyze.py Nyaa 段

MIKAN_FIXTURES = [
    "mikan/rss-bangumi.4009-370.xml",
    "mikan/rss-classic.xml",
    "mikan/rss-mybangumi.xml",
]
NYAA_FIXTURES = [
    "nyaa/rss-search.kamiina-botan.xml",
    "nyaa/rss-user.subsplease.kamiina-botan.xml",
]
ACGRIP_FIXTURES = [
    "acgrip/rss-search.kimi-ga-shinu.xml",
    "acgrip/rss-search.kamiina-botan.xml",
]
# fp_dump.py 原本的順序：mikan、nyaa、acgrip。
ALL_FIXTURES = [*MIKAN_FIXTURES, *NYAA_FIXTURES, *ACGRIP_FIXTURES]
TORRENT_FIXTURE = FIXTURES_ROOT / "mikan/download.85c93c23.torrent"


# --------------------------------------------------------------------------------------
# ElementTree 小工具：fixture 保證每個欄位都在，拿不到就直接炸比較好查，
# 不要吞掉變成空字串再默默印出錯的結論。
# --------------------------------------------------------------------------------------
def _text(el: ET.Element, tag: str, namespaces: dict[str, str] | None = None) -> str:
    value = el.findtext(tag, namespaces=namespaces)
    assert value is not None, f"missing <{tag}>"
    return value


def _child(el: ET.Element, tag: str, namespaces: dict[str, str] | None = None) -> ET.Element:
    child = el.find(tag, namespaces=namespaces)
    assert child is not None, f"missing <{tag}>"
    return child


def _attr(el: ET.Element, name: str) -> str:
    value = el.get(name)
    assert value is not None, f"missing @{name}"
    return value


# --------------------------------------------------------------------------------------
# 最小 bencode 解碼器：只為了算 .torrent 的 info hash，不追求通用。
# dict 的值存成 (value, None) 是為了跟 int / bytes / list 的回傳型別對齊，用不到第二個欄位。
# --------------------------------------------------------------------------------------
def bdecode(data: bytes, i: int = 0) -> tuple[Any, int]:
    c = data[i : i + 1]
    if c == b"i":
        j = data.index(b"e", i)
        return int(data[i + 1 : j]), j + 1
    if c == b"l":
        i += 1
        out = []
        while data[i : i + 1] != b"e":
            v, i = bdecode(data, i)
            out.append(v)
        return out, i + 1
    if c == b"d":
        i += 1
        outd: dict[Any, Any] = {}
        while data[i : i + 1] != b"e":
            k, i = bdecode(data, i)
            v, i = bdecode(data, i)
            outd[k] = (v, None)
        return outd, i + 1
    j = data.index(b":", i)
    n = int(data[i:j])
    return data[j + 1 : j + 1 + n], j + 1 + n


def info_span(data: bytes) -> bytes:
    """回傳最外層 `info` 值的原始位元組（sha1 這段，不是解碼後的值）。"""
    assert data[:1] == b"d"
    i = 1
    while data[i : i + 1] != b"e":
        k, i = bdecode(data, i)
        start = i
        _, i = bdecode(data, i)
        if k == b"info":
            return data[start:i]
    raise KeyError("info")


def shape(el: ET.Element) -> tuple[str, tuple[str, ...], tuple[Any, ...]]:
    """(tag, 排序後的屬性名, 每個子節點的 shape)：用來看不同 fixture 的 item 元素樹
    是不是同一種形狀。
    """
    return (el.tag, tuple(sorted(el.attrib)), tuple(shape(c) for c in el))


def f32(x: float) -> float:
    """模擬 float32 的精度損失：pack 成 4 bytes 再 unpack 回來。"""
    return float(struct.unpack("f", struct.pack("f", x))[0])


# --------------------------------------------------------------------------------------
# 原 fp_dump.py：feedparser 對每份 fixture 的完整解析結果。
# --------------------------------------------------------------------------------------
def dump_feedparser_view() -> None:
    print("feedparser", feedparser.__version__, "python", sys.version.split()[0])
    for rel in ALL_FIXTURES:
        p = FIXTURES_ROOT / rel
        print("\n=====", rel)
        if not p.exists():
            print("MISSING")
            continue
        d = feedparser.parse(p.read_bytes())
        print("version:", d.version, "bozo:", d.bozo, repr(d.get("bozo_exception")))
        print("namespaces:", dict(d.namespaces))
        print("entries:", len(d.entries))
        e = d.entries[0]
        for k in sorted(e.keys()):
            v = e[k]
            s = repr(v)
            if len(s) > 240:
                s = s[:240] + "..."
            print(f"  {k}: {s}")
        # key set stability across entries
        keysets = {tuple(sorted(x.keys())) for x in d.entries}
        print("distinct key sets across entries:", len(keysets))


# --------------------------------------------------------------------------------------
# 原 analyze.py 第一段：bencode 直接解 .torrent，核對 info hash。
# --------------------------------------------------------------------------------------
def check_torrent_info_hash() -> None:
    print("## torrent")
    raw = TORRENT_FIXTURE.read_bytes()
    info_raw = info_span(raw)
    print("sha1(info) =", hashlib.sha1(info_raw).hexdigest())
    top, _ = bdecode(raw)
    print("top keys:", [k.decode() for k in top])
    info, _ = bdecode(info_raw)
    print("info keys:", [k.decode() for k in info])
    if b"length" in info:
        print("single-file length:", info[b"length"][0])
    else:
        files = info[b"files"][0]
        unwrapped = [{k: v[0] for k, v in x.items()} for x in files]
        print("multi-file total:", sum(f[b"length"][0] for f in unwrapped))
    print("name:", info[b"name"][0].decode())


# --------------------------------------------------------------------------------------
# 原 analyze.py 第二段：Mikan 逐項核對 guid / hash / 大小 / 日期。
# --------------------------------------------------------------------------------------
def check_mikan_consistency() -> None:
    for rel in MIKAN_FIXTURES:
        print("\n##", rel)
        items = ET.parse(FIXTURES_ROOT / rel).findall("./channel/item")
        bad = 0
        fracs: set[int] = set()
        guid_eq_title = 0
        size_desc_ok = 0
        for it in items:
            link = _text(it, "link")
            h = link.rsplit("/", 1)[-1]
            enc = _child(it, "enclosure")
            enc_hash = _attr(enc, "url").rsplit("/", 1)[-1].removesuffix(".torrent")
            t = _child(it, f"{MIKAN_NS}torrent")
            tlink = _text(t, f"{MIKAN_NS}link")
            clen = _text(t, f"{MIKAN_NS}contentLength")
            pd = _text(t, f"{MIKAN_NS}pubDate")
            length_ok = enc.get("length") == clen
            if not (HEX40.match(h) and h == enc_hash and tlink == link and length_ok):
                bad += 1
                print("  MISMATCH", link, enc.get("url"), clen, enc.get("length"))
            fracs.add(len(pd.split(".")[1]) if "." in pd else 0)
            if it.findtext("guid") == it.findtext("title"):
                guid_eq_title += 1
            # description ends with [size]
            if re.search(r"\[([\d.]+)\s*(MB|GB|KB|TB)\]$", _text(it, "description")):
                size_desc_ok += 1
            # date folder in enclosure vs pubDate date
            folder = _attr(enc, "url").split("/Download/")[1].split("/")[0]
            if folder != pd[:10].replace("-", ""):
                print("  folder!=pubDate date:", folder, pd)
            # std pubDate at item level?
            if it.find("pubDate") is not None:
                print("  item-level pubDate present!")
        print(
            f"  items={len(items)} mismatches={bad} guid==title:{guid_eq_title} "
            f"desc-size:{size_desc_ok} frac-digit-lengths={sorted(fracs)}"
        )
        print("  guid isPermaLink values:", {_child(it, "guid").get("isPermaLink") for it in items})
        print("  enclosure types:", {_child(it, "enclosure").get("type") for it in items})
        # dup guids?
        guids = [it.findtext("guid") for it in items]
        print("  duplicate guids:", len(guids) - len(set(guids)))


# --------------------------------------------------------------------------------------
# 原 analyze.py 第三段：feedparser 對 Mikan 第一份 fixture entry[0] 的 links / enclosures。
# --------------------------------------------------------------------------------------
def dump_feedparser_mikan_entry() -> None:
    d = feedparser.parse((FIXTURES_ROOT / MIKAN_FIXTURES[0]).read_bytes())
    e = d.entries[0]
    print("\n## feedparser mikan entry[0]")
    print("  links:", e.links)
    print("  enclosures:", e.get("enclosures"))
    print("  'torrent' in e:", "torrent" in e, repr(e.get("torrent")))
    print(
        "  published_parsed -> ",
        e.published_parsed,
        "(value is naive local UTC+8 but tuple claims UTC)",
    )


# --------------------------------------------------------------------------------------
# 原 analyze.py 第四段：acg.rip 逐項核對 guid / enclosure / media:content。
# --------------------------------------------------------------------------------------
def check_acgrip_consistency() -> None:
    for rel in ACGRIP_FIXTURES:
        print("\n##", rel)
        items = ET.parse(FIXTURES_ROOT / rel).findall("./channel/item")
        ok = 0
        for it in items:
            guid = it.findtext("guid")
            link = it.findtext("link")
            enc = _child(it, "enclosure")
            cl = it.findtext("torrent:contentLength", namespaces=ACGRIP_NS)
            mc = _child(it, "media:content", namespaces=ACGRIP_NS)
            if (
                guid == link
                and enc.get("url") == f"{link}.torrent"
                and mc.get("fileSize") == cl
                and enc.get("length") is None
            ):
                ok += 1
        print(
            f"  items={len(items)} consistent(guid==link, enc=link+.torrent, "
            f"media fileSize==contentLength, enclosure has no length)={ok}"
        )
        print("  guid attrs:", {tuple(sorted(_child(it, "guid").attrib.items())) for it in items})
        print("  item child tags:", sorted({c.tag for it in items for c in it}))
        for it in items:
            t = _text(it, "title")
            if ACGRIP_COLLECTION.search(t):
                size = it.findtext("torrent:contentLength", namespaces=ACGRIP_NS)
                print("  COLLECTION?", t, "| size", size)
        d = feedparser.parse((FIXTURES_ROOT / rel).read_bytes())
        print("  feedparser enclosures[0]:", d.entries[0].enclosures)


# --------------------------------------------------------------------------------------
# 原 analyze.py 第五段：Nyaa（全靠 feedparser，沒有另外用 ElementTree 解）。
# --------------------------------------------------------------------------------------
def check_nyaa_consistency() -> None:
    for rel in NYAA_FIXTURES:
        print("\n##", rel)
        d = feedparser.parse((FIXTURES_ROOT / rel).read_bytes())
        hashes_ok = sum(1 for x in d.entries if HEX40.match(x.nyaa_infohash))
        print(f"  entries={len(d.entries)} infohash-40hex={hashes_ok}")
        print("  enclosures[0]:", d.entries[0].get("enclosures"))
        print("  size units:", sorted({x.nyaa_size.split()[1] for x in d.entries}))
        print(
            "  guid/link patterns ok:",
            sum(
                1
                for x in d.entries
                if x.id.startswith("https://nyaa.si/view/")
                and x.link == x.id.replace("/view/", "/download/") + ".torrent"
            ),
        )
        print("  categories:", sorted({(x.nyaa_categoryid, x.nyaa_category) for x in d.entries}))
        print("  pubDate tz suffixes:", sorted({x.published.rsplit(" ", 1)[1] for x in d.entries}))
        for x in d.entries:
            if NYAA_COLLECTION.search(x.title):
                print("  COLLECTION?", x.title, "|", x.nyaa_size)


# --------------------------------------------------------------------------------------
# 原 analyze.py 第六段：Mikan 與 acg.rip 對同一集的 pubDate 時區偏移、大小比較。
# --------------------------------------------------------------------------------------
def compare_mikan_acgrip_offsets() -> None:
    print("\n## time offset: 喵萌奶茶屋&LoliHouse Kimi ga Shinu 12")
    mk = ET.parse(FIXTURES_ROOT / MIKAN_FIXTURES[0]).findall("./channel/item")
    ar = ET.parse(FIXTURES_ROOT / "acgrip/rss-search.kimi-ga-shinu.xml").findall("./channel/item")
    for epi in ["12", "11", "10"]:
        mt = next((it for it in mk if f"Shitai - {epi} " in _text(it, "title")), None)
        at = next(
            (
                it
                for it in ar
                if f"Shitai - {epi} " in _text(it, "title") and "喵萌奶茶屋" in _text(it, "title")
            ),
            None,
        )
        if mt is None or at is None:
            print(" ", epi, "not in both")
            continue
        mpd = _text(_child(mt, f"{MIKAN_NS}torrent"), f"{MIKAN_NS}pubDate")
        apd = _text(at, "pubDate")
        mnaive = datetime.fromisoformat(mpd)
        autc = parsedate_to_datetime(apd).astimezone(UTC)
        diff = mnaive - autc.replace(tzinfo=None)
        print(
            f"  ep{epi}: mikan {mpd} (naive) ; acg.rip {apd} = {autc.isoformat()} "
            f"; mikan_naive - acg_utc = {diff}"
        )
        desc_size = re.search(r"\[[\d.]+ ?[KMGT]B\]$", _text(mt, "description"))
        assert desc_size is not None, "Mikan 的描述結尾沒有 [N UNIT]"
        print(
            "    sizes: mikan contentLength",
            _text(_child(mt, f"{MIKAN_NS}torrent"), f"{MIKAN_NS}contentLength"),
            "acg.rip contentLength",
            at.findtext("{http://xmlns.ezrss.it/0.1/}contentLength"),
            "| mikan desc",
            desc_size.group(),
        )


# --------------------------------------------------------------------------------------
# 原 dates_sizes.py：size 換算精度（float32 vs float64）與 pubDate 小數位數 / 時區格式。
# --------------------------------------------------------------------------------------
def check_date_size_precision() -> None:
    print("python", sys.version.split()[0], "feedparser", feedparser.__version__)
    samples: dict[int, str] = {}
    for rel in MIKAN_FIXTURES:
        items = ET.parse(FIXTURES_ROOT / rel).findall("./channel/item")
        exact_f32 = exact_f64 = 0
        for it in items:
            t = _child(it, f"{MIKAN_NS}torrent")
            cl = int(_text(t, f"{MIKAN_NS}contentLength"))
            m = re.search(r"\[([\d.]+)\s*(KB|MB|GB|TB)\]$", _text(it, "description"))
            assert m is not None
            num, unit = m.groups()
            if int(f32(float(num)) * UNIT[unit]) == cl:
                exact_f32 += 1
            if round(float(num) * UNIT[unit]) == cl:
                exact_f64 += 1
            pd = _text(t, f"{MIKAN_NS}pubDate")
            frac = len(pd.split(".")[1]) if "." in pd else 0
            samples.setdefault(frac, pd)
        print(
            f"{rel}: n={len(items)} contentLength==int(float32(desc)*1024^k): {exact_f32}  "
            f"==round(float64(desc)*1024^k): {exact_f64}"
        )

    print("\nMikan pubDate samples by fractional digits:", samples)
    # 7 位小數（.NET 'FFFFFFF' 的最壞情況），合成樣本，fixture 裡沒有這麼多位的。
    extra = ["2026-09-24T16:08:01.3890000", "2026-09-24T16:08:01.1234567"]
    for s in [*samples.values(), *extra]:
        try:
            v: object = datetime.fromisoformat(s)
        except ValueError as exc:
            v = f"ValueError: {exc}"
        fp = _parse_date(s)
        print(
            f"  {s!r:34} fromisoformat -> {v!s:28} feedparser._parse_date -> {fp[:6] if fp else fp}"
        )

    print("\nNyaa -0000:")
    s = "Fri, 18 Sep 2026 03:54:17 -0000"
    dt = parsedate_to_datetime(s)
    print("  parsedate_to_datetime:", repr(dt), "tzinfo:", dt.tzinfo)
    print("  feedparser._parse_date:", _parse_date(s)[:6])
    s = "Thu, 24 Sep 2026 01:08:02 -0700"
    print("acg.rip:", repr(parsedate_to_datetime(s)), _parse_date(s)[:6])


# --------------------------------------------------------------------------------------
# 原 tags.py：Mikan item 的元素樹形狀、pubDate 範圍、合集標題掃描，
# 加 .torrent 幾個 key 的原始位元組。
# --------------------------------------------------------------------------------------
def check_item_shapes_and_collections() -> None:
    for rel in MIKAN_FIXTURES:
        items = ET.parse(FIXTURES_ROOT / rel).findall("./channel/item")
        shapes = {shape(i) for i in items}
        pds = sorted(_text(_child(i, f"{MIKAN_NS}torrent"), f"{MIKAN_NS}pubDate") for i in items)
        coll = [_text(i, "title") for i in items if MIKAN_COLLECTION.search(_text(i, "title"))]
        print(
            rel,
            "items",
            len(items),
            "shapes",
            len(shapes),
            "range",
            pds[0],
            "->",
            pds[-1],
            "collections",
            len(coll),
        )
        for c in coll[:6]:
            print("   ", c)
        print("  ", next(iter(shapes)))
    raw = TORRENT_FIXTURE.read_bytes()
    i = raw.find(b"4:hash")
    print("hash key raw:", raw[i : i + 60])
    i = raw.find(b"10:created by")
    print(raw[i : i + 60])
    i = raw.find(b"13:creation date")
    print(raw[i : i + 30])


def main() -> int:
    # 標題裡有中文，Windows 主控台預設是 cp950（跟 absolute_rule_cost.py 同一個理由）。
    if isinstance(sys.stdout, io.TextIOWrapper):
        sys.stdout.reconfigure(encoding="utf-8")
    dump_feedparser_view()
    check_torrent_info_hash()
    check_mikan_consistency()
    dump_feedparser_mikan_entry()
    check_acgrip_consistency()
    check_nyaa_consistency()
    compare_mikan_acgrip_offsets()
    check_date_size_precision()
    check_item_shapes_and_collections()
    return 0


if __name__ == "__main__":
    sys.exit(main())
