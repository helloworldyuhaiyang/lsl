import { useState, useCallback, useRef } from 'react';
import { UploadCloud, FileAudio, X, Check } from 'lucide-react';
import { cn } from '@/lib/utils';

interface FileUploadProps {
  onFileSelect: (file: File | null) => void;
  accept?: string;
}

export function FileUpload({ onFileSelect, accept = '.mp3,.wav,.m4a' }: FileUploadProps) {
  const [isDragging, setIsDragging] = useState(false);
  const [selectedFile, setSelectedFile] = useState<File | null>(null);
  const inputRef = useRef<HTMLInputElement>(null);

  const handleDragOver = useCallback((e: React.DragEvent) => {
    e.preventDefault();
    setIsDragging(true);
  }, []);

  const handleDragLeave = useCallback((e: React.DragEvent) => {
    e.preventDefault();
    setIsDragging(false);
  }, []);

  const handleDrop = useCallback((e: React.DragEvent) => {
    e.preventDefault();
    setIsDragging(false);
    const file = e.dataTransfer.files[0];
    if (file) {
      setSelectedFile(file);
      onFileSelect(file);
    }
  }, [onFileSelect]);

  const handleClick = useCallback(() => {
    inputRef.current?.click();
  }, []);

  const handleFileChange = useCallback((e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0] || null;
    setSelectedFile(file);
    onFileSelect(file);
  }, [onFileSelect]);

  const handleRemove = useCallback(() => {
    setSelectedFile(null);
    onFileSelect(null);
    if (inputRef.current) inputRef.current.value = '';
  }, [onFileSelect]);

  if (selectedFile) {
    return (
      <div className="border border-emerald-200 rounded-xl p-4 bg-emerald-50/50">
        <div className="flex items-center gap-3">
          <div className="w-10 h-10 rounded-lg bg-emerald-100 flex items-center justify-center">
            <FileAudio className="w-5 h-5 text-emerald-600" />
          </div>
          <div className="flex-1 min-w-0">
            <p className="text-[13px] font-medium text-slate-800 truncate">{selectedFile.name}</p>
            <p className="text-[11px] text-slate-500">{(selectedFile.size / 1024 / 1024).toFixed(2)} MB</p>
          </div>
          <div className="flex items-center gap-2">
            <span className="flex items-center gap-1 text-[11px] font-medium text-emerald-600">
              <Check className="w-3.5 h-3.5" /> Ready
            </span>
            <button onClick={handleRemove} className="p-1.5 hover:bg-white rounded-md transition-colors">
              <X className="w-4 h-4 text-slate-400" />
            </button>
          </div>
        </div>
      </div>
    );
  }

  return (
    <div
      onClick={handleClick}
      onDragOver={handleDragOver}
      onDragLeave={handleDragLeave}
      onDrop={handleDrop}
      className={cn(
        'border-2 border-dashed rounded-xl h-[180px] flex flex-col items-center justify-center cursor-pointer transition-all duration-200',
        isDragging
          ? 'border-indigo-400 bg-indigo-50'
          : 'border-slate-200 bg-white hover:border-slate-300 hover:bg-slate-50/50'
      )}
    >
      <input ref={inputRef} type="file" accept={accept} onChange={handleFileChange} className="hidden" />
      <div className={cn(
        'w-12 h-12 rounded-xl flex items-center justify-center mb-3 transition-colors',
        isDragging ? 'bg-indigo-100' : 'bg-slate-100'
      )}>
        <UploadCloud className={cn('w-6 h-6', isDragging ? 'text-indigo-500' : 'text-slate-400')} />
      </div>
      <p className="text-[13px] text-slate-600 font-medium">
        {isDragging ? 'Drop your file here' : 'Drag & drop or click to upload'}
      </p>
      <p className="text-[11px] text-slate-400 mt-1">MP3, WAV, M4A up to 100MB</p>
    </div>
  );
}
