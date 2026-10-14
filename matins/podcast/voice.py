"""Read a spoken script aloud with Kokoro (kokoro-onnx).

  voice = Voice(model_dir, "bm_lewis")
  wave, rate = voice.read(segments, speed=0.95)

A voice is a name ("bm_lewis"), a blend ("am_michael:0.5+am_puck:0.5"),
optionally with "@en-us" / "@en-gb" to choose the pronunciation.
"""

import os
import pathlib

import espeakng_loader
import numpy as np
from kokoro_onnx import EspeakConfig, Kokoro
from phonemizer.backend.espeak.wrapper import EspeakWrapper


class Voice:
    def __init__(self, model_dir, voice):
        model_dir = os.path.abspath(model_dir)
        # The bundled espeak-ng wants the folder that contains espeak-ng-data,
        # as a short path; phonemizer always expands the path it is given, so
        # work from that folder and pin the path to ".".
        os.chdir(os.path.dirname(espeakng_loader.get_data_path()))
        EspeakWrapper.data_path = property(lambda self: pathlib.Path("."))
        self.kokoro = Kokoro(os.path.join(model_dir, "kokoro-v1.0.onnx"), os.path.join(model_dir, "voices-v1.0.bin"),
                             espeak_config=EspeakConfig(lib_path=espeakng_loader.get_library_path(), data_path="."))
        name, _, lang = voice.partition("@")
        if "+" in name or ":" in name:
            parts = [(n, float(w or 1)) for n, _, w in (x.partition(":") for x in name.split("+"))]
            self.style = sum(self.kokoro.get_voice_style(n) * w for n, w in parts) / sum(w for _, w in parts)
        else:
            self.style = name
        self.lang = lang or ("en-gb" if name.startswith("b") else "en-us")

    def read(self, segments, speed=0.95):
        audio, rate = [], 24000
        for text, pause in segments:
            samples, rate = self.kokoro.create(text, voice=self.style, speed=speed, lang=self.lang)
            audio.append(samples)
            audio.append(np.zeros(int(rate * pause), dtype=samples.dtype))
        return np.concatenate(audio), rate
