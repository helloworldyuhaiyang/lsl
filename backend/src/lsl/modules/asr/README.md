# LSL - ASR Module

ASR 模块负责音频识别过程，不保存标准 transcript 结果。

## 职责

- 创建 `asr_recognitions`
- 调用 ASR provider submit / query
- 通过 `job_type=asr_recognition` 接入通用 Job
- 成功后写入 Transcript 模块
- `target_language` 保存本次识别的目标语言快照，并写入最终 transcript 的 `language`

## API

- `POST /asr/recognitions`
- `GET /asr/recognitions`
- `GET /asr/recognitions/{recognition_id}`

`POST /asr/recognitions` 请求体使用 `target_language`，例如：

```json
{
  "object_key": "conversation/audio.m4a",
  "audio_url": "https://example.com/audio.m4a",
  "target_language": "en-US"
}
```
