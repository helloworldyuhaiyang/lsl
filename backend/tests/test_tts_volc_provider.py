from __future__ import annotations

from lsl.core.config import Settings
from lsl.modules.tts.providers.volc_tts import VolcTtsProvider


def test_volc_speaker_i18n_uses_hardcoded_cn_and_en_names() -> None:
    provider = VolcTtsProvider(Settings())

    speaker = next(
        item
        for item in provider.get_speakers()
        if item.speaker_id == "zh_female_xiaohe_uranus_bigtts"
    )

    assert speaker.name == "小何 2.0"
    assert speaker.display_name == "小何"
    assert speaker.i18n["zh-CN"]["name"] == "小何"
    assert speaker.i18n["en"]["name"] == "Xiaohe"
    assert speaker.avatar.get("initials") is None
