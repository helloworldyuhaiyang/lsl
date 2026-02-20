import { requestJson } from '@/lib/api/client'
import type {
  AssetListItem,
  AssetListResponse,
  CompleteUploadRequest,
  CompleteUploadResponse,
  UploadUrlRequest,
  UploadUrlResponse,
} from '@/types/api'

interface ApiResponse<T> {
  code: number
  message: string
  data: T
}

interface UploadToPresignedUrlParams {
  uploadUrl: string
  file: File
  contentType: string
  onProgress?: (progress: number) => void
}

interface UploadToPresignedUrlResult {
  etag?: string
}

export async function uploadToPresignedUrl({
  uploadUrl,
  file,
  contentType,
  onProgress,
}: UploadToPresignedUrlParams): Promise<UploadToPresignedUrlResult> {
  return new Promise<UploadToPresignedUrlResult>((resolve, reject) => {
    const xhr = new XMLHttpRequest()

    xhr.open('PUT', uploadUrl)
    xhr.setRequestHeader('Content-Type', contentType)

    xhr.upload.onprogress = (event) => {
      if (event.lengthComputable && onProgress) {
        onProgress(Math.round((event.loaded / event.total) * 100))
      }
    }

    xhr.onerror = () => {
      reject(new Error('Upload failed. Please check the network and retry.'))
    }

    xhr.onload = () => {
      if (xhr.status >= 200 && xhr.status < 300) {
        const etag = xhr.getResponseHeader('etag')?.replaceAll('"', '') ?? undefined
        resolve({ etag })
      } else {
        reject(new Error(`Upload failed with status ${xhr.status}`))
      }
    }

    xhr.send(file)
  })
}

export async function notifyUploadCompleted(payload: CompleteUploadRequest): Promise<CompleteUploadResponse> {
  const response = await requestJson<ApiResponse<CompleteUploadResponse>>('/assets/complete-upload', {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
    },
    body: JSON.stringify({
      object_key: payload.objectKey,
      category: payload.category,
      entity_id: payload.entityId,
      filename: payload.filename,
      content_type: payload.contentType,
      file_size: payload.fileSize,
      etag: payload.etag,
    }),
  })
  return response.data
}

interface CompleteUploadedAssetParams {
  uploadInfo: UploadUrlResponse
  upload: UploadUrlRequest
  file: File
  etag?: string
}

export async function prepareUploadUrl(payload: UploadUrlRequest): Promise<UploadUrlResponse> {
  const response = await requestJson<ApiResponse<UploadUrlResponse>>('/assets/upload-url', {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
    },
    body: JSON.stringify({
      category: payload.category,
      entity_id: payload.entityId,
      filename: payload.filename,
      content_type: payload.contentType,
    }),
  })
  return response.data
}

export async function completeUploadedAsset({
  uploadInfo,
  upload,
  file,
  etag,
}: CompleteUploadedAssetParams): Promise<CompleteUploadResponse> {
  return notifyUploadCompleted({
    objectKey: uploadInfo.object_key,
    category: upload.category,
    entityId: upload.entityId,
    filename: file.name,
    contentType: upload.contentType,
    fileSize: file.size,
    etag,
  })
}

interface ListAssetsParams {
  limit?: number
  category?: string
  entityId?: string
}

export async function listAssets({
  limit = 20,
  category,
  entityId,
}: ListAssetsParams = {}): Promise<AssetListItem[]> {
  const query: Record<string, string> = {
    limit: String(limit),
  }

  if (category) {
    query.category = category
  }
  if (entityId) {
    query.entity_id = entityId
  }

  const response = await requestJson<ApiResponse<AssetListResponse>>('/assets', {
    method: 'GET',
    query,
  })
  return response.data.items
}
