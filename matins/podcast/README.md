# Podcast

Reads the daily readings aloud for the Matins podcast at matutinum.org.

- `script.py`: daily-data JSON to a spoken script (cues such as "First Nocturn",
  "Lesson one", pauses, and spoken-only respellings like Machabees -> Maccabees).
- `voice.py`: Kokoro (kokoro-onnx) text-to-speech; the feed uses Lewis blended with
  Fable (`bm_lewis:0.7+bm_fable:0.3`) at 0.92, softened in `render.py` (EQ, de-esser, 96k).
- `render.py`: renders the days that have no episode yet and uploads them to
  the R2 bucket as `podcast/<calendar>/<lang>/<date>.mp3`; run by the
  `podcast` job in `.github/workflows/daily-readings.yml`.
