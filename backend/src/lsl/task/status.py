from enum import IntEnum


class TaskStatus(IntEnum):
    UPLOADED = 0
    TRANSCRIBING = 1
    ANALYZING = 2
    COMPLETED = 3
    FAILED = 4


TASK_STATUS_NAME_MAP: dict[int, str] = {
    TaskStatus.UPLOADED: "uploaded",
    TaskStatus.TRANSCRIBING: "transcribing",
    TaskStatus.ANALYZING: "analyzing",
    TaskStatus.COMPLETED: "completed",
    TaskStatus.FAILED: "failed",
}


def status_code_to_name(status_code: int) -> str:
    return TASK_STATUS_NAME_MAP.get(status_code, "unknown")
