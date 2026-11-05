#!/usr/bin/env python3
"""
Faceless-Shorts-Generator (Deutsch)
===================================

Erstellt aus einem YAML-Skript ein fertiges Hochkant-Video (1080x1920) für
TikTok, YouTube Shorts und Instagram Reels – ohne Gesicht, ohne Schnittprogramm.

Zwei Stile (angelehnt an erfolgreiche deutsche Faceless-Kanäle):

  stil: fakten   -> "Zufällige Fakten": schnelle Bildwechsel, Fotos aus dem Internet,
                    große 1-2-Wort-Untertitel in GROSSBUCHSTABEN, bunte Schlüsselwörter
  stil: psycho   -> "Hast du gewusst…": ruhige Stimme, KI-Bilder im Neon-Look,
                    ein einzelnes Wort als Untertitel in der Bildmitte

Bilder kommen aus dem ganzen Internet:
  * Openverse (Millionen freie Fotos u.a. von Flickr), Wikimedia Commons
  * Pexels / Pixabay (wenn PEXELS_API_KEY bzw. PIXABAY_API_KEY gesetzt ist)
  * KI-Bilder (Pollinations, kostenlos, kein Konto nötig)
  * eigene Bilder oder beliebige Bild-URLs

Benutzung:
    python shorts.py skripte/fakten_01.yaml
    python shorts.py skripte/*.yaml
"""

from __future__ import annotations

import argparse
import asyncio
import hashlib
import json
import os
import random
import re
import shutil
import subprocess
import sys
import textwrap
import time
import urllib.parse
import urllib.error
import urllib.request
from dataclasses import dataclass, field
from pathlib import Path

import yaml
from PIL import Image, ImageDraw, ImageFilter, ImageFont, ImageOps

# Firmen-/Proxy-Zertifikate respektieren (z.B. SSL_CERT_FILE=/pfad/ca.crt)
if os.environ.get("SSL_CERT_FILE"):
    try:
        import certifi
        certifi.where = lambda: os.environ["SSL_CERT_FILE"]
    except ImportError:
        pass

W, H = 1080, 1920
FPS = 30
ROOT = Path(__file__).resolve().parent
CACHE = ROOT / ".cache"
AUSGABE = ROOT / "ausgabe"
USER_AGENT = "FacelessShortsDE/1.0 (+https://github.com)"

SCHRIFTEN = [
    "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
    "/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf",
    "/System/Library/Fonts/Supplemental/Arial Bold.ttf",
    "C:/Windows/Fonts/arialbd.ttf",
]

# --------------------------------------------------------------------------- #
# Stil-Vorlagen
# --------------------------------------------------------------------------- #
STILE = {
    "fakten": {
        "stimme": "de-DE-ConradNeural",
        "tempo": "+12%",
        "bildquelle": "web",
        "ki_stil": "hyperrealistic photo, vivid colors, cinematic lighting, sharp focus",
        "woerter_pro_untertitel": 2,
        "grossbuchstaben": True,
        "schriftgroesse": 100,
        "vollbild": True,
        "rand": 8,
        "farben": ["&H0033FF33&", "&H00FFB000&", "&H0000E5FF&"],  # grün, blau, gelb (BGR)
        "drehen": True,
        "y": 900,
        "zoom": 0.10,
        "musik": "synthwave",
    },
    "psycho": {
        "stimme": "de-DE-FlorianMultilingualNeural",
        "tempo": "+0%",
        "bildquelle": "ki",
        "ki_stil": ("glowing neon wireframe hologram, cyan and magenta light, dark futuristic "
                    "background, 3d render, digital art, highly detailed"),
        "woerter_pro_untertitel": 1,
        "grossbuchstaben": False,
        "schriftgroesse": 66,
        "vollbild": True,
        "rand": 3,
        "farben": [],
        "drehen": False,
        "y": 960,
        "zoom": 0.08,
        "musik": "ambient",
    },
}


def log(msg: str) -> None:
    print(f"  {msg}", flush=True)


def run(cmd: list[str]) -> str:
    res = subprocess.run(cmd, capture_output=True, text=True)
    if res.returncode != 0:
        sys.stderr.write(res.stderr[-3000:])
        raise RuntimeError(f"Befehl fehlgeschlagen: {' '.join(cmd[:6])} ...")
    return res.stdout


def dauer(datei: Path) -> float:
    return float(run(["ffprobe", "-v", "error", "-show_entries", "format=duration",
                      "-of", "default=nw=1:nk=1", str(datei)]).strip())


def schrift_pfad() -> str:
    return next((p for p in SCHRIFTEN if Path(p).exists()), "")


def schrift_name() -> str:
    p = schrift_pfad()
    return "Liberation Sans" if "Liberation" in p else "Arial" if "rial" in p else "DejaVu Sans"


def hashname(*teile: str) -> str:
    return hashlib.sha1("|".join(map(str, teile)).encode()).hexdigest()[:16]


# --------------------------------------------------------------------------- #
# Skript
# --------------------------------------------------------------------------- #
@dataclass
class Wort:
    text: str
    start: float
    ende: float


@dataclass
class Szene:
    text: str
    suche: str | None = None
    ki: str | None = None
    bild: str | None = None
    quelle: str | None = None
    audio: Path | None = None
    dauer: float = 0.0
    woerter: list[Wort] = field(default_factory=list)
    bild_datei: Path | None = None
    nachweis: str = ""


@dataclass
class Skript:
    name: str
    stil: dict
    stilname: str
    szenen: list[Szene]
    titel: str = ""
    beschreibung: str = ""
    hashtags: list[str] = field(default_factory=list)
    musik: str | None = None
    titel_einblenden: bool = False
    fortschritt: bool = False
    quelle: str | None = None


def lade_skript(pfad: Path) -> Skript:
    d = yaml.safe_load(pfad.read_text(encoding="utf-8"))
    stilname = d.get("stil", "fakten")
    stil = dict(STILE[stilname])
    for k in ("stimme", "tempo", "bildquelle", "ki_stil"):
        if k in d:
            stil[k] = str(d[k])
    szenen = []
    for s in d["szenen"]:
        s = {"text": s} if isinstance(s, str) else s
        szenen.append(Szene(text=" ".join(s["text"].split()), suche=s.get("suche"),
                            ki=s.get("ki"), bild=s.get("bild"), quelle=s.get("quelle")))
    return Skript(name=pfad.stem, stil=stil, stilname=stilname, szenen=szenen,
                  titel=d.get("titel", ""), beschreibung=d.get("beschreibung", ""),
                  hashtags=d.get("hashtags", []), musik=d.get("musik", stil["musik"]),
                  titel_einblenden=d.get("titel_einblenden", False),
                  fortschritt=d.get("fortschritt", False), quelle=d.get("quelle"))


def sprechtext(text: str) -> str:
    return text.replace("*", "")


# --------------------------------------------------------------------------- #
# Stimme (mit Wort-Zeitstempeln für synchrone Untertitel)
# --------------------------------------------------------------------------- #
def tts_edge(text: str, stimme: str, tempo: str, ziel: Path) -> list[tuple[str, float, float]]:
    import edge_tts

    grenzen: list[tuple[str, float, float]] = []

    async def _go():
        com = edge_tts.Communicate(text, stimme, rate=tempo, boundary="WordBoundary")
        with open(ziel, "wb") as f:
            async for ch in com.stream():
                if ch["type"] == "audio":
                    f.write(ch["data"])
                elif ch["type"] == "WordBoundary":
                    s = ch["offset"] / 1e7
                    grenzen.append((ch["text"], s, s + ch["duration"] / 1e7))
    asyncio.run(_go())
    return grenzen


def tts_gtts(text: str, tempo: str, ziel: Path) -> None:
    from gtts import gTTS
    roh = ziel.with_suffix(".roh.mp3")
    gTTS(text, lang="de").save(str(roh))
    faktor = max(0.6, min(2.0, 1.15 + int(re.sub(r"[^\d-]", "", tempo) or 0) / 100))
    run(["ffmpeg", "-y", "-v", "error", "-i", str(roh), "-af",
         f"silenceremove=start_periods=1:start_threshold=-45dB,atempo={faktor:.3f}", str(ziel)])
    roh.unlink(missing_ok=True)


def woerter_zuordnen(text: str, grenzen, gesamt: float) -> list[Wort]:
    tokens = text.split()
    if grenzen and len(grenzen) == len(tokens):
        return [Wort(t, g[1], g[2]) for t, g in zip(tokens, grenzen)]
    if grenzen:  # Anzahl weicht ab (z.B. Zahlen) -> Zeiten proportional verteilen
        start, ende = grenzen[0][1], grenzen[-1][2]
    else:
        start, ende = 0.05, gesamt - 0.05
    gewichte = [len(sprechtext(t)) + 2 for t in tokens]
    summe, t, out = sum(gewichte), start, []
    for tok, g in zip(tokens, gewichte):
        d = (ende - start) * g / summe
        out.append(Wort(tok, t, t + d))
        t += d
    return out


def erzeuge_audio(sk: Skript, motor: str) -> None:
    ordner = CACHE / "audio"
    ordner.mkdir(parents=True, exist_ok=True)
    for i, sz in enumerate(sk.szenen, 1):
        text = sprechtext(sz.text)
        grenzen = None
        if motor == "edge":
            ziel = ordner / f"e_{hashname(sk.stil['stimme'], sk.stil['tempo'], text)}.mp3"
            meta = ziel.with_suffix(".json")
            if ziel.exists() and meta.exists():
                grenzen = json.loads(meta.read_text())
            else:
                try:
                    grenzen = tts_edge(text, sk.stil["stimme"], sk.stil["tempo"], ziel)
                    meta.write_text(json.dumps(grenzen))
                except Exception as e:
                    log(f"edge-tts nicht erreichbar ({type(e).__name__}) -> gTTS")
                    motor = "gtts"
        if motor == "gtts":
            ziel = ordner / f"g_{hashname(sk.stil['tempo'], text)}.mp3"
            if not ziel.exists():
                tts_gtts(text, sk.stil["tempo"], ziel)
        sz.audio = ziel
        roh = dauer(ziel)
        sz.dauer = roh + 0.08
        sz.woerter = woerter_zuordnen(sz.text, grenzen, roh)
    log(f"Stimme fertig ({sum(s.dauer for s in sk.szenen):.1f} Sek.)")


# --------------------------------------------------------------------------- #
# Bilder aus dem Internet
# --------------------------------------------------------------------------- #
def http_get(url: str, headers: dict | None = None, timeout: int = 60) -> bytes:
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT, **(headers or {})})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return r.read()


def http_json(url: str, headers: dict | None = None) -> dict:
    return json.loads(http_get(url, headers, 30).decode())


def suche_pexels(q: str):
    key = os.environ.get("PEXELS_API_KEY")
    if not key:
        return []
    d = http_json("https://api.pexels.com/v1/search?per_page=8&orientation=portrait&query="
                  + urllib.parse.quote(q), {"Authorization": key})
    return [(p["src"]["large2x"], f"Foto: {p['photographer']} / Pexels") for p in d.get("photos", [])]


def suche_pixabay(q: str):
    key = os.environ.get("PIXABAY_API_KEY")
    if not key:
        return []
    d = http_json(f"https://pixabay.com/api/?key={key}&per_page=8&safesearch=true&q="
                  + urllib.parse.quote(q))
    return [(h["largeImageURL"], f"Bild: {h['user']} / Pixabay") for h in d.get("hits", [])]


def suche_openverse(q: str):
    basis = ("https://api.openverse.org/v1/images/?page_size=10&mature=false"
             "&license_type=commercial,modification&q=" + urllib.parse.quote(q))
    ergebnisse = []
    for extra in ("&aspect_ratio=tall", ""):  # Hochformat-Fotos zuerst
        for versuch in range(3):
            try:
                ergebnisse += http_json(basis + extra).get("results", [])
                break
            except urllib.error.HTTPError as e:
                if e.code != 429 or versuch == 2:
                    raise
                time.sleep(8 * (versuch + 1))  # zu viele Anfragen -> kurz warten
    out = []
    for r in ergebnisse:
        if (r.get("width") or 0) < 700:
            continue
        lic = f"CC {r.get('license', '').upper()} {r.get('license_version', '')}".strip()
        if r.get("license") in ("cc0", "pdm"):
            lic = "gemeinfrei"
        out.append((r["url"], f"„{r.get('title', '')[:60]}“ von {r.get('creator') or 'unbekannt'}"
                              f" ({lic}) – {r.get('foreign_landing_url', '')}"))
    return out


def suche_wikimedia(q: str):
    params = {"action": "query", "format": "json", "generator": "search",
              "gsrsearch": f"{q} filetype:bitmap", "gsrnamespace": 6, "gsrlimit": 10,
              "prop": "imageinfo", "iiprop": "url|extmetadata|size", "iiurlwidth": 1600}
    d = http_json("https://commons.wikimedia.org/w/api.php?" + urllib.parse.urlencode(params))
    out = []
    for p in sorted(d.get("query", {}).get("pages", {}).values(), key=lambda p: p.get("index", 99)):
        info = (p.get("imageinfo") or [{}])[0]
        if info.get("width", 0) < 700:
            continue
        meta = info.get("extmetadata", {})
        autor = " ".join(re.sub(r"<[^>]+>", " ", meta.get("Artist", {}).get("value", "")).split())[:60]
        lic = meta.get("LicenseShortName", {}).get("value", "")
        out.append((info.get("thumburl") or info["url"],
                    f"{p['title'].removeprefix('File:')} – {autor or 'unbekannt'} ({lic}), Wikimedia Commons"))
    return out


def ki_bild(prompt: str, stil: str, ziel: Path, seed: int) -> bool:
    """Kostenlose KI-Bilder über Pollinations (kein Konto nötig)."""
    voll = f"{prompt}, {stil}, vertical composition"
    url = (f"https://image.pollinations.ai/prompt/{urllib.parse.quote(voll)}"
           f"?width=1080&height=1920&nologo=true&seed={seed}")
    for versuch in range(5):
        if versuch:
            time.sleep(6 * versuch)  # kostenloser Dienst: bei Überlastung kurz warten
        try:
            daten = http_get(url, timeout=180)
            ziel.write_bytes(daten)
            img = Image.open(ziel)
            img.verify()
            img = Image.open(ziel).convert("RGB")
            # evtl. vorhandenes Wasserzeichen unten abschneiden
            img = img.crop((0, 0, img.width, int(img.height * 0.93)))
            img.save(ziel, "JPEG", quality=95)
            return True
        except Exception:
            continue
    return False


def platzhalter(begriff: str, ziel: Path) -> Path:
    a, b = random.Random(begriff).choice([((20, 24, 60), (120, 20, 90)), ((10, 50, 60), (10, 120, 110)),
                                          ((60, 20, 10), (160, 80, 10))])
    img = Image.new("RGB", (W, H))
    dr = ImageDraw.Draw(img)
    for y in range(H):
        t = y / H
        dr.line([(0, y), (W, y)], fill=tuple(int(a[i] + (b[i] - a[i]) * t) for i in range(3)))
    img.save(ziel)
    return ziel


def besorge_bilder(sk: Skript) -> None:
    ordner = CACHE / "bilder"
    ordner.mkdir(parents=True, exist_ok=True)
    benutzt: set[str] = set()
    letzte = None
    for i, sz in enumerate(sk.szenen):
        # 1) eigenes Bild / URL
        if sz.bild:
            if sz.bild.startswith("http"):
                ziel = ordner / f"u_{hashname(sz.bild)}.img"
                if not ziel.exists():
                    ziel.write_bytes(http_get(sz.bild))
                sz.bild_datei, sz.nachweis = ziel, sz.bild
            else:
                p = Path(sz.bild) if Path(sz.bild).is_absolute() else ROOT / sz.bild
                sz.bild_datei, sz.nachweis = p, "eigenes Bild"
            letzte = sz.bild_datei
            continue
        if not sz.suche and not sz.ki:
            if letzte:
                sz.bild_datei = letzte
                continue
            sz.suche = sk.titel
        quelle = sk.stil["bildquelle"]
        if sz.ki and not sz.suche:
            quelle = "ki"
        elif sz.suche and not sz.ki and quelle == "ki":
            quelle = "web"
        # 2) KI-Bild
        if quelle == "ki":
            ziel = ordner / f"k_{hashname(sz.ki, sk.stil['ki_stil'])}.jpg"
            if ziel.exists() or ki_bild(sz.ki, sk.stil["ki_stil"], ziel, int(hashname(sz.ki), 16) % 99999):
                sz.bild_datei, sz.nachweis = ziel, "KI-generiert (Pollinations)"
                letzte = ziel
                log(f"Bild {i + 1}: KI – {sz.ki[:60]}")
                continue
            sz.suche = sz.suche or sz.ki
        # 3) Websuche über mehrere Quellen
        treffer = None
        reihenfolge = {"wikimedia": [suche_wikimedia, suche_openverse],
                       "openverse": [suche_openverse, suche_wikimedia]}.get(sz.quelle or sk.quelle,
                                                                           [suche_wikimedia, suche_openverse])
        for f in [suche_pexels, suche_pixabay] + reihenfolge:
            try:
                kand = [k for k in f(sz.suche) if k[0] not in benutzt]
            except Exception as e:
                log(f"{f.__name__}: {type(e).__name__}")
                kand = []
            for url, nachweis in kand[:4]:
                ziel = ordner / f"w_{hashname(url)}.img"
                try:
                    if not ziel.exists():
                        ziel.write_bytes(http_get(url, timeout=40))
                    Image.open(ziel).verify()
                    treffer = (ziel, nachweis, url)
                    break
                except Exception:
                    ziel.unlink(missing_ok=True)
            if treffer:
                break
        if treffer:
            sz.bild_datei, sz.nachweis, url = treffer
            benutzt.add(url)
        elif sz.ki or sk.stil["bildquelle"] != "ki":
            ziel = ordner / f"k_{hashname(sz.suche, sk.stil['ki_stil'])}.jpg"
            if ziel.exists() or ki_bild(sz.suche, sk.stil["ki_stil"], ziel, 7):
                sz.bild_datei, sz.nachweis = ziel, "KI-generiert (Pollinations)"
        if not sz.bild_datei:
            sz.bild_datei = platzhalter(sz.suche, ordner / f"p_{hashname(sz.suche)}.png")
            sz.nachweis = "Platzhalter"
        letzte = sz.bild_datei
        log(f"Bild {i + 1}: {sz.nachweis[:70]}")


def bild_hochkant(quelle: Path, ziel: Path, vollbild: bool = True) -> Path:
    img = ImageOps.exif_transpose(Image.open(quelle)).convert("RGB")
    gross = (W * 2, H * 2)
    # Vollbild: wie bei TikTok üblich das ganze Bild füllen (nur sehr breite Panoramen bekommen Rahmen)
    if img.width / img.height > (1.9 if vollbild else 0.9):
        # Querformat: unscharfer Hintergrund + großes Bild in der Mitte
        hg = ImageOps.fit(img, gross).filter(ImageFilter.GaussianBlur(45))
        hg = Image.eval(hg, lambda v: int(v * 0.5))
        vh = int(gross[1] * 0.62)
        vw = int(img.width * vh / img.height)
        vg = img.resize((vw, vh), Image.LANCZOS)
        if vw > gross[0] * 1.35:                     # sehr breit -> etwas beschneiden
            vg = ImageOps.fit(vg, (int(gross[0] * 1.35), vh))
        hg.paste(vg, ((gross[0] - vg.width) // 2, (gross[1] - vh) // 2))
        img = hg
    else:
        img = ImageOps.fit(img, gross, Image.LANCZOS)
    img.save(ziel, quality=92)
    return ziel


# --------------------------------------------------------------------------- #
# Untertitel
# --------------------------------------------------------------------------- #
def ass_zeit(t: float) -> str:
    t = max(t, 0)
    return f"{int(t // 3600)}:{int(t % 3600 // 60):02d}:{t % 60:05.2f}"


def ass_text(s: str) -> str:
    return s.replace("\\", "").replace("{", "(").replace("}", ")")


def gruppiere(woerter: list[Wort], n: int) -> list[list[Wort]]:
    gruppen, akt = [], []
    for w in woerter:
        akt.append(w)
        if len(akt) >= n or re.search(r"[.!?,:;…]\**$", w.text):
            gruppen.append(akt)
            akt = []
    if akt:
        gruppen.append(akt)
    return gruppen


def passend(text: str, st: dict, max_breite: int = 960) -> float:
    """Skalierung in Prozent, damit lange Wörter nicht über den Bildrand laufen."""
    try:
        font = ImageFont.truetype(schrift_pfad(), st["schriftgroesse"])
        breite = font.getlength(text) + 2 * st["rand"]
    except OSError:
        return 100.0
    return 100.0 if breite <= max_breite else 100.0 * max_breite / breite


def schreibe_ass(sk: Skript, ziel: Path, gesamt: float) -> None:
    st = sk.stil
    font = schrift_name()
    rnd = random.Random(sk.name)
    kopf = f"""[Script Info]
ScriptType: v4.00+
PlayResX: {W}
PlayResY: {H}
WrapStyle: 2

[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
Style: U,{font},{st['schriftgroesse']},&H00FFFFFF,&H00FFFFFF,&H00000000,&H80000000,-1,0,0,0,100,100,0,0,1,{st['rand']},{3 if st['rand'] > 4 else 2},5,40,40,0,1
Style: Titel,{font},64,&H00000000,&H00000000,&H00FFFFFF,&H00000000,-1,0,0,0,100,100,0,0,3,20,0,8,80,80,200,1

[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
"""
    zeilen = []
    if sk.titel_einblenden and sk.titel:
        tt = r"\N".join(textwrap.wrap(ass_text(sk.titel.upper()), 22))
        zeilen.append(f"Dialogue: 1,{ass_zeit(0)},{ass_zeit(min(3.5, gesamt))},Titel,,0,0,0,,{tt}")

    alle: list[tuple[float, float, str]] = []
    offset = 0.0
    farb_i = 0
    for sz in sk.szenen:
        for g in gruppiere(sz.woerter, st["woerter_pro_untertitel"]):
            teile = []
            markiert = any("*" in w.text for w in g)
            # ohne Markierung: längstes Wort der Gruppe einfärben (wie im Vorbild)
            auto = max(g, key=lambda w: len(w.text)) if (st["farben"] and not markiert and len(g) > 1) else None
            for w in g:
                wort = w.text.replace("*", "")
                wort = wort.upper() if st["grossbuchstaben"] else wort
                wort = ass_text(re.sub(r"[.,;:!]+$", "", wort))
                if st["farben"] and ("*" in w.text or w is auto):
                    farbe = st["farben"][farb_i % len(st["farben"])]
                    farb_i += 1
                    teile.append(rf"{{\c{farbe}}}{wort}{{\c&HFFFFFF&}}")
                elif "*" in w.text:
                    teile.append(rf"{{\c&H00E5FF&}}{wort}{{\c&HFFFFFF&}}")
                else:
                    teile.append(wort)
            rein = " ".join(re.sub(r"[.,;:!]+$", "", w.text.replace("*", "")) for w in g)
            rein = rein.upper() if st["grossbuchstaben"] else rein
            alle.append((offset + g[0].start, offset + g[-1].ende, " ".join(teile), passend(rein, st)))
        offset += sz.dauer

    for k, (s, e, txt, sk_) in enumerate(alle):
        e = alle[k + 1][0] if k + 1 < len(alle) and alle[k + 1][0] - e < 0.6 else e + 0.15
        dreh = rf"\frz{rnd.uniform(-4, 4):.1f}" if st["drehen"] else ""
        pop = (rf"{{\pos(540,{st['y']}){dreh}\fscx{sk_ * .7:.0f}\fscy{sk_ * .7:.0f}"
               rf"\t(0,80,\fscx{sk_ * 1.08:.0f}\fscy{sk_ * 1.08:.0f})\t(80,140,\fscx{sk_:.0f}\fscy{sk_:.0f})}}")
        zeilen.append(f"Dialogue: 0,{ass_zeit(s)},{ass_zeit(e)},U,,0,0,0,,{pop}{txt}")
    ziel.write_text(kopf + "\n".join(zeilen) + "\n", encoding="utf-8")


# --------------------------------------------------------------------------- #
# Video
# --------------------------------------------------------------------------- #
def szenenclip(i: int, sz: Szene, zoom: float, arbeit: Path, vollbild: bool) -> Path:
    bild = bild_hochkant(sz.bild_datei, arbeit / f"b{i:02d}.jpg", vollbild)
    n = max(1, round(sz.dauer * FPS))
    z = f"1+{zoom}*on/{n}" if i % 2 == 0 else f"{1 + zoom}-{zoom}*on/{n}"
    r = 1 if i % 4 < 2 else -1
    x = f"(iw-iw/zoom)/2+{r}*(iw-iw/zoom)*0.35*(on/{n}-0.5)"
    clip = arbeit / f"c{i:02d}.mp4"
    run(["ffmpeg", "-y", "-v", "error", "-i", str(bild), "-vf",
         f"zoompan=z='{z}':x='{x}':y='(ih-ih/zoom)/2':d={n}:s={W}x{H}:fps={FPS},format=yuv420p",
         "-frames:v", str(n), "-c:v", "libx264", "-preset", "veryfast", "-crf", "19", str(clip)])
    return clip


def finde_musik(name: str | None) -> Path | None:
    if not name or name == "keine":
        return None
    p = Path(name) if Path(name).is_absolute() else ROOT / name
    if p.exists():
        return p
    if name in ("synthwave", "ambient"):
        from musik import erzeuge
        ziel = CACHE / f"musik_{name}.wav"
        if not ziel.exists():
            CACHE.mkdir(exist_ok=True)
            erzeuge(name, ziel)
        return ziel
    log(f"Musik nicht gefunden: {name}")
    return None


def baue_video(sk: Skript, musik_arg: str | None) -> Path:
    arbeit = CACHE / "arbeit" / sk.name
    shutil.rmtree(arbeit, ignore_errors=True)
    arbeit.mkdir(parents=True)
    AUSGABE.mkdir(exist_ok=True)

    clips = [szenenclip(i, sz, sk.stil["zoom"], arbeit, sk.stil.get("vollbild", True)) for i, sz in enumerate(sk.szenen)]
    (arbeit / "v.txt").write_text("".join(f"file '{c.as_posix()}'\n" for c in clips))
    stumm = arbeit / "stumm.mp4"
    run(["ffmpeg", "-y", "-v", "error", "-f", "concat", "-safe", "0", "-i", str(arbeit / "v.txt"),
         "-c", "copy", str(stumm)])

    wavs = []
    for i, sz in enumerate(sk.szenen):
        wav = arbeit / f"a{i:02d}.wav"
        run(["ffmpeg", "-y", "-v", "error", "-i", str(sz.audio), "-af",
             f"apad=whole_dur={sz.dauer:.3f}", "-ar", "44100", "-ac", "2", "-t", f"{sz.dauer:.3f}", str(wav)])
        wavs.append(wav)
    (arbeit / "a.txt").write_text("".join(f"file '{w.as_posix()}'\n" for w in wavs))
    sprache = arbeit / "sprache.wav"
    run(["ffmpeg", "-y", "-v", "error", "-f", "concat", "-safe", "0", "-i", str(arbeit / "a.txt"),
         "-c", "copy", str(sprache)])

    gesamt = sum(sz.dauer for sz in sk.szenen) + 0.4
    ass = arbeit / "u.ass"
    schreibe_ass(sk, ass, gesamt)
    ass_pfad = ass.as_posix().replace(":", r"\:").replace("'", r"\'")

    fv = f"[0:v]tpad=stop_mode=clone:stop_duration=0.5,ass='{ass_pfad}'"
    if sk.fortschritt:
        fv += (f"[s];color=c=0xFFD700:s={W}x12:r={FPS}[bar];"
               f"[s][bar]overlay=x='-W+W*t/{gesamt:.3f}':y=H-12:shortest=1")
    fv += "[v]"
    cmd = ["ffmpeg", "-y", "-v", "error", "-i", str(stumm), "-i", str(sprache)]
    musik = finde_musik(musik_arg or sk.musik)
    if musik:
        cmd += ["-stream_loop", "-1", "-i", str(musik)]
        fa = (f"[1:a]volume=1.0[s];[2:a]volume=0.16,afade=t=out:st={gesamt - 1.2:.2f}:d=1.2[m];"
              "[s][m]amix=inputs=2:duration=longest:normalize=0[a]")
    else:
        fa = "[1:a]anull[a]"
    ziel = AUSGABE / f"{sk.name}.mp4"
    cmd += ["-filter_complex", fv + ";" + fa, "-map", "[v]", "-map", "[a]", "-t", f"{gesamt:.3f}",
            "-c:v", "libx264", "-preset", "medium", "-crf", "19", "-pix_fmt", "yuv420p",
            "-c:a", "aac", "-b:a", "192k", "-movflags", "+faststart", str(ziel)]
    run(cmd)
    return ziel


def schreibe_infos(sk: Skript, video: Path) -> Path:
    tags = " ".join(h if h.startswith("#") else f"#{h}" for h in sk.hashtags)
    nachweise = sorted({s.nachweis for s in sk.szenen if s.nachweis not in ("", "eigenes Bild", "Platzhalter")})
    info = video.with_suffix(".txt")
    info.write_text(
        f"TITEL / ERSTE ZEILE:\n{sk.titel}\n\nBESCHREIBUNG (kopieren & einfügen):\n{sk.beschreibung}\n\n{tags}\n\n"
        "BILDNACHWEISE (CC-Lizenzen verlangen Namensnennung – in die Beschreibung oder einen Kommentar):\n"
        + "\n".join(f"- {n}" for n in nachweise) + "\n", encoding="utf-8")
    return info


def main() -> None:
    ap = argparse.ArgumentParser(description="Erstellt deutsche Faceless-Shorts aus YAML-Skripten.")
    ap.add_argument("skripte", nargs="+", type=Path)
    ap.add_argument("--tts", choices=["edge", "gtts"], default="edge")
    ap.add_argument("--stimme", help="z.B. de-DE-ConradNeural, de-DE-KatjaNeural, de-DE-FlorianMultilingualNeural")
    ap.add_argument("--musik", help="MP3-Datei, 'synthwave', 'ambient' oder 'keine'")
    args = ap.parse_args()
    if not shutil.which("ffmpeg"):
        sys.exit("FEHLER: ffmpeg fehlt – siehe README.md")
    for pfad in args.skripte:
        print(f"\n▶ {pfad.name}")
        sk = lade_skript(pfad)
        if args.stimme:
            sk.stil["stimme"] = args.stimme
        erzeuge_audio(sk, args.tts)
        besorge_bilder(sk)
        video = baue_video(sk, args.musik)
        info = schreibe_infos(sk, video)
        print(f"✔ {video.relative_to(ROOT)}  ({dauer(video):.0f} Sek.)  |  Upload-Text: {info.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
