from __future__ import annotations

import base64
import json
import logging
import re
import time
import uuid
from dataclasses import dataclass
from typing import Any

import requests

from lsl.core.config import Settings
from lsl.modules.tts.audio_duration import estimate_audio_duration_ms
from lsl.modules.tts.types import TtsSpeaker, TtsSynthesizeRequest, TtsSynthesizeResult

logger = logging.getLogger(__name__)

_SCENE_EN: dict[str, str] = {
    "通用场景": "General",
    "视频配音": "Video narration",
    "角色扮演": "Role play",
    "教育场景": "Education",
    "客服场景": "Customer service",
    "有声阅读": "Audiobook",
    "多语种": "Multilingual",
}

_LANGUAGE_EN: dict[str, str] = {
    "中文": "Chinese",
    "日文": "Japanese",
    "印尼": "Indonesian",
    "墨西哥西班牙语": "Mexican Spanish",
    "美式英语": "American English",
}

_CAPABILITY_EN: dict[str, str] = {
    "情感变化": "emotion control",
    "指令遵循": "instruction following",
    "ASMR": "ASMR",
    "COT/QA功能": "CoT/QA",
}

_AVATAR_COLORS = [
    "#7C3AED",
    "#DB2777",
    "#059669",
    "#2563EB",
    "#D97706",
    "#0891B2",
    "#C026D3",
    "#16A34A",
]


@dataclass(frozen=True, slots=True)
class _VolcSpeakerRow:
    scene: str
    provider_name: str
    cn_name: str
    en_name: str
    voice_type: str
    language: str
    capability: str
    launched_for: str


_VOLC_TTS_2_SOURCE_ROWS: list[tuple[str, str, str, str, str, str]] = [
    ("通用场景", "Vivi 2.0", "zh_female_vv_uranus_bigtts", "中文、日文、印尼、墨西哥西班牙语", "情感变化、指令遵循、ASMR", ""),
    ("通用场景", "小何 2.0", "zh_female_xiaohe_uranus_bigtts", "中文", "情感变化、指令遵循、ASMR", ""),
    ("视频配音", "猴哥 2.0", "zh_male_sunwukong_uranus_bigtts", "中文", "情感变化、指令遵循、ASMR", ""),
    ("通用场景", "云舟 2.0", "zh_male_m191_uranus_bigtts", "中文", "情感变化、指令遵循、ASMR", ""),
    ("通用场景", "小天 2.0", "zh_male_taocheng_uranus_bigtts", "中文", "情感变化、指令遵循、ASMR", ""),
    ("通用场景", "刘飞 2.0", "zh_male_liufei_uranus_bigtts", "中文", "情感变化、指令遵循、ASMR", ""),
    ("通用场景", "魅力苏菲 2.0", "zh_male_sophie_uranus_bigtts", "中文", "情感变化、指令遵循、ASMR", ""),
    ("通用场景", "清新女声 2.0", "zh_female_qingxinnvsheng_uranus_bigtts", "中文", "情感变化、指令遵循、ASMR", ""),
    ("角色扮演", "知性灿灿 2.0", "zh_female_cancan_uranus_bigtts", "中文", "情感变化、指令遵循、ASMR", ""),
    ("角色扮演", "撒娇学妹 2.0", "zh_female_sajiaoxuemei_uranus_bigtts", "中文", "情感变化、指令遵循、ASMR", ""),
    ("通用场景", "甜美小源 2.0", "zh_female_tianmeixiaoyuan_uranus_bigtts", "中文", "情感变化、指令遵循、ASMR", ""),
    ("通用场景", "甜美桃子 2.0", "zh_female_tianmeitaozi_uranus_bigtts", "中文", "情感变化、指令遵循、ASMR", ""),
    ("通用场景", "爽快思思 2.0", "zh_female_shuangkuaisisi_uranus_bigtts", "中文", "情感变化、指令遵循、ASMR", ""),
    ("视频配音", "佩奇猪 2.0", "zh_female_peiqi_uranus_bigtts", "中文", "情感变化、指令遵循、ASMR", ""),
    ("通用场景", "邻家女孩 2.0", "zh_female_linjianvhai_uranus_bigtts", "中文", "情感变化、指令遵循、ASMR", ""),
    ("通用场景", "少年梓辛/Brayan 2.0", "zh_male_shaonianzixin_uranus_bigtts", "中文", "情感变化、指令遵循、ASMR", ""),
    ("教育场景", "Tina老师 2.0", "zh_female_yingyujiaoxue_uranus_bigtts", "中文", "情感变化、指令遵循、ASMR", ""),
    ("客服场景", "暖阳女声 2.0", "zh_female_kefunvsheng_uranus_bigtts", "中文", "情感变化、指令遵循、ASMR", ""),
    ("有声阅读", "儿童绘本 2.0", "zh_female_xiaoxue_uranus_bigtts", "中文", "情感变化、指令遵循、ASMR", ""),
    ("视频配音", "大壹 2.0", "zh_male_dayi_uranus_bigtts", "中文", "情感变化、指令遵循、ASMR", ""),
    ("视频配音", "黑猫侦探社咪仔 2.0", "zh_female_mizai_uranus_bigtts", "中文", "情感变化、指令遵循、ASMR", ""),
    ("视频配音", "鸡汤女 2.0", "zh_female_jitangnv_uranus_bigtts", "中文", "情感变化、指令遵循、ASMR", ""),
    ("通用场景", "魅力女友 2.0", "zh_female_meilinvyou_uranus_bigtts", "中文", "情感变化、指令遵循、ASMR", ""),
    ("视频配音", "流畅女声 2.0", "zh_female_liuchangnv_uranus_bigtts", "中文", "情感变化、指令遵循、ASMR", ""),
    ("视频配音", "儒雅逸辰 2.0", "zh_male_ruyayichen_uranus_bigtts", "中文", "情感变化、指令遵循、ASMR", ""),
    ("多语种", "Tim", "en_male_tim_uranus_bigtts", "美式英语", "情感变化、指令遵循、ASMR", ""),
    ("多语种", "Dacey", "en_female_dacey_uranus_bigtts", "美式英语", "情感变化、指令遵循、ASMR", ""),
    ("多语种", "Stokie", "en_female_stokie_uranus_bigtts", "美式英语", "情感变化、指令遵循、ASMR", ""),
    ("有声阅读", "儿童绘本", "zh_female_xueayi_saturn_bigtts", "中文", "指令遵循", "剪映"),
    ("视频配音", "大壹", "zh_male_dayi_saturn_bigtts", "中文", "指令遵循", "剪映"),
    ("视频配音", "黑猫侦探社咪仔", "zh_female_mizai_saturn_bigtts", "中文", "指令遵循", "剪映"),
    ("视频配音", "鸡汤女", "zh_female_jitangnv_saturn_bigtts", "中文", "指令遵循", "剪映"),
    ("视频配音", "魅力女友", "zh_female_meilinvyou_saturn_bigtts", "中文", "指令遵循", "剪映"),
    ("视频配音", "流畅女声", "zh_female_santongyongns_saturn_bigtts", "中文", "指令遵循", "剪映"),
    ("视频配音", "儒雅逸辰", "zh_male_ruyayichen_saturn_bigtts", "中文", "指令遵循", "剪映"),
    ("角色扮演", "可爱女生", "saturn_zh_female_keainvsheng_tob", "中文", "指令遵循、COT/QA功能", ""),
    ("角色扮演", "调皮公主", "saturn_zh_female_tiaopigongzhu_tob", "中文", "指令遵循、COT/QA功能", ""),
    ("角色扮演", "爽朗少年", "saturn_zh_male_shuanglangshaonian_tob", "中文", "指令遵循、COT/QA功能", ""),
    ("角色扮演", "天才同桌", "saturn_zh_male_tiancaitongzhuo_tob", "中文", "指令遵循、COT/QA功能", ""),
    ("角色扮演", "知性灿灿", "saturn_zh_female_cancan_tob", "中文", "指令遵循、COT/QA功能", ""),
    ("客服场景", "轻盈朵朵 2.0", "saturn_zh_female_qingyingduoduo_cs_tob", "中文", "指令遵循", ""),
    ("客服场景", "温婉珊珊 2.0", "saturn_zh_female_wenwanshanshan_cs_tob", "中文", "指令遵循", ""),
    ("客服场景", "热情艾娜 2.0", "saturn_zh_female_reqingaina_cs_tob", "中文", "指令遵循", ""),
]


def _strip_speaker_version(name: str) -> str:
    normalized = re.sub(r"\s+", " ", name.strip())
    return re.sub(r"\s+\d+(?:\.\d+)*$", "", normalized).strip() or normalized


def _to_english_list(value: str, mapping: dict[str, str]) -> str:
    parts = [part.strip() for part in value.split("、") if part.strip()]
    return ", ".join(mapping.get(part, part) for part in parts)


def _build_volc_speaker_row(
    scene: str,
    name: str,
    voice_type: str,
    language: str,
    capability: str,
    launched_for: str,
) -> _VolcSpeakerRow:
    display_name = _strip_speaker_version(name)
    return _VolcSpeakerRow(
        scene=scene,
        provider_name=name,
        cn_name=display_name,
        en_name=display_name,
        voice_type=voice_type,
        language=language,
        capability=capability,
        launched_for=launched_for,
    )


_VOLC_TTS_2_SPEAKER_ROWS = [
    _build_volc_speaker_row(*row)
    for row in _VOLC_TTS_2_SOURCE_ROWS
]


def _infer_gender(voice_type: str) -> str | None:
    if "_female_" in voice_type:
        return "female"
    if "_male_" in voice_type:
        return "male"
    return None


def _build_description(scene: str, capability: str, launched_for: str) -> str:
    parts = [scene, capability]
    if launched_for:
        parts.append(f"上线业务方: {launched_for}")
    return " | ".join(part for part in parts if part)


def _build_english_description(scene: str, capability: str, launched_for: str) -> str:
    parts = [_SCENE_EN.get(scene, scene), _to_english_list(capability, _CAPABILITY_EN)]
    if launched_for:
        parts.append(f"launched for: {launched_for}")
    return " | ".join(part for part in parts if part)


def _build_avatar(row: _VolcSpeakerRow) -> dict[str, Any]:
    color_index = sum(ord(ch) for ch in row.voice_type) % len(_AVATAR_COLORS)
    return {
        "type": "preset",
        "key": f"{_infer_gender(row.voice_type) or 'neutral'}_{row.scene}",
        "color": _AVATAR_COLORS[color_index],
        "initials": (row.cn_name or row.en_name or row.provider_name)[:2],
    }


def _build_traits(row: _VolcSpeakerRow) -> dict[str, Any]:
    return {
        "gender": _infer_gender(row.voice_type),
        "scene": row.scene,
        "capabilities": [part.strip() for part in row.capability.split("、") if part.strip()],
        "launched_for": row.launched_for or None,
    }


def _build_i18n(row: _VolcSpeakerRow) -> dict[str, dict[str, str]]:
    return {
        "zh-CN": {
            "name": row.cn_name,
            "language": row.language,
            "style": row.scene,
            "description": _build_description(row.scene, row.capability, row.launched_for),
        },
        "en": {
            "name": row.en_name,
            "language": _to_english_list(row.language, _LANGUAGE_EN),
            "style": _SCENE_EN.get(row.scene, row.scene),
            "description": _build_english_description(row.scene, row.capability, row.launched_for),
        },
    }


def _mask_secret(value: str) -> str:
    if len(value) <= 8:
        return "*" * len(value)
    return f"{value[:4]}***{value[-4:]}"


class VolcTtsProvider:
    provider_name = "volc"

    def __init__(self, settings: Settings) -> None:
        self._app_id = settings.TTS_VOLC_APP_ID
        self._access_key = settings.TTS_VOLC_ACCESS_KEY
        self._resource_id = settings.TTS_VOLC_RESOURCE_ID
        self._url = settings.TTS_VOLC_URL
        self._timeout = float(settings.TTS_VOLC_HTTP_TIMEOUT)
        self._speakers = [
            TtsSpeaker(
                speaker_id=row.voice_type,
                name=row.provider_name,
                provider_name=row.provider_name,
                display_name=row.cn_name,
                language=row.language,
                gender=_infer_gender(row.voice_type),
                style=row.scene,
                description=_build_description(row.scene, row.capability, row.launched_for),
                i18n=_build_i18n(row),
                avatar=_build_avatar(row),
                traits=_build_traits(row),
            )
            for row in _VOLC_TTS_2_SPEAKER_ROWS
        ]

    def get_speakers(self) -> list[TtsSpeaker]:
        return list(self._speakers)

    def synthesize(self, req: TtsSynthesizeRequest) -> TtsSynthesizeResult:
        if not self._app_id:
            raise RuntimeError("TTS_VOLC_APP_ID is not configured")
        if not self._access_key:
            raise RuntimeError("TTS_VOLC_ACCESS_KEY is not configured")
        if not self._resource_id:
            raise RuntimeError("TTS_VOLC_RESOURCE_ID is not configured")
        if not self._url:
            raise RuntimeError("TTS_VOLC_URL is not configured")

        request_id = uuid.uuid4().hex
        headers = {
            "X-Api-App-Id": self._app_id,
            "X-Api-Access-Key": self._access_key,
            "X-Api-Resource-Id": self._resource_id,
            "X-Api-Request-Id": request_id,
            "Content-Type": "application/json",
            "Connection": "keep-alive",
        }
        additions = self._build_additions(req)
        audio_params = self._build_audio_params(req)
        payload: dict[str, Any] = {
            "user": {"uid": req.session_id},
            "req_params": {
                "text": req.plain_text,
                "speaker": req.provider_speaker_id,
                "audio_params": audio_params,
                "additions": json.dumps(additions, ensure_ascii=False),
            },
        }
        debug_headers = {
            "X-Api-App-Id": self._app_id,
            "X-Api-Access-Key": _mask_secret(self._access_key),
            "X-Api-Resource-Id": self._resource_id,
            "X-Api-Request-Id": request_id,
            "Content-Type": "application/json",
            "Connection": "keep-alive",
        }
        logger.info(
            "Volc TTS request url=%s headers=%s payload=%s",
            self._url,
            json.dumps(debug_headers, ensure_ascii=False),
            json.dumps(payload, ensure_ascii=False),
        )
        request_started_at = time.monotonic()
        logger.info(
            "Volc TTS request started session_id=%s request_id=%s speaker=%s format=%s timeout_s=%s text_length=%s cue_count=%s",
            req.session_id,
            request_id,
            req.provider_speaker_id,
            req.format,
            self._timeout,
            len(req.plain_text),
            len(req.cue_texts),
        )

        response = requests.post(
            self._url,
            headers=headers,
            json=payload,
            stream=True,
            timeout=self._timeout,
        )
        try:
            log_id = response.headers.get("X-Tt-Logid")
            logger.info(
                "Volc TTS response headers received session_id=%s request_id=%s status=%s x_tt_logid=%s elapsed_ms=%s",
                req.session_id,
                request_id,
                response.status_code,
                log_id,
                int((time.monotonic() - request_started_at) * 1000),
            )
            if response.status_code != 200:
                response_text = response.text[:400]
                logger.error(
                    "Volc TTS non-200 request_id=%s status=%s x_tt_logid=%s body=%s",
                    request_id,
                    response.status_code,
                    log_id,
                    response_text,
                )
                if response.status_code == 403 and "requested resource not granted" in response_text:
                    raise RuntimeError(
                        "Volc TTS resource is not granted. "
                        "Check TTS_VOLC_APP_ID, TTS_VOLC_ACCESS_KEY, and TTS_VOLC_RESOURCE_ID in .env. "
                        "Use credentials that are authorized for TTS, not ASR-only credentials. "
                        f"x_tt_logid={log_id}"
                    )
                raise RuntimeError(
                    f"Volc TTS request failed: status={response.status_code} x_tt_logid={log_id} body={response_text}"
                )

            audio_data = bytearray()
            max_subtitle_end_time_ms: int | None = None
            stream_started_at = time.monotonic()
            try:
                events = self._iter_response_events(response)
            except Exception as exc:
                logger.exception(
                    "Volc TTS stream read failed session_id=%s speaker=%s elapsed_ms=%s exc_type=%s",
                    req.session_id,
                    req.provider_speaker_id,
                    int((time.monotonic() - stream_started_at) * 1000),
                    type(exc).__name__,
                )
                raise
            logger.info(
                "Volc TTS stream parsed session_id=%s speaker=%s event_count=%s elapsed_ms=%s",
                req.session_id,
                req.provider_speaker_id,
                len(events),
                int((time.monotonic() - stream_started_at) * 1000),
            )
            for event_name, data in events:
                code = int(data.get("code", 0))
                if code == 0 and data.get("data"):
                    audio_data.extend(base64.b64decode(data["data"]))
                    continue
                if code == 0 and data.get("sentence"):
                    sentence_duration_ms = self._extract_sentence_end_time_ms(data.get("sentence"))
                    if sentence_duration_ms is not None:
                        max_subtitle_end_time_ms = max(
                            max_subtitle_end_time_ms or 0,
                            sentence_duration_ms,
                        )
                    logger.info(
                        "Volc TTS subtitle event=%s sentence=%s",
                        event_name or "json",
                        json.dumps(data.get("sentence"), ensure_ascii=False),
                    )
                    continue
                if code == 20000000:
                    break
                if code > 0:
                    logger.error(
                        "Volc TTS response error session_id=%s request_id=%s x_tt_logid=%s resource_id=%s speaker=%s format=%s event=%s body=%s",
                        req.session_id,
                        request_id,
                        log_id,
                        self._resource_id,
                        req.provider_speaker_id,
                        req.format,
                        event_name or "json",
                        json.dumps(data, ensure_ascii=False),
                    )
                    raise RuntimeError(f"Volc TTS response error: {data}")

            if not audio_data:
                event_summaries = [self._summarize_event(event_name, data) for event_name, data in events]
                logger.error(
                    "Volc TTS returned empty audio data session_id=%s request_id=%s x_tt_logid=%s resource_id=%s speaker=%s format=%s text_length=%s text_preview=%s event_count=%s events=%s",
                    req.session_id,
                    request_id,
                    log_id,
                    self._resource_id,
                    req.provider_speaker_id,
                    req.format,
                    len(req.plain_text),
                    self._preview_text(req.plain_text),
                    len(events),
                    json.dumps(event_summaries, ensure_ascii=False),
                )
                raise RuntimeError(
                    "Volc TTS returned empty audio data "
                    f"x_tt_logid={log_id} resource_id={self._resource_id} events={event_summaries}"
                )

            actual_duration_ms = estimate_audio_duration_ms(
                audio_bytes=bytes(audio_data),
                format_name=req.format,
            )
            duration_ms = actual_duration_ms or max_subtitle_end_time_ms
            if actual_duration_ms and max_subtitle_end_time_ms and abs(actual_duration_ms - max_subtitle_end_time_ms) > 250:
                logger.info(
                    "Volc TTS duration adjusted session_id=%s speaker=%s subtitle_duration_ms=%s audio_duration_ms=%s",
                    req.session_id,
                    req.provider_speaker_id,
                    max_subtitle_end_time_ms,
                    actual_duration_ms,
                )

            return TtsSynthesizeResult(
                audio_bytes=bytes(audio_data),
                content_type=self._content_type_for_format(req.format),
                duration_ms=duration_ms,
                provider_speaker_id=req.provider_speaker_id,
            )
        finally:
            logger.info(
                "Volc TTS request finished session_id=%s speaker=%s total_elapsed_ms=%s",
                req.session_id,
                req.provider_speaker_id,
                int((time.monotonic() - request_started_at) * 1000),
            )
            response.close()

    @staticmethod
    def _build_additions(req: TtsSynthesizeRequest) -> dict[str, Any]:
        explicit_language = "en" if any("a" <= ch.lower() <= "z" for ch in req.plain_text) else "zh"
        additions: dict[str, Any] = {
            "explicit_language": explicit_language,
            "disable_markdown_filter": True,
        }
        if req.cue_texts:
            additions["context_texts"] = req.cue_texts
        return additions

    @staticmethod
    def _build_audio_params(req: TtsSynthesizeRequest) -> dict[str, Any]:
        return {
            "format": req.format,
            "sample_rate": 24000,
            "emotion_scale": req.emotion_scale,
            "speech_rate": req.speech_rate,
            "loudness_rate": req.loudness_rate,
            "enable_subtitle": True,
        }

    @staticmethod
    def _content_type_for_format(format_name: str) -> str:
        if format_name.lower() == "wav":
            return "audio/wav"
        return "audio/mpeg"

    @staticmethod
    def _summarize_event(event_name: str | None, data: dict[str, Any]) -> dict[str, Any]:
        summary: dict[str, Any] = {
            "event": event_name or "json",
            "code": data.get("code"),
            "keys": sorted(data.keys()),
        }
        if "message" in data:
            summary["message"] = data.get("message")
        if "data" in data:
            value = data.get("data")
            summary["data_type"] = type(value).__name__
            summary["data_length"] = len(value) if isinstance(value, (str, bytes, list, dict)) else None
        if "sentence" in data:
            summary["has_sentence"] = data.get("sentence") is not None
            summary["sentence_type"] = type(data.get("sentence")).__name__
        return summary

    @staticmethod
    def _preview_text(value: str, limit: int = 120) -> str:
        normalized = " ".join(value.split())
        if len(normalized) <= limit:
            return normalized
        return f"{normalized[:limit]}..."

    @staticmethod
    def _iter_response_events(response: requests.Response) -> list[tuple[str | None, dict[str, Any]]]:
        current_event: str | None = None
        events: list[tuple[str | None, dict[str, Any]]] = []
        for chunk in response.iter_lines(decode_unicode=True):
            if not chunk:
                continue
            line = chunk.strip()
            if not line:
                continue
            if line.startswith("event:"):
                current_event = line.partition(":")[2].strip() or None
                continue
            payload = line.partition(":")[2].strip() if line.startswith("data:") else line
            try:
                message = json.loads(payload)
            except json.JSONDecodeError:
                logger.warning("Volc TTS returned non-JSON chunk: %s", line[:200])
                continue
            events.append((current_event, message))
        return events

    @staticmethod
    def _extract_sentence_end_time_ms(sentence_payload: Any) -> int | None:
        if not isinstance(sentence_payload, dict):
            return None
        words = sentence_payload.get("words")
        if not isinstance(words, list) or not words:
            return None
        max_end_time = 0.0
        found = False
        for item in words:
            if not isinstance(item, dict):
                continue
            try:
                end_time = float(item.get("endTime", 0))
            except (TypeError, ValueError):
                continue
            max_end_time = max(max_end_time, end_time)
            found = True
        if not found:
            return None
        return int(max_end_time * 1000)
