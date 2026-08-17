from __future__ import annotations

import sys
import time
import uuid
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
MOSS_TTS_DIR = REPO_ROOT / "MOSS-TTS-Nano"

if str(MOSS_TTS_DIR) not in sys.path:
    sys.path.insert(0, str(MOSS_TTS_DIR))

from onnx_tts_runtime import OnnxTtsRuntime
AUDIO_DIR = REPO_ROOT / "audios"
GENERATED_AUDIO_DIR = AUDIO_DIR / "generated"
REFERENCE_AUDIO = AUDIO_DIR / "referencia_neutra.wav"

_tts_runtime: OnnxTtsRuntime | None = None


def get_tts_runtime() -> OnnxTtsRuntime:
    global _tts_runtime
    if _tts_runtime is None:
        model_dir = REPO_ROOT / "MOSS-TTS-Nano" / "models"
        _tts_runtime = OnnxTtsRuntime(
            model_dir=str(model_dir),
            thread_count=4,
            execution_provider="cpu",
            output_dir=str(GENERATED_AUDIO_DIR),
        )
    return _tts_runtime


def synthesize_text(text: str) -> dict:
    runtime = get_tts_runtime()
    timestamp = time.strftime("%Y%m%d_%H%M%S")
    random_suffix = uuid.uuid4().hex[:8]
    output_filename = f"assistant_{timestamp}_{random_suffix}.wav"
    output_path = GENERATED_AUDIO_DIR / output_filename

    result = runtime.synthesize(
        text=text,
        prompt_audio_path=str(REFERENCE_AUDIO),
        output_audio_path=str(output_path),
        sample_mode="fixed",
        do_sample=True,
        streaming=True,
        max_new_frames=375,
        voice_clone_max_text_tokens=75,
        enable_wetext=False,
        enable_normalize_tts_text=False,
    )

    return {
        "audio_path": result["audio_path"],
        "sample_rate": result["sample_rate"],
        "filename": output_filename,
    }
