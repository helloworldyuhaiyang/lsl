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
}

export interface AssetListItem {
  object_key: string
  category: string
  entity_id: string
  filename?: string | null
  content_type?: string | null
  file_size?: number | null
  etag?: string | null
  upload_status: number
  created_at: string
  asset_url: string
}

export interface AssetListResponse {
  items: AssetListItem[]
}
