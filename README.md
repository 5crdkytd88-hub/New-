# 🎬 Faceless Shorts auf Deutsch

Erstellt automatisch fertige Hochkant-Videos (1080×1920) für **TikTok, YouTube Shorts und Instagram Reels**, ohne dass du dich zeigen musst.
Du schreibst nur den Text, den Rest übernimmt das Tool:

- 🗣️ **Deutsche KI-Stimme** (Microsoft-Neural-Stimmen über `edge-tts`, kostenlos)
- 🖼️ **Bilder aus dem ganzen Internet**: Openverse (Flickr & Co.), Wikimedia Commons, Pexels, Pixabay, dazu **KI-Bilder** (kostenlos, ohne Konto)
- 🔤 **Untertitel Wort für Wort**, synchron zur Stimme, Schlüsselwörter bunt
- 🎥 Zoom-Effekt auf jedem Bild, schnelle Bildwechsel
- 🎵 **Lizenzfreie Hintergrundmusik**, die das Tool selbst erzeugt (Synthwave/Ambient)
- 📝 Textdatei mit Titel, Beschreibung, Hashtags und **Bildnachweisen** zum Hochladen

## Die zwei Stile (nach deinen Beispielvideos)

| `stil: fakten` | `stil: psycho` |
|---|---|
| wie „Zufällige Fakten 🧠“ | wie „Hast du gewusst, dass …?“ |
| echte Fotos aus dem Internet, Vollbild | KI-Bilder im Neon-Hologramm-Look |
| 2 Wörter pro Untertitel, GROSS, bunt, leicht schräg | 1 Wort pro Untertitel, ruhig in der Mitte |
| schnelle Stimme, Synthwave-Musik | ruhige Stimme, Ambient-Musik |

Fertige Beispiele liegen in `ausgabe/`.

---

## Installation (einmalig)

1. **Python 3.10+** installieren: https://www.python.org/downloads/ (unter Windows „Add to PATH“ anhaken)
2. **ffmpeg** installieren:
   - Windows: `winget install ffmpeg`
   - Mac: `brew install ffmpeg`
   - Linux: `sudo apt install ffmpeg`
3. Im Projektordner:
   ```bash
   pip install -r requirements.txt
   ```

## Ein Video erstellen

```bash
python shorts.py skripte/fakten_01.yaml
```

Alle Skripte auf einmal:

```bash
python shorts.py skripte/*.yaml
```

Das fertige Video landet in `ausgabe/`, daneben eine `.txt` mit dem Text zum Hochladen.

**Optionen**

```bash
python shorts.py skripte/x.yaml --stimme de-DE-KatjaNeural     # weibliche Stimme
python shorts.py skripte/x.yaml --musik assets/musik/song.mp3  # eigene Musik
python shorts.py skripte/x.yaml --musik keine                  # ohne Musik (Trend-Sound später in der App)
```

Gute deutsche Stimmen: `de-DE-ConradNeural` (männlich, kräftig), `de-DE-FlorianMultilingualNeural` (männlich, ruhig), `de-DE-KatjaNeural` / `de-DE-SeraphinaMultilingualNeural` (weiblich), `de-AT-JonasNeural` (österreichisch).

**Mehr und bessere Fotos (optional, kostenlos):** API-Schlüssel bei https://www.pexels.com/api/ und/oder https://pixabay.com/api/docs/ holen und setzen:

```bash
# Mac/Linux
export PEXELS_API_KEY="dein-schluessel"
# Windows (PowerShell)
$env:PEXELS_API_KEY="dein-schluessel"
```

---

## Ein eigenes Skript schreiben

Kopiere eine Datei aus `skripte/` und ändere sie. Jede Szene ist **ein Satz und ein Bild**.

```yaml
stil: fakten                      # oder: psycho
titel: "Diese 7 Fakten glaubt dir niemand"
beschreibung: "Welchen kanntest du? 👇"
hashtags: [fakten, wusstestdu, deutsch]
szenen:
  - text: "Ein Oktopus hat *drei Herzen*."    # *Wort* = farbig hervorgehoben
    suche: "octopus"                         # Foto aus dem Internet suchen (Englisch = mehr Treffer)
  - text: "Und sein Blut ist *blau*."
    ki: "octopus with glowing blue veins, macro photo"   # KI-Bild nach Beschreibung
  - text: "Das ist mein eigenes Bild."
    bild: assets/bilder/foto.jpg             # eigenes Bild oder URL
```

- `suche:` → Foto aus dem Internet
- `ki:` → KI-Bild (bei `stil: psycho` wird der Neon-Look automatisch ergänzt)
- nichts angegeben → das Bild der vorherigen Szene bleibt stehen

---

## 🧠 So hältst du Zuschauer bis zum Ende (Neugier-Formeln)

Der Algorithmus belohnt vor allem eins: **Wie viel vom Video angeschaut wird.** Diese Techniken stecken in den Beispielskripten:

### 1. Der Hook (die ersten 1–2 Sekunden)
Der erste Satz muss eine **Lücke im Kopf** öffnen. Niemals mit „Hallo“ oder „Heute zeige ich euch …“ anfangen.

- **„Hast du gewusst, dass …?“** + etwas, das unlogisch klingt
  → „Hast du gewusst, dass unpünktliche Menschen oft kreativer sind?“
- **Unmöglicher Vergleich**
  → „Kleopatra lebte näher an der Mondlandung als am Bau der Pyramiden.“
- **Ein kleines Ding mit großer Folge**
  → „Ein winziger Schlüssel könnte schuld am Untergang der Titanic sein.“
- **Direkte Ansprache + Geheimnis**
  → „Dein Gehirn tut gerade etwas, ohne dass du es merkst.“
- **Warnung / Verbot**
  → „Versuch nicht, dieses Video ohne Blinzeln anzuschauen.“

### 2. Offene Schleifen (Open Loops)
Kündige etwas an, das erst später kommt:
„… aber der verrückteste Fakt kommt am Ende.“ · „Und genau hier wird es seltsam.“ · „Aber hier ist das Beste:“

### 3. Tempo
- **Ein Satz = ein Bild.** Spätestens alle 2–3 Sekunden ein neues Bild.
- Kurze Sätze, keine Füllwörter. Ideal: **20–45 Sekunden**.

### 4. Das Ende
- **Loop-Ende:** Der letzte Satz führt zurück zum Anfang, dann schauen viele das Video ein zweites Mal (zählt doppelt).
  → „… und genau deshalb bist du bis zum Ende geblieben.“
- **Kommentar-Frage:** „Welchen Fakt kanntest du noch nicht? Schreib die Nummer in die Kommentare.“
- **Folgen-Grund:** „Folge mir, die nächste Geschichte ist noch verrückter.“

### 5. Themen, die auf Deutsch gut laufen
Psychologie & Gehirn · Zufällige Fakten · Geschichte mit Wendung (Titanic, Römer, Weltkriege) · Weltall · Tiere · Geld & Reichtum · Lost Places · ungelöste Rätsel · „Dinge, die du falsch machst“

---

## Hochladen: Checkliste

1. Video aus `ausgabe/` aufs Handy schicken (AirDrop, Google Drive, Telegram an dich selbst)
2. In TikTok/YouTube hochladen, **Beschreibung + Hashtags** aus der `.txt` einfügen
3. **Bildnachweise:** Bilder mit CC-BY/CC-BY-SA-Lizenz verlangen eine Namensnennung, also die Zeilen aus der `.txt` in die Beschreibung oder einen angepinnten Kommentar kopieren. Wer das nicht will, nimmt `ki:`-Bilder oder Pexels/Pixabay (keine Namensnennung nötig).
4. TikTok: Bei KI-Inhalten den Schalter **„KI-generierter Inhalt“** aktivieren.
5. Regelmäßig posten (1–3 Videos am Tag), immer im selben Stil, damit der Kanal erkennbar wird.

> ⚠️ **Fakten prüfen!** Falsche „Fakten“ werden in den Kommentaren schnell zerrissen und können zu Sperren führen. Lieber ein Fakt weniger als ein falscher.

## Ordner

```
shorts.py        # der Generator
musik.py         # erzeugt lizenzfreie Hintergrundmusik
skripte/         # deine Video-Skripte (YAML)
assets/bilder/   # eigene Bilder
assets/musik/    # eigene Musik (MP3)
ausgabe/         # fertige Videos + Upload-Texte
```
