interface UploadToPresignedUrlParams {
  uploadUrl: string
  file: File
  contentType: string
  onProgress?: (progress: number) => void
}

export async function uploadToPresignedUrl({
  uploadUrl,
  file,
  contentType,
  onProgress,
}: UploadToPresignedUrlParams): Promise<void> {
  await new Promise<void>((resolve, reject) => {
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
        resolve()
      } else {
        reject(new Error(`Upload failed with status ${xhr.status}`))
      }
    }

    xhr.send(file)
  })
}
