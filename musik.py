"""
Erzeugt lizenzfreie Hintergrundmusik direkt am Computer (keine Urheberrechtsprobleme).

  synthwave -> treibender Retro-Synth (passt zu "Zufällige Fakten")
  ambient   -> ruhige, mystische Flächen (passt zu Psychologie-Videos)

Eigene Musik: einfach eine MP3 in assets/musik/ legen und im Skript
`musik: assets/musik/datei.mp3` eintragen. Tipp: In TikTok/YouTube kannst du
auch nach dem Hochladen einen Trend-Sound aus der App-Bibliothek darüberlegen.
"""
from __future__ import annotations

import sys
import wave
from pathlib import Path

import numpy as np

SR = 44100


def _note(n: int) -> float:  # MIDI -> Hz
    return 440.0 * 2 ** ((n - 69) / 12)


def _hall(x: np.ndarray, verz=(0.031, 0.047, 0.071, 0.113), fb=0.35) -> np.ndarray:
    out = x.copy()
    for d in verz:
        k = int(d * SR)
        y = np.zeros_like(x)
        y[k:] = x[:-k] * fb
        out += y
    return out


def erzeuge(stil: str, ziel: Path, takte: int = 8) -> Path:
    rng = np.random.default_rng(3)
    if stil == "synthwave":
        bpm, akkorde = 100, [[57, 60, 64], [53, 57, 60], [48, 52, 55], [55, 59, 62]]  # Am F C G
    else:
        bpm, akkorde = 70, [[50, 57, 62, 65], [46, 53, 58, 62], [48, 55, 60, 64], [45, 52, 57, 60]]
    takt = 4 * 60 / bpm
    n = int(takt * takte * SR)
    t = np.arange(n) / SR
    mix = np.zeros(n + SR)  # 1 s Reserve, wird am Ende abgeschnitten

    for k in range(takte):
        akk = akkorde[k % len(akkorde)]
        a, b = int(k * takt * SR), int((k + 1) * takt * SR)
        tt = t[a:b] - t[a]
        hull = np.minimum(1, tt / 0.4) * np.minimum(1, (takt - tt) / 0.3)
        for m in akk:
            f = _note(m)
            for verstimmung in (-0.12, 0.0, 0.12):  # breite Fläche durch Verstimmung
                ph = 2 * np.pi * f * (1 + verstimmung / 100) * tt
                welle = np.sin(ph) + (0.3 * np.sin(2 * ph) if stil == "synthwave" else 0)
                mix[a:b] += welle * hull * 0.05
        # Bass
        fb = _note(akk[0] - 12)
        if stil == "synthwave":
            achtel = takt / 8
            for j in range(8):
                s = a + int(j * achtel * SR)
                e = s + int(achtel * 0.85 * SR)
                ts = np.arange(e - s) / SR
                saw = 2 * ((fb * ts) % 1) - 1
                mix[s:e] += saw * np.exp(-ts * 6) * 0.12
        else:
            mix[a:b] += np.sin(2 * np.pi * fb * tt) * hull * 0.10
        # Arpeggio / Glitzer
        schritte = 16 if stil == "synthwave" else 8
        for j in range(schritte):
            s = a + int(j * takt / schritte * SR)
            ln = int(0.18 * SR)
            ts = np.arange(ln) / SR
            ton = _note(akk[j % len(akk)] + 12 + (12 if j % 4 == 3 else 0))
            if stil == "ambient" and rng.random() < 0.5:
                continue
            mix[s:s + ln] += np.sin(2 * np.pi * ton * ts) * np.exp(-ts * 12) * 0.05
    if stil == "synthwave":  # sanfte Drums
        schlag = 60 / bpm
        for j in range(int(takt * takte / schlag)):
            s = int(j * schlag * SR)
            ts = np.arange(int(0.25 * SR)) / SR
            kick = np.sin(2 * np.pi * (50 + 80 * np.exp(-ts * 30)) * ts) * np.exp(-ts * 9) * 0.35
            mix[s:s + len(ts)] += kick
            if j % 2 == 1:
                rs = np.arange(int(0.2 * SR)) / SR
                snare = rng.normal(0, 1, len(rs)) * np.exp(-rs * 18) * 0.08
                mix[s:s + len(rs)] += snare
            h = s + int(schlag / 2 * SR)
            hs = np.arange(int(0.05 * SR)) / SR
            if h + len(hs) < n:
                mix[h:h + len(hs)] += rng.normal(0, 1, len(hs)) * np.exp(-hs * 60) * 0.03

    mix = _hall(mix)[:n]
    mix = mix / (np.max(np.abs(mix)) + 1e-9) * 0.8
    links = mix
    rechts = np.roll(mix, int(0.012 * SR))
    st = (np.stack([links, rechts], 1) * 32767).astype(np.int16)
    with wave.open(str(ziel), "wb") as w:
        w.setnchannels(2)
        w.setsampwidth(2)
        w.setframerate(SR)
        w.writeframes(st.tobytes())
    return ziel


if __name__ == "__main__":
    stil = sys.argv[1] if len(sys.argv) > 1 else "synthwave"
    print(erzeuge(stil, Path(f"musik_{stil}.wav")))
