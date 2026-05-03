# LSL - Transcript Module

Transcript 模块负责统一的 utterance stream 产物，不关心内容来自 ASR、AI script、手动输入还是导入。

## 职责

- 管理 `transcript_transcripts` 与 `transcript_utterances`
- 提供 pending / completed / failed 状态
- 保存标准字段：`seq`、`speaker`、`text`、`start_time`、`end_time`、`additions`
- 通过 `source_type + source_entity_id` 指回生产者模块

## Source Type

- `asr`
- `ai_script`
- `manual`
- `import`

## API

- `GET /transcripts`
- `GET /transcripts/{transcript_id}`
- `GET /transcripts/{transcript_id}/utterances`
