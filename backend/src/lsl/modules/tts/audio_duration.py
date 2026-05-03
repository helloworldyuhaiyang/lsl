from __future__ import annotations

from math import floor


_BITRATES_KBPS: dict[tuple[str, str], list[int | None]] = {
    ("mpeg1", "layer1"): [None, 32, 64, 96, 128, 160, 192, 224, 256, 288, 320, 352, 384, 416, 448, None],
    ("mpeg1", "layer2"): [None, 32, 48, 56, 64, 80, 96, 112, 128, 160, 192, 224, 256, 320, 384, None],
    ("mpeg1", "layer3"): [None, 32, 40, 48, 56, 64, 80, 96, 112, 128, 160, 192, 224, 256, 320, None],
    ("mpeg2", "layer1"): [None, 32, 48, 56, 64, 80, 96, 112, 128, 144, 160, 176, 192, 224, 256, None],
    ("mpeg2", "layer2"): [None, 8, 16, 24, 32, 40, 48, 56, 64, 80, 96, 112, 128, 144, 160, None],
    ("mpeg2", "layer3"): [None, 8, 16, 24, 32, 40, 48, 56, 64, 80, 96, 112, 128, 144, 160, None],
}

_SAMPLE_RATES: dict[str, list[int | None]] = {
    "mpeg1": [44100, 48000, 32000, None],
    "mpeg2": [22050, 24000, 16000, None],
    "mpeg25": [11025, 12000, 8000, None],
}


def estimate_audio_duration_ms(*, audio_bytes: bytes, format_name: str) -> int | None:
    normalized_format = format_name.lower()
    if normalized_format == "mp3":
        return estimate_mp3_duration_ms(audio_bytes)
    return None


def estimate_mp3_duration_ms(audio_bytes: bytes) -> int | None:
    offset = _skip_id3v2(audio_bytes)
    total_seconds = 0.0
    frame_count = 0

    while offset + 4 <= len(audio_bytes):
        header = int.from_bytes(audio_bytes[offset : offset + 4], "big")
        frame = _parse_mp3_frame_header(header)
        if frame is None:
            offset += 1
            continue

        frame_size, samples_per_frame, sample_rate = frame
        if frame_size <= 0 or offset + frame_size > len(audio_bytes):
            break

        total_seconds += samples_per_frame / sample_rate
        frame_count += 1
        offset += frame_size

    if frame_count == 0:
        return None
    return int(round(total_seconds * 1000))


def _skip_id3v2(audio_bytes: bytes) -> int:
    if len(audio_bytes) < 10 or audio_bytes[:3] != b"ID3":
        return 0
    size_bytes = audio_bytes[6:10]
    if any(value & 0x80 for value in size_bytes):
        return 0
    tag_size = (
        (size_bytes[0] << 21)
        | (size_bytes[1] << 14)
        | (size_bytes[2] << 7)
        | size_bytes[3]
    )
    return min(10 + tag_size, len(audio_bytes))


def _parse_mp3_frame_header(header: int) -> tuple[int, int, int] | None:
    if (header & 0xFFE00000) != 0xFFE00000:
        return None

    version_bits = (header >> 19) & 0x3
    layer_bits = (header >> 17) & 0x3
    bitrate_index = (header >> 12) & 0xF
    sample_rate_index = (header >> 10) & 0x3
    padding = (header >> 9) & 0x1

    version = {0: "mpeg25", 2: "mpeg2", 3: "mpeg1"}.get(version_bits)
    layer = {1: "layer3", 2: "layer2", 3: "layer1"}.get(layer_bits)
    if version is None or layer is None:
        return None

    bitrate_version = "mpeg1" if version == "mpeg1" else "mpeg2"
    bitrate_kbps = _BITRATES_KBPS[(bitrate_version, layer)][bitrate_index]
    sample_rate = _SAMPLE_RATES[version][sample_rate_index]
    if bitrate_kbps is None or sample_rate is None:
        return None

    bitrate = bitrate_kbps * 1000
    if layer == "layer1":
        samples_per_frame = 384
        frame_size = (floor((12 * bitrate) / sample_rate) + padding) * 4
    elif layer == "layer2":
        samples_per_frame = 1152
        frame_size = floor((144 * bitrate) / sample_rate) + padding
    else:
        samples_per_frame = 1152 if version == "mpeg1" else 576
        coefficient = 144 if version == "mpeg1" else 72
        frame_size = floor((coefficient * bitrate) / sample_rate) + padding

    return frame_size, samples_per_frame, sample_rate
