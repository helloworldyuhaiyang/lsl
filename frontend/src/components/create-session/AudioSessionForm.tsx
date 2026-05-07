import { useCallback, useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { Loader2, Mic } from 'lucide-react';
import { FileUpload } from '@/components/FileUpload';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select';
import { Textarea } from '@/components/ui/textarea';
import { useApp } from '@/context/AppContext';
import { createAsrRecognition } from '@/lib/api/asr';
import { createSession } from '@/lib/api/sessions';
import { completeUploadedAsset, prepareUploadUrl, uploadToPresignedUrl } from '@/lib/api/upload';
import { createClientUuid } from '@/lib/clientId';
import { mapSessionItem } from '@/lib/domain';
import { useI18n } from '@/i18n';

type AudioSessionFormProps = {
  active: boolean;
};

export function AudioSessionForm({ active }: AudioSessionFormProps) {
  const navigate = useNavigate();
  const { dispatch, refreshSessions } = useApp();
  const { t } = useI18n();
  const [targetLanguage, setTargetLanguage] = useState('en-US');
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [errors, setErrors] = useState<Record<string, string>>({});
  const [sessionName, setSessionName] = useState('');
  const [sessionDescription, setSessionDescription] = useState('');
  const [selectedFile, setSelectedFile] = useState<File | null>(null);

  const clearErrors = useCallback(() => setErrors({}), []);

  useEffect(() => {
    if (!active) {
      clearErrors();
    }
  }, [active, clearErrors]);

  const handleSubmit = useCallback(async () => {
    clearErrors();
    const newErrors: Record<string, string> = {};

    if (!sessionName.trim()) {
      newErrors.name = t('validation.sessionNameRequired');
    } else if (sessionName.trim().length < 2) {
      newErrors.name = t('validation.sessionNameTooShort');
    }

    if (!selectedFile) {
      newErrors.file = t('validation.fileRequired');
    } else {
      const validTypes = ['audio/mpeg', 'audio/wav', 'audio/x-wav', 'audio/mp4', 'audio/x-m4a'];
      const validExtensions = ['.mp3', '.wav', '.m4a'];
      const hasValidType = validTypes.includes(selectedFile.type);
      const hasValidExt = validExtensions.some((ext) => selectedFile.name.toLowerCase().endsWith(ext));
      if (!hasValidType && !hasValidExt) {
        newErrors.file = t('validation.fileUnsupported');
      }
    }

    if (Object.keys(newErrors).length > 0) {
      setErrors(newErrors);
      return;
    }

    setIsSubmitting(true);

    try {
      if (!selectedFile) return;
      const upload = {
        category: 'audio',
        entityId: createClientUuid(),
        filename: selectedFile.name,
        contentType: selectedFile.type || 'audio/mpeg',
      };
      const uploadInfo = await prepareUploadUrl(upload);
      const { etag } = await uploadToPresignedUrl({
        uploadUrl: uploadInfo.upload_url,
        file: selectedFile,
        contentType: upload.contentType,
      });
      await completeUploadedAsset({ uploadInfo, upload, file: selectedFile, etag });
      const recognition = await createAsrRecognition({
        objectKey: uploadInfo.object_key,
        audioUrl: uploadInfo.asset_url,
        targetLanguage,
      });
      const item = await createSession({
        title: sessionName,
        description: sessionDescription || selectedFile.name,
        targetLanguage,
        fType: 1,
        assetObjectKey: uploadInfo.object_key,
        currentTranscriptId: recognition.transcript.transcript_id,
      });
      const session = mapSessionItem(item);
      dispatch({ type: 'ADD_SESSION', payload: session });
      navigate(`/session/${session.id}`);
      void refreshSessions();
    } catch (error) {
      setErrors({
        submit: error instanceof Error ? error.message : t('error.createSession'),
      });
    } finally {
      setIsSubmitting(false);
    }
  }, [clearErrors, dispatch, navigate, refreshSessions, selectedFile, sessionDescription, sessionName, t, targetLanguage]);

  return (
    <div hidden={!active} className="space-y-5 rounded-xl border border-slate-200 bg-white p-6 shadow-sm">
      <div>
        <Label className="text-[12px] font-semibold text-slate-700">
          {t('create.sessionName')} <span className="text-red-400">*</span>
        </Label>
        <Input
          value={sessionName}
          onChange={(event) => {
            setSessionName(event.target.value);
            clearErrors();
          }}
          placeholder={t('create.sessionNamePlaceholder')}
          className={`mt-1.5 h-10 border-slate-200 text-[13px] focus:border-indigo-300 ${errors.name ? 'border-red-300' : ''}`}
        />
        {errors.name && <p className="mt-1 text-[11px] text-red-500">{errors.name}</p>}
      </div>

      <div>
        <Label className="text-[12px] font-semibold text-slate-700">
          {t('create.description')} <span className="font-normal text-slate-400">({t('common.optional')})</span>
        </Label>
        <Textarea
          value={sessionDescription}
          onChange={(event) => setSessionDescription(event.target.value)}
          placeholder={t('create.descriptionPlaceholder')}
          className="mt-1.5 resize-none border-slate-200 text-[13px] focus:border-indigo-300"
          rows={2}
        />
      </div>

      <div>
        <Label className="text-[12px] font-semibold text-slate-700">{t('create.targetLanguage')}</Label>
        <Select value={targetLanguage} onValueChange={setTargetLanguage}>
          <SelectTrigger className="mt-1.5 h-10 border-slate-200 text-[13px]"><SelectValue /></SelectTrigger>
          <SelectContent>
            <SelectItem value="en-US">{t('create.targetLanguage.english')}</SelectItem>
            <SelectItem value="zh-CN">{t('create.targetLanguage.chinese')}</SelectItem>
          </SelectContent>
        </Select>
      </div>

      <div>
        <Label className="text-[12px] font-semibold text-slate-700">
          {t('create.audioFile')} <span className="text-red-400">*</span>
        </Label>
        <div className="mt-1.5">
          <FileUpload onFileSelect={(file) => {
            setSelectedFile(file);
            clearErrors();
          }} />
        </div>
        {errors.file && <p className="mt-1 text-[11px] text-red-500">{errors.file}</p>}
      </div>

      {errors.submit && <p className="text-[12px] text-red-500">{errors.submit}</p>}
      <Button
        onClick={handleSubmit}
        disabled={isSubmitting}
        className="h-11 w-full bg-indigo-500 text-[13px] font-semibold text-white hover:bg-indigo-600 disabled:opacity-60"
      >
        {isSubmitting ? (
          <span className="flex items-center gap-2">
            <Loader2 className="h-4 w-4 animate-spin" />
            {t('create.creating')}
          </span>
        ) : (
          <span className="flex items-center gap-2">
            <Mic className="h-4 w-4" />
            {t('create.createAudio')}
          </span>
        )}
      </Button>
    </div>
  );
}
