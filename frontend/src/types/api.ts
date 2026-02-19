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
