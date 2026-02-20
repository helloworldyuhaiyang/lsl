import { createUploadUrl } from '@/lib/api/assets'
import { requestJson } from '@/lib/api/client'
import type {
  CompleteUploadRequest,
  CompleteUploadResponse,
  UploadUrlRequest,
  UploadUrlResponse,
} from '@/types/api'

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
  return requestJson<CompleteUploadResponse>('/assets/complete-upload', {
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
}

interface UploadAssetParams {
  upload: UploadUrlRequest
  file: File
  onProgress?: (progress: number) => void
}

interface UploadAssetResult {
  uploadInfo: UploadUrlResponse
  completed: CompleteUploadResponse
}

export async function uploadAssetWithConfirmation({
  upload,
  file,
  onProgress,
}: UploadAssetParams): Promise<UploadAssetResult> {
  const uploadInfo = await createUploadUrl(upload)
  const { etag } = await uploadToPresignedUrl({
    uploadUrl: uploadInfo.upload_url,
    file,
    contentType: upload.contentType,
    onProgress,
  })

  const completed = await notifyUploadCompleted({
    objectKey: uploadInfo.object_key,
    category: upload.category,
    entityId: upload.entityId,
    filename: file.name,
    contentType: upload.contentType,
    fileSize: file.size,
    etag,
  })

  return {
    uploadInfo,
    completed,
  }
}
