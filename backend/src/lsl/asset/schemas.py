from pydantic import BaseModel, Field, field_validator


class CompleteUploadRequest(BaseModel):
    object_key: str = Field(..., min_length=1, max_length=1024)
    category: str | None = Field(default=None, max_length=64)
    entity_id: str | None = Field(default=None, max_length=128)
    filename: str | None = Field(default=None, max_length=255)
    content_type: str | None = Field(default=None, max_length=128)
    file_size: int | None = Field(default=None, ge=0)
    etag: str | None = Field(default=None, max_length=128)

    @field_validator("object_key")
    @classmethod
    def normalize_object_key(cls, value: str) -> str:
        normalized = value.strip().lstrip("/")
        if not normalized:
            raise ValueError("object_key is required")
        return normalized


class CompleteUploadResponse(BaseModel):
    object_key: str
    asset_url: str
    status: str = "acknowledged"
    message: str
