from __future__ import annotations

import os
import time
import uuid
from pathlib import Path

import requests

REPO_ROOT = Path(__file__).resolve().parents[1]
GENERATED_AUDIO_DIR = REPO_ROOT / "audios" / "generated"


def generate_audio_filename(response_format: str | None = None) -> str:
    if response_format is None:
        response_format = os.environ.get("TTS_RESPONSE_FORMAT", "wav")
    timestamp = time.strftime("%Y%m%d_%H%M%S")
    random_suffix = uuid.uuid4().hex[:8]
    return f"assistant_{timestamp}_{random_suffix}.{response_format}"


def synthesize_text(text: str, output_path: Path | None = None) -> dict:
    tts_base_url = os.environ["TTS_BASE_URL"]
    voice = os.environ["TTS_VOICE"]
    seed = int(os.environ["TTS_SEED"])
    temperature = float(os.environ["TTS_TEMPERATURE"])
    response_format = os.environ["TTS_RESPONSE_FORMAT"]

    if output_path is None:
        output_filename = generate_audio_filename(response_format)
        output_path = GENERATED_AUDIO_DIR / output_filename
    else:
        output_filename = output_path.name

    payload = {
        "input": text,
        "voice": voice,
        "response_format": response_format,
        "seed": seed,
        "temperature": temperature,
    }

    response = requests.post(
        f"{tts_base_url}/audio/speech",
        json=payload,
        timeout=120,
    )
    response.raise_for_status()

    with open(output_path, "wb") as f:
        f.write(response.content)

    return {
        "audio_path": str(output_path),
        "filename": output_filename,
    }
