from __future__ import annotations

import base64
import json
import time
from pathlib import Path
from typing import Any

import requests

from ..config import settings


def transcribe(file_path: str) -> list[list[Any]]:
    """Единая точка транскрипции. Провайдер выбирается через TRANSCRIPTION_PROVIDER."""
    provider = settings.transcription_provider.strip().lower()

    if provider == "yandex_async":
        return _transcribe_yandex_async(file_path)
    if provider == "openai_whisper":
        return _transcribe_openai_whisper(file_path)

    raise ValueError(f"Unknown transcription provider: {provider}")


def _transcribe_yandex_async(file_path: str) -> list[list[Any]]:
    api_key = settings.yandex_api_key
    folder_id = settings.yandex_folder_id
    if not api_key or not folder_id:
        raise RuntimeError("YANDEX_API_KEY and YANDEX_FOLDER_ID are required for yandex_async transcription")

    with Path(file_path).open("rb") as fh:
        audio_b64 = base64.b64encode(fh.read()).decode("utf-8")

    headers = {
        "Authorization": f"Api-Key {api_key}",
        "x-folder-id": folder_id,
        "Content-Type": "application/json",
    }

    timeout = settings.yandex_stt_http_timeout_seconds
    poll_timeout = settings.yandex_stt_poll_timeout_seconds
    poll_interval = settings.yandex_stt_poll_interval_seconds
    return_partial_on_timeout = settings.yandex_stt_return_partial_on_timeout

    session = requests.Session()
    session.trust_env = settings.yandex_stt_trust_env

    body = {
        "content": audio_b64,
        "recognitionModel": {
            "model": settings.yandex_stt_model,
            "audioFormat": {"containerAudio": {"containerAudioType": _detect_container_type(file_path)}},
            "textNormalization": {
                "textNormalization": settings.yandex_stt_text_normalization,
                "profanityFilter": settings.yandex_stt_profanity_filter,
                "literatureText": settings.yandex_stt_literature_text,
            },
        },
    }

    try:
        start_response = session.post(
            "https://stt.api.cloud.yandex.net/stt/v3/recognizeFileAsync",
            headers=headers,
            data=json.dumps(body),
            timeout=timeout,
        )
    except requests.RequestException as exc:
        raise RuntimeError("Yandex STT network error on recognizeFileAsync") from exc

    if not start_response.ok:
        raise RuntimeError(f"Yandex recognizeFileAsync failed: {start_response.text}")

    start_payload = _safe_response_json(start_response)
    operation_id = str(start_payload.get("id", ""))

    if not operation_id:
        raise RuntimeError("Yandex recognizeFileAsync did not return operation id")

    deadline = time.time() + poll_timeout
    last_payload_with_text: dict[str, Any] | None = None

    while time.time() < deadline:
        try:
            poll_response = session.get(
                "https://stt.api.cloud.yandex.net/stt/v3/getRecognition",
                headers=headers,
                params={"operation_id": operation_id},
                timeout=timeout,
            )
        except requests.RequestException as exc:
            raise RuntimeError("Yandex STT network error on getRecognition") from exc

        if not poll_response.ok:
            if _is_yandex_not_ready_error(poll_response):
                time.sleep(poll_interval)
                continue
            raise RuntimeError(f"Yandex getRecognition failed: {poll_response.text}")

        payload = _safe_response_json(poll_response)

        if _payload_has_any_text(payload):
            last_payload_with_text = payload

        if _recognition_is_done(payload):
            return _extract_transcript_from_yandex(payload)

        time.sleep(poll_interval)

    if return_partial_on_timeout and last_payload_with_text:
        transcript = _extract_transcript_from_yandex(last_payload_with_text)
        if transcript:
            return transcript

    raise RuntimeError(f"Yandex recognition timeout after {poll_timeout} seconds")


def _openai_request_kwargs() -> dict[str, Any]:
    kwargs: dict[str, Any] = {}
    if settings.openai_proxy_url:
        kwargs["proxies"] = {"http": settings.openai_proxy_url, "https": settings.openai_proxy_url}
    return kwargs


def _transcribe_openai_whisper(file_path: str) -> list[list[Any]]:
    api_key = settings.openai_api_key
    if not api_key:
        raise RuntimeError("OPENAI_API_KEY is required for openai_whisper")

    url = "https://api.openai.com/v1/audio/transcriptions"
    headers = {"Authorization": f"Bearer {api_key}", "Accept": "application/json"}

    files = {"file": (Path(file_path).name, open(file_path, "rb"), "audio/mpeg")}
    data = {"model": settings.openai_transcribe_model, "response_format": "verbose_json"}
    if settings.openai_transcribe_language:
        data["language"] = settings.openai_transcribe_language

    try:
        resp = requests.post(
            url,
            headers=headers,
            files=files,
            data=data,
            timeout=(30, 300),
            **_openai_request_kwargs(),
        )
        resp.raise_for_status()
    except requests.RequestException as exc:
        error_msg = "Unknown error"
        try:
            error_msg = resp.json().get("error", {}).get("message", str(exc))
        except Exception:
            if "resp" in locals():
                error_msg = resp.text[:400]
        raise RuntimeError(f"OpenAI Whisper failed: {error_msg}") from exc

    try:
        result = resp.json()
    except json.JSONDecodeError:
        raise RuntimeError(f"Invalid JSON from OpenAI: {resp.text[:400]}")

    transcript: list[list[Any]] = []
    segments = result.get("segments", [])
    if segments:
        for seg in segments:
            text = (seg.get("text") or "").strip()
            start = float(seg.get("start") or 0.0)
            if text:
                transcript.append([text, start])
    else:
        text = (result.get("text") or "").strip()
        if text:
            transcript.append([text, 0.0])

    return transcript


def diarize_transcript(transcription: Any) -> dict[str, str]:
    segments = _normalize_transcript_segments(transcription)
    if not segments:
        return {}

    dialog_for_model = "\n".join(f"{_seconds_to_mmss(start)} | {text}" for text, start in segments)

    prompt = """Ты делаешь диаризацию разговора менеджера и клиента.
Верни строго JSON-объект без markdown.
Формат:
{
  "speaker_map": {
    "MM:SS": "operator|client|unknown"
  }
}
Правила:
- Ключи — время начала реплики из входных данных.
- Значения только: operator, client, unknown.
- Не добавляй новые таймкоды, которых не было во входе.
- Если не уверен, ставь unknown.

Диалог:
""" + dialog_for_model

    messages = [
        {"role": "system", "content": prompt},
        {"role": "user", "content": "Проанализируй и верни только JSON."},
    ]
    return _openai_chat_completion_request(messages, model=settings.openai_diarization_model)


def ai_analysis(transcription: Any, speaker_map: dict[str, str] | None = None) -> Any:
    normalized = _normalize_transcript_segments(transcription)
    speaker_map = speaker_map or {}

    dialog_lines = []
    for text, start in normalized:
        ts = _seconds_to_mmss(start)
        role = speaker_map.get(ts, "unknown")
        dialog_lines.append(f"[{ts}] [{role}] {text}")

    dialog_text = "\n".join(dialog_lines) if dialog_lines else str(transcription)

    system_prompt = """Ты контролер качества звонков. Тебе даётся разговор в формате:
[MM:SS] [operator|client|unknown] текст реплики.
Сами диалоги могут быть немного искажены. Не галлюцинируй.

Проанализируй разговор оператора с клиентом.
Ответь строго JSON:
{
"summary": "1-3 предложения: о чем был диалог и какие договоренности/результаты достигнуты",
"name_used": true/false,
"pain_identified": true/false,
"solution_offered": true/false,
"chat_invite": true/false,
"next_step_agreed": true/false,
"score": 1-5,
"mistakes": [список],
"recommendations": [список]
}

Разговор:
"""

    messages = [
        {"role": "system", "content": system_prompt + dialog_text},
        {"role": "user", "content": "Верни только JSON без пояснений."},
    ]
    return _openai_chat_completion_request(messages, model=settings.openai_analysis_model)


def _openai_chat_completion_request(messages: list[dict[str, str]], model: str) -> Any:
    if not settings.openai_api_key:
        raise RuntimeError("OPENAI_API_KEY required")

    url = "https://api.openai.com/v1/chat/completions"
    headers = {
        "Authorization": f"Bearer {settings.openai_api_key}",
        "Content-Type": "application/json",
    }
    payload = {
        "model": model,
        "messages": messages,
        "temperature": 0.0,
        "max_tokens": 2000,
        "response_format": {"type": "json_object"},
    }

    try:
        resp = requests.post(
            url,
            headers=headers,
            json=payload,
            timeout=(15, 120),
            **_openai_request_kwargs(),
        )
        resp.raise_for_status()
    except requests.RequestException as exc:
        error_text = ""
        try:
            error_text = resp.json().get("error", {}).get("message", str(exc))
        except Exception:
            if "resp" in locals():
                error_text = resp.text[:400]
        raise RuntimeError(f"OpenAI ChatCompletion failed: {error_text}") from exc

    try:
        data = resp.json()
        content = data["choices"][0]["message"]["content"]
        return json.loads(content)
    except Exception as exc:
        try:
            return data["choices"][0]["message"]["content"]
        except Exception:
            raise RuntimeError(f"Cannot parse OpenAI response: {exc}") from exc


def _recognition_is_done(payload: dict[str, Any]) -> bool:
    if payload.get("done") is True:
        return True
    status = str(payload.get("status") or "").upper()
    if status in {"DONE", "SUCCESS"}:
        return True
    op = payload.get("operation")
    if isinstance(op, dict) and op.get("done") is True:
        return True
    return False


def _extract_transcript_from_yandex(payload: dict[str, Any]) -> list[list[Any]]:
    transcript = []
    chunks = _extract_chunks(payload)
    for chunk in chunks:
        text = _extract_chunk_text(chunk)
        if not text:
            continue
        start = _extract_start_seconds(chunk)
        transcript.append([text, start])

    if transcript:
        return transcript

    full_text = _extract_full_text(payload)
    if full_text:
        return [[full_text, 0.0]]

    return []


def _extract_start_seconds(chunk: Any) -> float:
    if not isinstance(chunk, dict):
        return 0.0

    words = chunk.get("words")
    if isinstance(words, list) and words:
        first = words[0] if isinstance(words[0], dict) else {}
        for key in ("startTimeMs", "start_time_ms", "startTime", "start_time"):
            val = first.get(key)
            if val is not None:
                try:
                    num = float(val)
                    return num / 1000.0 if "ms" in key.lower() else num
                except Exception:
                    pass

    for key in ("startTimeMs", "start_time_ms", "startTime", "start_time"):
        val = chunk.get(key)
        if val is not None:
            try:
                num = float(val)
                return num / 1000.0 if "ms" in key.lower() else num
            except Exception:
                pass

    return 0.0


def _extract_chunks(payload: dict[str, Any]) -> list[dict[str, Any]]:
    result = payload.get("result")
    candidates = []

    if isinstance(result, dict):
        candidates.extend(
            [
                result.get("chunks"),
                result.get("segments"),
                result.get("recognition", {}).get("chunks") if isinstance(result.get("recognition"), dict) else None,
            ]
        )

    if isinstance(payload.get("result"), list):
        candidates.append(payload.get("result"))

    candidates.extend([payload.get("chunks"), payload.get("segments")])

    for cand in candidates:
        if isinstance(cand, list):
            return [item for item in cand if isinstance(item, dict)]

    return []


def _extract_chunk_text(chunk: Any) -> str:
    if not isinstance(chunk, dict):
        return ""

    alts = chunk.get("alternatives")
    if isinstance(alts, list) and alts:
        dict_alts = [a for a in alts if isinstance(a, dict)]
        if dict_alts:
            best = max(dict_alts, key=lambda a: float(a.get("confidence") or 0))
            text = str(best.get("text") or "").strip()
            if text:
                return text

    text = str(chunk.get("text") or "").strip()
    if text:
        return text

    words = chunk.get("words")
    if isinstance(words, list):
        tokens = [str(w.get("text") or "").strip() for w in words if isinstance(w, dict) and w.get("text")]
        if tokens:
            return " ".join(tokens)

    return ""


def _extract_full_text(payload: dict[str, Any]) -> str:
    result = payload.get("result")
    if isinstance(result, dict):
        for k in ("text", "finalText", "transcript", "normalizedText"):
            val = result.get(k)
            if isinstance(val, str) and val.strip():
                return val.strip()
    return ""


def _payload_has_any_text(payload: dict[str, Any]) -> bool:
    return bool(_extract_chunks(payload)) or bool(_extract_full_text(payload))


def _detect_container_type(file_path: str) -> str:
    suffix = Path(file_path).suffix.lower()
    mapping = {
        ".mp3": "MP3",
        ".wav": "WAV",
        ".ogg": "OGG_OPUS",
        ".opus": "OGG_OPUS",
        ".m4a": "M4A",
        ".flac": "FLAC",
        ".webm": "WEBM_OPUS",
    }
    return mapping.get(suffix, "MP3")


def _is_yandex_not_ready_error(response: requests.Response) -> bool:
    if response.status_code != 404:
        return False
    payload = _safe_response_json(response, raise_on_invalid=False)
    error = payload.get("error", {})
    if isinstance(error, dict):
        return "not ready" in str(error.get("message") or "").lower()
    return "not ready" in response.text.lower()


def _safe_response_json(resp: requests.Response, raise_on_invalid: bool = True) -> dict[str, Any]:
    try:
        payload = resp.json()
        return payload if isinstance(payload, dict) else {}
    except ValueError:
        text = (resp.text or "").strip()
        if not text:
            if raise_on_invalid:
                raise RuntimeError("Empty response body")
            return {}
        try:
            parsed, _ = json.JSONDecoder().raw_decode(text)
            return parsed if isinstance(parsed, dict) else {}
        except ValueError:
            if raise_on_invalid:
                raise RuntimeError(f"Invalid JSON: {text[:400]}")
            return {}


def _normalize_transcript_segments(transcription: Any) -> list[tuple[str, float]]:
    normalized: list[tuple[str, float]] = []
    if not isinstance(transcription, list):
        return normalized

    for item in transcription:
        if isinstance(item, list) and len(item) >= 2:
            text = str(item[0] or "").strip()
            try:
                start = float(item[1])
            except Exception:
                start = 0.0
            if text:
                normalized.append((text, start))
            continue

        if isinstance(item, dict):
            text = str(item.get("text") or item.get("TEXT") or "").strip()
            start_raw = item.get("start") or item.get("start_seconds")
            try:
                start = float(start_raw)
            except Exception:
                start = 0.0
            if text:
                normalized.append((text, start))
            continue

        text = str(item or "").strip()
        if text:
            normalized.append((text, 0.0))

    return normalized


def _seconds_to_mmss(seconds: float) -> str:
    total = max(int(seconds), 0)
    minutes = total // 60
    secs = total % 60
    return f"{minutes:02d}:{secs:02d}"
