# LSL - ASR Module

ASR 模块负责音频识别过程，不保存标准 transcript 结果。

## 职责

- 创建 `asr_recognitions`
- 调用 ASR provider submit / query
- 通过 `job_type=asr_recognition` 接入通用 Job
- 成功后写入 Transcript 模块

## API

- `POST /asr/recognitions`
- `GET /asr/recognitions`
- `GET /asr/recognitions/{recognition_id}`
