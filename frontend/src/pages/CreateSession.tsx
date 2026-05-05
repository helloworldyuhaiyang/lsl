import { useCallback, useState } from 'react';
import { Link, useNavigate } from 'react-router-dom';
import { ArrowLeft, Loader2, Mic, Sparkles } from 'lucide-react';
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
import type { Difficulty } from '@/types';
import { cn } from '@/lib/utils';
import { createSession } from '@/lib/api/sessions';
import { createAsrRecognition } from '@/lib/api/asr';
import { completeUploadedAsset, prepareUploadUrl, uploadToPresignedUrl } from '@/lib/api/upload';
import { generateScriptSession } from '@/lib/api/scripts';
import { mapSessionItem } from '@/lib/domain';
import { useI18n } from '@/i18n';

export function CreateSession() {
  const navigate = useNavigate();
  const { dispatch, refreshSessions } = useApp();
  const { t } = useI18n();
  const [mode, setMode] = useState<'audio' | 'script'>('audio');
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [errors, setErrors] = useState<Record<string, string>>({});

  const [sessionName, setSessionName] = useState('');
  const [sessionDescription, setSessionDescription] = useState('');
  const [selectedFile, setSelectedFile] = useState<File | null>(null);
  const [scenarioPrompt, setScenarioPrompt] = useState('');
  const [turnCount, setTurnCount] = useState('8');
  const [speakerCount, setSpeakerCount] = useState('2');
  const [difficulty, setDifficulty] = useState<Difficulty>('Beginner');
  const [cueStyle, setCueStyle] = useState(() => t('create.defaultCueStyle'));
  const [mustInclude, setMustInclude] = useState('');

  const clearErrors = useCallback(() => setErrors({}), []);

  const handleSubmit = useCallback(async () => {
    clearErrors();
    const newErrors: Record<string, string> = {};

    if (!sessionName.trim()) {
      newErrors.name = t('validation.sessionNameRequired');
    } else if (sessionName.trim().length < 2) {
      newErrors.name = t('validation.sessionNameTooShort');
    }

    if (mode === 'audio') {
      if (!selectedFile) {
        newErrors.file = t('validation.fileRequired');
      } else {
        const validTypes = ['audio/mpeg', 'audio/wav', 'audio/x-wav', 'audio/mp4', 'audio/x-m4a'];
        const validExtensions = ['.mp3', '.wav', '.m4a'];
        const hasValidType = validTypes.includes(selectedFile.type);
        const hasValidExt = validExtensions.some(ext => selectedFile.name.toLowerCase().endsWith(ext));
        if (!hasValidType && !hasValidExt) {
          newErrors.file = t('validation.fileUnsupported');
        }
      }
    } else if (!scenarioPrompt.trim()) {
      newErrors.prompt = t('validation.promptRequired');
    } else if (scenarioPrompt.trim().length < 10) {
      newErrors.prompt = t('validation.promptTooShort');
    }

    if (Object.keys(newErrors).length > 0) {
      setErrors(newErrors);
      return;
    }

    setIsSubmitting(true);

    try {
      if (mode === 'audio') {
        if (!selectedFile) return;
        const upload = {
          category: 'audio',
          entityId: crypto.randomUUID(),
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
          language: 'en',
        });
        const item = await createSession({
          title: sessionName,
          description: sessionDescription || selectedFile.name,
          language: 'en',
          fType: 1,
          assetObjectKey: uploadInfo.object_key,
          currentTranscriptId: recognition.transcript.transcript_id,
        });
        const session = mapSessionItem(item);
        dispatch({ type: 'ADD_SESSION', payload: session });
        navigate(`/session/${session.id}`);
      } else {
        const result = await generateScriptSession({
          title: sessionName,
          description: sessionDescription,
          language: 'en',
          prompt: scenarioPrompt,
          turnCount: Number(turnCount),
          speakerCount: Number(speakerCount),
          difficulty,
          cueStyle,
          mustInclude: mustInclude.split(',').map((item) => item.trim()).filter(Boolean),
        });
        const session = {
          ...mapSessionItem(result.session),
          userPrompt: scenarioPrompt,
        };
        dispatch({ type: 'ADD_SESSION', payload: session });
        const params = new URLSearchParams({
          generation_id: result.generation.generation_id,
          job_id: result.job.job_id,
        });
        navigate(`/session/${session.id}/revise?${params.toString()}`);
      }
      void refreshSessions();
    } catch (error) {
      setErrors({
        submit: error instanceof Error ? error.message : t('error.createSession'),
      });
    } finally {
      setIsSubmitting(false);
    }
  }, [sessionName, mode, clearErrors, selectedFile, scenarioPrompt, t, sessionDescription, dispatch, navigate, turnCount, speakerCount, difficulty, cueStyle, mustInclude, refreshSessions]);

  return (
    <div className="max-w-2xl space-y-6">
      <div>
        <Link to="/" className="inline-flex items-center gap-1.5 text-[12px] text-slate-500 hover:text-indigo-600 transition-colors mb-4">
          <ArrowLeft className="w-3.5 h-3.5" />
          {t('create.back')}
        </Link>
        <h1 className="text-[22px] font-bold text-slate-900 tracking-tight">{t('create.title')}</h1>
        <p className="text-[13px] text-slate-500 mt-0.5">{t('create.subtitle')}</p>
      </div>

      <div className="bg-slate-100 rounded-xl p-1 flex gap-1">
        <button
          onClick={() => { setMode('audio'); clearErrors(); }}
          className={cn(
            'flex-1 flex items-center justify-center gap-2 py-2.5 rounded-lg text-[13px] font-medium transition-all duration-200',
            mode === 'audio'
              ? 'bg-white text-slate-800 shadow-sm'
              : 'text-slate-500 hover:text-slate-700'
          )}
        >
          <Mic className="w-4 h-4" /> {t('create.audioUpload')}
        </button>
        <button
          onClick={() => { setMode('script'); clearErrors(); }}
          className={cn(
            'flex-1 flex items-center justify-center gap-2 py-2.5 rounded-lg text-[13px] font-medium transition-all duration-200',
            mode === 'script'
              ? 'bg-white text-slate-800 shadow-sm'
              : 'text-slate-500 hover:text-slate-700'
          )}
        >
          <Sparkles className="w-4 h-4" /> {t('create.aiScript')}
        </button>
      </div>

      <div className="bg-white rounded-xl border border-slate-200 p-6 shadow-sm space-y-5">
        <div>
          <Label className="text-[12px] font-semibold text-slate-700">{t('create.sessionName')} <span className="text-red-400">*</span></Label>
          <Input
            value={sessionName}
            onChange={(e) => { setSessionName(e.target.value); clearErrors(); }}
            placeholder={t('create.sessionNamePlaceholder')}
            className={`mt-1.5 text-[13px] border-slate-200 focus:border-indigo-300 h-10 ${errors.name ? 'border-red-300' : ''}`}
          />
          {errors.name && <p className="text-[11px] text-red-500 mt-1">{errors.name}</p>}
        </div>

        <div>
          <Label className="text-[12px] font-semibold text-slate-700">
            {t('create.description')} <span className="text-slate-400 font-normal">({t('common.optional')})</span>
          </Label>
          <Textarea
            value={sessionDescription}
            onChange={(e) => setSessionDescription(e.target.value)}
            placeholder={t('create.descriptionPlaceholder')}
            className="mt-1.5 text-[13px] border-slate-200 focus:border-indigo-300 resize-none"
            rows={2}
          />
        </div>

        {mode === 'audio' ? (
          <div>
            <Label className="text-[12px] font-semibold text-slate-700">{t('create.audioFile')} <span className="text-red-400">*</span></Label>
            <div className="mt-1.5">
              <FileUpload onFileSelect={(file) => { setSelectedFile(file); clearErrors(); }} />
            </div>
            {errors.file && <p className="text-[11px] text-red-500 mt-1">{errors.file}</p>}
          </div>
        ) : (
          <div className="space-y-5">
            <div>
              <Label className="text-[12px] font-semibold text-slate-700">{t('create.scenarioPrompt')} <span className="text-red-400">*</span></Label>
              <p className="text-[11px] text-slate-400 mt-0.5 mb-1.5">
                {t('create.scenarioHelp')}
              </p>
              <Textarea
                value={scenarioPrompt}
                onChange={(e) => { setScenarioPrompt(e.target.value); clearErrors(); }}
                placeholder={t('create.scenarioPlaceholder')}
                className={`text-[13px] border-slate-200 focus:border-indigo-300 resize-none ${errors.prompt ? 'border-red-300' : ''}`}
                rows={4}
              />
              {errors.prompt && <p className="text-[11px] text-red-500 mt-1">{errors.prompt}</p>}
            </div>

            <div className="grid grid-cols-3 gap-4">
              <div>
                <Label className="text-[12px] font-semibold text-slate-700">{t('create.turns')}</Label>
                <Select value={turnCount} onValueChange={setTurnCount}>
                  <SelectTrigger className="mt-1.5 h-10 text-[13px] border-slate-200"><SelectValue /></SelectTrigger>
                  <SelectContent>{['8', '12', '16', '20', '24'].map(v => <SelectItem key={v} value={v}>{v}</SelectItem>)}</SelectContent>
                </Select>
              </div>
              <div>
                <Label className="text-[12px] font-semibold text-slate-700">{t('create.speakers')}</Label>
                <Select value={speakerCount} onValueChange={setSpeakerCount}>
                  <SelectTrigger className="mt-1.5 h-10 text-[13px] border-slate-200"><SelectValue /></SelectTrigger>
                  <SelectContent>{['2', '3', '4'].map(v => <SelectItem key={v} value={v}>{v}</SelectItem>)}</SelectContent>
                </Select>
              </div>
              <div>
                <Label className="text-[12px] font-semibold text-slate-700">{t('create.difficulty')}</Label>
                <Select value={difficulty} onValueChange={(v) => setDifficulty(v as Difficulty)}>
                  <SelectTrigger className="mt-1.5 h-10 text-[13px] border-slate-200"><SelectValue /></SelectTrigger>
                  <SelectContent>
                    <SelectItem value="Beginner">{t('create.difficulty.beginner')}</SelectItem>
                    <SelectItem value="Intermediate">{t('create.difficulty.intermediate')}</SelectItem>
                    <SelectItem value="Advanced">{t('create.difficulty.advanced')}</SelectItem>
                  </SelectContent>
                </Select>
              </div>
            </div>

            <div>
              <Label className="text-[12px] font-semibold text-slate-700">{t('create.cueStyle')}</Label>
              <Input
                value={cueStyle}
                onChange={(e) => setCueStyle(e.target.value)}
                placeholder={t('create.cueStylePlaceholder')}
                className="mt-1.5 text-[13px] border-slate-200 h-10"
              />
            </div>

            <div>
              <Label className="text-[12px] font-semibold text-slate-700">
                {t('create.mustInclude')} <span className="text-slate-400 font-normal">({t('common.optional')})</span>
              </Label>
              <Input
                value={mustInclude}
                onChange={(e) => setMustInclude(e.target.value)}
                placeholder={t('create.mustIncludePlaceholder')}
                className="mt-1.5 text-[13px] border-slate-200 h-10"
              />
            </div>
          </div>
        )}

        {errors.submit && <p className="text-[12px] text-red-500">{errors.submit}</p>}
        <Button
          onClick={handleSubmit}
          disabled={isSubmitting}
          className="w-full bg-indigo-500 hover:bg-indigo-600 text-white h-11 text-[13px] font-semibold disabled:opacity-60"
        >
          {isSubmitting ? (
            <span className="flex items-center gap-2">
              <Loader2 className="w-4 h-4 animate-spin" />
              {mode === 'audio' ? t('create.creating') : t('create.generating')}
            </span>
          ) : (
            <span className="flex items-center gap-2">
              {mode === 'audio' ? <Mic className="w-4 h-4" /> : <Sparkles className="w-4 h-4" />}
              {mode === 'audio' ? t('create.createAudio') : t('create.generateScript')}
            </span>
          )}
        </Button>
      </div>
    </div>
  );
}
