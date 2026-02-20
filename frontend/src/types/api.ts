export interface UploadUrlRequest {
  category: string
  entityId: string
  filename: string
  contentType: string
}

export interface UploadUrlResponse {
  object_key: string
  upload_url: string
  asset_url: string
}

export interface CompleteUploadRequest {
  objectKey: string
  category?: string
  entityId?: string
  filename?: string
  contentType?: string
  fileSize?: number
  etag?: string
}

export interface CompleteUploadResponse {
  object_key: string
  asset_url: string
  status: string
  message: string
}
