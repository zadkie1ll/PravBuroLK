import base64
import json
import os
import time
from pathlib import Path
from typing import Any

import requests
from dotenv import find_dotenv, load_dotenv

load_dotenv(find_dotenv())


def transcribe(file_path: str):
    """
    Единая точка транскрипции.
    Переключается между провайдерами через env:
    - TRANSCRIPTION_PROVIDER=whisper (по умолчанию)
    - TRANSCRIPTION_PROVIDER=yandex_async
    """
    provider = os.getenv("TRANSCRIPTION_PROVIDER", "openai_whisper").strip().lower()

    if provider == "yandex_async":
        return _transcribe_yandex_async(file_path)
    if provider == "openai_whisper":
        return _transcribe_openai_whisper(file_path)



# def _transcribe_whisper(file_path: str):
#     # Ленивая загрузка heavy-зависимостей:
#     # так Django/Celery стартуют даже если ML-стек еще не установлен.
#     from faster_whisper import WhisperModel
#     from tqdm import tqdm

#     hf_token = os.getenv("HF_TOKEN", "").strip()
#     model_kwargs = {"device": "cpu"}
#     # Не передаем пустой токен, иначе huggingface_hub отправляет "Bearer " и падает.
#     if hf_token:
#         model_kwargs["use_auth_token"] = hf_token

#     model = WhisperModel("base", **model_kwargs)
#     segments, _ = model.transcribe(file_path, vad_filter=True)

#     transcript = []
#     for segment in tqdm(segments, desc="Транскрипция Whisper..."):
#         transcript.append([segment.text, segment.start])
#     return transcript


def _transcribe_yandex_async(file_path: str):
    """
    Yandex SpeechKit: отложенное (асинхронное) распознавание.
    1) POST /stt/v3/recognizeFileAsync
    2) GET  /stt/v3/getRecognition?operation_id=...
    """
    api_key = os.getenv("YANDEX_API_KEY", "")
    folder_id = os.getenv("YANDEX_FOLDER_ID", "")
    if not api_key or not folder_id:
        raise RuntimeError("YANDEX_API_KEY and YANDEX_FOLDER_ID are required for yandex_async transcription")

    with Path(file_path).open("rb") as fh:
        audio_b64 = base64.b64encode(fh.read()).decode("utf-8")

    headers = {
        "Authorization": f"Api-Key {api_key}",
        "x-folder-id": folder_id,
        "Content-Type": "application/json",
    }

    timeout = float(os.getenv("YANDEX_STT_HTTP_TIMEOUT_SECONDS", "60"))
    poll_timeout = float(os.getenv("YANDEX_STT_POLL_TIMEOUT_SECONDS", "1200"))
    poll_interval = float(os.getenv("YANDEX_STT_POLL_INTERVAL_SECONDS", "2"))
    return_partial_on_timeout = _env_bool("YANDEX_STT_RETURN_PARTIAL_ON_TIMEOUT", default=True)
    session = _build_yandex_session()

    body = {
        "content": audio_b64,
        "recognitionModel": {
            "model": os.getenv("YANDEX_STT_MODEL", "deferred-general"),
            "audioFormat": {
                "containerAudio": {
                    "containerAudioType": _detect_container_type(file_path),
                }
            },
            "textNormalization": {
                "textNormalization": os.getenv("YANDEX_STT_TEXT_NORMALIZATION", "TEXT_NORMALIZATION_ENABLED"),
                "profanityFilter": _env_bool("YANDEX_STT_PROFANITY_FILTER", default=False),
                "literatureText": _env_bool("YANDEX_STT_LITERATURE_TEXT", default=False),
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
        raise RuntimeError(
            "Yandex STT network error on recognizeFileAsync. "
            "Check network/VPN/proxy and try YANDEX_STT_TRUST_ENV=true if you need proxy env."
        ) from exc
    if not start_response.ok:
        raise RuntimeError(f"Yandex recognizeFileAsync failed: {start_response.text}")

    start_payload = _safe_response_json(start_response)
    operation_id = str((start_payload or {}).get("id") or "")
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
            raise RuntimeError(
                "Yandex STT network error on getRecognition. "
                "Check network/VPN/proxy and try YANDEX_STT_TRUST_ENV=true if you need proxy env."
            ) from exc
        if not poll_response.ok:
            # Yandex async может вернуть 404 "operation data is not ready ...",
            # это штатно и означает "подождите еще".
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

    raise RuntimeError(
        f"Yandex recognition timeout after {poll_timeout} seconds. "
        f"Try increasing YANDEX_STT_POLL_TIMEOUT_SECONDS."
    )


def _transcribe_openai_whisper(file_path: str):
    """
    OpenAI Speech-to-Text провайдер.
    Модель задается через OPENAI_TRANSCRIBE_MODEL (по умолчанию whisper-1).
    """
    from openai import OpenAI

    api_key = os.getenv("OPENAI_API_KEY", "").strip()
    if not api_key:
        raise RuntimeError("OPENAI_API_KEY is empty. Required for openai_whisper transcription.")

    timeout_seconds = float(os.getenv("OPENAI_REQUEST_TIMEOUT_SECONDS", "180"))
    model_name = os.getenv("OPENAI_TRANSCRIBE_MODEL", "whisper-1").strip() or "whisper-1"
    language = os.getenv("OPENAI_TRANSCRIBE_LANGUAGE", "").strip() or None
    response_format = os.getenv("OPENAI_TRANSCRIBE_RESPONSE_FORMAT", "verbose_json").strip() or "verbose_json"

    client = OpenAI(api_key=api_key, timeout=timeout_seconds)

    with Path(file_path).open("rb") as audio_file:
        request_kwargs: dict[str, Any] = {
            "model": model_name,
            "file": audio_file,
            "response_format": response_format,
        }
        if language:
            request_kwargs["language"] = language

        response = client.audio.transcriptions.create(**request_kwargs)

    # В зависимости от response_format может прийти объект или строка.
    if isinstance(response, str):
        return [[response.strip(), 0.0]] if response.strip() else []

    segments = getattr(response, "segments", None)
    if segments and isinstance(segments, list):
        transcript = []
        for segment in segments:
            text = str(getattr(segment, "text", "") or "").strip()
            if not text:
                continue
            start = float(getattr(segment, "start", 0.0) or 0.0)
            transcript.append([text, start])
        if transcript:
            return transcript

    text = str(getattr(response, "text", "") or "").strip()
    if text:
        return [[text, 0.0]]

    # Последний fallback на dict-представление.
    try:
        data = response.model_dump() if hasattr(response, "model_dump") else dict(response)
    except Exception:
        data = {}
    text = str((data or {}).get("text") or "").strip()
    if text:
        return [[text, 0.0]]
    return []


def _recognition_is_done(payload: dict[str, Any]) -> bool:
    # Важно: считаем операцию завершенной только по явному DONE/SUCCESS.
    # Иначе можно вычитать промежуточный (частичный) результат.
    if payload.get("done") is True:
        return True
    status = str(payload.get("status") or "").upper()
    if status in {"DONE", "SUCCESS"}:
        return True
    op = payload.get("operation")
    if isinstance(op, dict) and op.get("done") is True:
        return True
    return False


def _extract_transcript_from_yandex(payload: dict[str, Any]):
    # Форматы ответов могут отличаться, поэтому вытаскиваем текст максимально толерантно.
    transcript = []
    chunks = _extract_chunks(payload)

    for chunk in chunks:
        text = _extract_chunk_text(chunk)

        if not text:
            continue

        start_seconds = _extract_start_seconds(chunk)
        transcript.append([text, start_seconds])

    if transcript:
        return transcript

    # Fallback: пытаемся взять единый полный текст, но не распиливаем на отдельные слова.
    full_text = _extract_full_text(payload)
    if full_text:
        return [[full_text, 0.0]]

    return []


def _extract_start_seconds(chunk: Any) -> float:
    if not isinstance(chunk, dict):
        return 0.0

    words = chunk.get("words")
    if isinstance(words, list) and words:
        first_word = words[0] if isinstance(words[0], dict) else {}
        for key in ("startTimeMs", "start_time_ms", "startTime", "start_time"):
            value = first_word.get(key)
            if value is None:
                continue
            try:
                numeric = float(value)
                if key.lower().endswith("ms"):
                    return numeric / 1000.0
                return numeric
            except (TypeError, ValueError):
                continue

    for key in ("startTimeMs", "start_time_ms", "startTime", "start_time"):
        value = chunk.get(key)
        if value is None:
            continue
        try:
            numeric = float(value)
            # Если миллисекунды - приводим к секундам.
            if key.lower().endswith("ms"):
                return numeric / 1000.0
            return numeric
        except (TypeError, ValueError):
            continue

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

    for candidate in candidates:
        if isinstance(candidate, list):
            return [item for item in candidate if isinstance(item, dict)]
    return []


def _extract_chunk_text(chunk: Any) -> str:
    if not isinstance(chunk, dict):
        return ""

    alternatives = chunk.get("alternatives")
    if isinstance(alternatives, list) and alternatives:
        # Берем альтернативу с максимальной confidence, если она есть.
        dict_alts = [alt for alt in alternatives if isinstance(alt, dict)]
        if dict_alts:
            best = max(dict_alts, key=lambda alt: float(alt.get("confidence") or 0))
            text = str(best.get("text") or "").strip()
            if text:
                return text

    text = str(chunk.get("text") or "").strip()
    if text:
        return text

    words = chunk.get("words")
    if isinstance(words, list):
        word_tokens = []
        for word in words:
            if isinstance(word, dict):
                token = str(word.get("text") or "").strip()
                if token:
                    word_tokens.append(token)
        if word_tokens:
            return " ".join(word_tokens)

    return ""


def _extract_full_text(payload: dict[str, Any]) -> str:
    result = payload.get("result")
    if isinstance(result, dict):
        for key in ("text", "finalText", "transcript", "normalizedText"):
            value = result.get(key)
            if isinstance(value, str) and value.strip():
                return value.strip()
    return ""


def _payload_has_any_text(payload: dict[str, Any]) -> bool:
    if _extract_chunks(payload):
        return True
    return bool(_extract_full_text(payload))


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


def _env_bool(name: str, default: bool = False) -> bool:
    value = os.getenv(name)
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


def _build_yandex_session() -> requests.Session:
    session = requests.Session()
    # По умолчанию игнорируем системные proxy env, чтобы избежать неожиданных
    # TLS/Protocol ошибок в локальной среде.
    # Если прокси нужен, установи YANDEX_STT_TRUST_ENV=true.
    session.trust_env = _env_bool("YANDEX_STT_TRUST_ENV", default=False)
    return session


def _is_yandex_not_ready_error(response: requests.Response) -> bool:
    if response.status_code != 404:
        return False

    payload = _safe_response_json(response, raise_on_invalid=False)

    error = payload.get("error")
    if isinstance(error, dict):
        message = str(error.get("message") or "").lower()
        return "not ready" in message

    return "not ready" in (response.text or "").lower()


def _safe_response_json(response: requests.Response, raise_on_invalid: bool = True) -> dict[str, Any]:
    """
    Устойчивый парсинг JSON:
    - сначала стандартный response.json()
    - при `Extra data` пытаемся распарсить первый JSON-объект через raw_decode
    """
    try:
        payload = response.json() or {}
        return payload if isinstance(payload, dict) else {}
    except ValueError:
        text = (response.text or "").strip()
        if not text:
            if raise_on_invalid:
                raise RuntimeError("Empty response body, expected JSON")
            return {}

        decoder = json.JSONDecoder()
        try:
            parsed, _ = decoder.raw_decode(text)
            if isinstance(parsed, dict):
                return parsed
            return {}
        except ValueError:
            if raise_on_invalid:
                snippet = text[:500]
                raise RuntimeError(f"Invalid JSON response: {snippet}")
            return {}


def _normalize_transcript_segments(transcription: Any) -> list[tuple[str, float]]:
    """
    Приводит transcript к списку (text, start_seconds) из разных форматов.
    """
    normalized: list[tuple[str, float]] = []
    if not isinstance(transcription, list):
        return normalized

    for item in transcription:
        if isinstance(item, list) and len(item) >= 2:
            text = str(item[0] or "").strip()
            try:
                start = float(item[1] or 0.0)
            except (TypeError, ValueError):
                start = 0.0
            if text:
                normalized.append((text, start))
            continue

        if isinstance(item, dict):
            text = str(item.get("text") or item.get("TEXT") or "").strip()
            start_raw = item.get("start")
            if start_raw is None:
                start_raw = item.get("start_seconds")
            try:
                start = float(start_raw or 0.0)
            except (TypeError, ValueError):
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


def _clean_json_text(raw_text: str) -> str:
    text = str(raw_text or "").strip()
    if text.startswith("```"):
        lines = text.splitlines()
        if lines:
            lines = lines[1:]
        if lines and lines[-1].strip() == "```":
            lines = lines[:-1]
        text = "\n".join(lines).strip()
    return text


def _safe_json_loads(raw_text: str) -> dict[str, Any]:
    text = _clean_json_text(raw_text)
    if not text:
        return {}

    try:
        payload = json.loads(text)
        return payload if isinstance(payload, dict) else {}
    except json.JSONDecodeError:
        pass

    start = text.find("{")
    end = text.rfind("}")
    if start >= 0 and end > start:
        try:
            payload = json.loads(text[start : end + 1])
            return payload if isinstance(payload, dict) else {}
        except json.JSONDecodeError:
            return {}
    return {}


def diarize_transcript(transcription: Any) -> dict[str, str]:
    """
    Размечает роли говорящих и возвращает словарь:
    {
      "00:03": "operator",
      "00:11": "client"
    }
    """
    from openai import OpenAI
    import httpx
    api_key = os.getenv("OPENAI_API_KEY", "").strip()
    if not api_key:
        raise RuntimeError("OPENAI_API_KEY is empty. Set it in environment or disable diarization step.")

    segments = _normalize_transcript_segments(transcription)
    if not segments:
        return {}

    timeout_seconds = float(os.getenv("OPENAI_REQUEST_TIMEOUT_SECONDS", "180"))
    model_name = os.getenv("OPENAI_DIARIZATION_MODEL", "gpt-4.1-mini").strip() or "gpt-4.1-mini"
    client = OpenAI(api_key=api_key, timeout=timeout_seconds, http_client=httpx.Client(proxy="socks5h://127.0.0.1:9050", headers={
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/134.0.0.0 Safari/537.36",
        "Accept": "application/json",
        "Accept-Language": "en-US,en;q=0.9",
    },
    http1=True,           # иногда помогает отключить http2
    http2=False,))

    dialog_for_model = "\n".join(
        f"{_seconds_to_mmss(start)} | {text}"
        for text, start in segments
    )

    response = client.responses.create(
        model=model_name,
        input=[
            {
                "role": "developer",
                "content": [
                    {
                        "type": "input_text",
                        "text": """Ты делаешь диаризацию разговора менеджера и клиента.
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
""",
                    }
                ],
            },
            {
                "role": "user",
                "content": [{"type": "input_text", "text": dialog_for_model}],
            },
        ],
    )

    payload = _safe_json_loads(response.output_text)
    speaker_map = payload.get("speaker_map")
    if not isinstance(speaker_map, dict):
        return {}

    cleaned: dict[str, str] = {}
    allowed_roles = {"operator", "client", "unknown"}
    for k, v in speaker_map.items():
        key = str(k or "").strip()
        value = str(v or "").strip().lower()
        if not key:
            continue
        if value not in allowed_roles:
            value = "unknown"
        cleaned[key] = value
    return cleaned


# === Анализ ===
def ai_analysis(transcribtion, speaker_map: dict[str, str] | None = None):
    from openai import OpenAI
    import httpx
    api_key = os.getenv("OPENAI_API_KEY", "").strip()
    if not api_key:
        raise RuntimeError("OPENAI_API_KEY is empty. Set it in environment or disable analysis step.")

    timeout_seconds = float(os.getenv("OPENAI_REQUEST_TIMEOUT_SECONDS", "180"))
    client = OpenAI(api_key=api_key, timeout=timeout_seconds, http_client=httpx.Client(proxy="socks5h://127.0.0.1:9050"))
    model_name = os.getenv("OPENAI_ANALYSIS_MODEL", "gpt-4.1-mini").strip() or "gpt-4.1-mini"

    normalized = _normalize_transcript_segments(transcribtion)
    normalized_speaker_map = speaker_map or {}
    dialog_lines = []
    for text, start in normalized:
        timestamp = _seconds_to_mmss(start)
        role = normalized_speaker_map.get(timestamp, "unknown")
        dialog_lines.append(f"[{timestamp}] [{role}] {text}")

    dialog_text = "\n".join(dialog_lines) if dialog_lines else str(transcribtion)

    response = client.responses.create(
        model=model_name,
        input=[
            {
                "role": "developer",
                "content": [
                    {
                        "type": "input_text",
                        "text": """Ты контролер качества звонков. Тебе даётся разговор в формате:
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
""",
                    }
                ],
            },
            {
                "role": "user",
                "content": [
                    {
                        "type": "input_text",
                        "text": dialog_text,
                    }
                ],
            },
        ],
    )

    return response.output_text
