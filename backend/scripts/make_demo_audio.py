"""Render a synthetic demo song (no copyright issues) for trying the app.

python -m scripts.make_demo_audio            # -> demo-song.wav (+ .mp3 if FFmpeg exists)
python -m scripts.make_demo_audio out.wav
"""

from __future__ import annotations

import shutil
import subprocess
import sys
from pathlib import Path

import soundfile as sf

from app.devtools.synth import SongSection, render_song


def main() -> None:
    target = Path(sys.argv[1] if len(sys.argv) > 1 else "demo-song.wav")
    intro = SongSection(["G", "C"] * 2, timbre="pad", drums=False, gain=0.5)
    verse = SongSection(["G", "D/F#", "Em", "C"] * 2, gain=0.7)
    chorus = SongSection(["C", "D", "G", "Em", "C", "D", "G", "G"], gain=1.0)
    bridge = SongSection(["Am7", "Em", "C", "D", "Am7", "Em", "Dsus4", "D"], timbre="pad")
    outro = SongSection(["G", "C", "G", "G"], timbre="pad", drums=False, gain=0.5)
    form = [intro, verse, chorus, verse, chorus, bridge, chorus, outro]
    samples = render_song(form, bpm=92, beats_per_bar=4, lead_in_seconds=0.6)
    sf.write(str(target), samples, 22050)
    print(f"wrote {target}  (G major, 92 BPM, 4/4)")
    if shutil.which("ffmpeg"):
        mp3 = target.with_suffix(".mp3")
        cmd = ["ffmpeg", "-y", "-loglevel", "error", "-i", str(target), "-b:a", "160k", str(mp3)]
        subprocess.run(cmd, check=True)
        print(f"wrote {mp3}")


if __name__ == "__main__":
    main()
