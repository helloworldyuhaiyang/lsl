import { useState, useCallback } from 'react';
import { useNavigate } from 'react-router-dom';
import { ArrowLeft, Sparkles, Mic, Loader2 } from 'lucide-react';
import { FileUpload } from '@/components/FileUpload';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Textarea } from '@/components/ui/textarea';
import { Label } from '@/components/ui/label';
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select';
import { useApp } from '@/context/AppContext';
import { validateSessionName, validateFile, validateScenarioPrompt } from '@/utils/validateForm';
import type { Difficulty } from '@/types';
import { cn } from '@/lib/utils';
import { Link } from 'react-router-dom';
import { createSession } from '@/lib/api/sessions';
import { createAsrRecognition } from '@/lib/api/asr';
import { completeUploadedAsset, prepareUploadUrl, uploadToPresignedUrl } from '@/lib/api/upload';
import { generateScriptSession } from '@/lib/api/scripts';
import { mapSessionItem } from '@/lib/domain';

const DEFAULT_CUE_STYLE = '自然口语、便于 TTS 演绎';

export function CreateSession() {
  const navigate = useNavigate();
  const { dispatch, refreshSessions } = useApp();
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
  const [cueStyle, setCueStyle] = useState(DEFAULT_CUE_STYLE);
  const [mustInclude, setMustInclude] = useState('');

  const clearErrors = useCallback(() => setErrors({}), []);

  const handleSubmit = useCallback(async () => {
    clearErrors();
    const newErrors: Record<string, string> = {};

    const nameError = validateSessionName(sessionName);
    if (nameError) newErrors.name = nameError.message;

    if (mode === 'audio') {
      const fileError = validateFile(selectedFile);
      if (fileError) newErrors.file = fileError.message;
    } else {
      const promptError = validateScenarioPrompt(scenarioPrompt);
      if (promptError) newErrors.prompt = promptError.message;
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
        submit: error instanceof Error ? error.message : 'Failed to create session',
      });
    } finally {
      setIsSubmitting(false);
    }
  }, [sessionName, sessionDescription, selectedFile, scenarioPrompt, mode, clearErrors, dispatch, navigate, refreshSessions, turnCount, speakerCount, difficulty, cueStyle, mustInclude]);

  return (
    <div className="max-w-2xl space-y-6">
      {/* Header */}
      <div>
        <Link to="/" className="inline-flex items-center gap-1.5 text-[12px] text-slate-500 hover:text-indigo-600 transition-colors mb-4">
          <ArrowLeft className="w-3.5 h-3.5" />
          Back to Dashboard
        </Link>
        <h1 className="text-[22px] font-bold text-slate-900 tracking-tight">Create Session</h1>
        <p className="text-[13px] text-slate-500 mt-0.5">Upload audio or generate an AI script with CUE annotations</p>
      </div>

      {/* Mode Toggle */}
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
          <Mic className="w-4 h-4" /> Audio Upload
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
          <Sparkles className="w-4 h-4" /> AI Script
        </button>
      </div>

      {/* Form */}
      <div className="bg-white rounded-xl border border-slate-200 p-6 shadow-sm space-y-5">
        {/* Session Name */}
        <div>
          <Label className="text-[12px] font-semibold text-slate-700">Session Name <span className="text-red-400">*</span></Label>
          <Input
            value={sessionName}
            onChange={(e) => { setSessionName(e.target.value); clearErrors(); }}
            placeholder="e.g., Job Interview Practice"
            className={`mt-1.5 text-[13px] border-slate-200 focus:border-indigo-300 h-10 ${errors.name ? 'border-red-300' : ''}`}
          />
          {errors.name && <p className="text-[11px] text-red-500 mt-1">{errors.name}</p>}
        </div>

        {/* Description */}
        <div>
          <Label className="text-[12px] font-semibold text-slate-700">Description <span className="text-slate-400 font-normal">(optional)</span></Label>
          <Textarea
            value={sessionDescription}
            onChange={(e) => setSessionDescription(e.target.value)}
            placeholder="Brief description of this session..."
            className="mt-1.5 text-[13px] border-slate-200 focus:border-indigo-300 resize-none"
            rows={2}
          />
        </div>

        {/* Mode-specific fields */}
        {mode === 'audio' ? (
          <div>
            <Label className="text-[12px] font-semibold text-slate-700">Audio File <span className="text-red-400">*</span></Label>
            <div className="mt-1.5">
              <FileUpload onFileSelect={(file) => { setSelectedFile(file); clearErrors(); }} />
            </div>
            {errors.file && <p className="text-[11px] text-red-500 mt-1">{errors.file}</p>}
          </div>
        ) : (
          <div className="space-y-5">
            <div>
              <Label className="text-[12px] font-semibold text-slate-700">Scenario Prompt <span className="text-red-400">*</span></Label>
              <p className="text-[11px] text-slate-400 mt-0.5 mb-1.5">
                Describe the scene, speakers, and key content. AI will generate dialogue with embedded CUE markers.
              </p>
              <Textarea
                value={scenarioPrompt}
                onChange={(e) => { setScenarioPrompt(e.target.value); clearErrors(); }}
                placeholder="e.g., A job interview at a tech company. The candidate is confident but slightly nervous..."
                className={`text-[13px] border-slate-200 focus:border-indigo-300 resize-none ${errors.prompt ? 'border-red-300' : ''}`}
                rows={4}
              />
              {errors.prompt && <p className="text-[11px] text-red-500 mt-1">{errors.prompt}</p>}
            </div>

            <div className="grid grid-cols-3 gap-4">
              <div>
                <Label className="text-[12px] font-semibold text-slate-700">Turns</Label>
                <Select value={turnCount} onValueChange={setTurnCount}>
                  <SelectTrigger className="mt-1.5 h-10 text-[13px] border-slate-200"><SelectValue /></SelectTrigger>
                  <SelectContent>{['8', '12', '16', '20', '24'].map(v => <SelectItem key={v} value={v}>{v}</SelectItem>)}</SelectContent>
                </Select>
              </div>
              <div>
                <Label className="text-[12px] font-semibold text-slate-700">Speakers</Label>
                <Select value={speakerCount} onValueChange={setSpeakerCount}>
                  <SelectTrigger className="mt-1.5 h-10 text-[13px] border-slate-200"><SelectValue /></SelectTrigger>
                  <SelectContent>{['2', '3', '4'].map(v => <SelectItem key={v} value={v}>{v}</SelectItem>)}</SelectContent>
                </Select>
              </div>
              <div>
                <Label className="text-[12px] font-semibold text-slate-700">Difficulty</Label>
                <Select value={difficulty} onValueChange={(v) => setDifficulty(v as Difficulty)}>
                  <SelectTrigger className="mt-1.5 h-10 text-[13px] border-slate-200"><SelectValue /></SelectTrigger>
                  <SelectContent>{['Beginner', 'Intermediate', 'Advanced'].map(v => <SelectItem key={v} value={v}>{v}</SelectItem>)}</SelectContent>
                </Select>
              </div>
            </div>

            <div>
              <Label className="text-[12px] font-semibold text-slate-700">CUE Style</Label>
              <Input
                value={cueStyle}
                onChange={(e) => setCueStyle(e.target.value)}
                placeholder="e.g., Casual, professional, emotional..."
                className="mt-1.5 text-[13px] border-slate-200 h-10"
              />
            </div>

            <div>
              <Label className="text-[12px] font-semibold text-slate-700">Must-Include Expressions <span className="text-slate-400 font-normal">(optional)</span></Label>
              <Input
                value={mustInclude}
                onChange={(e) => setMustInclude(e.target.value)}
                placeholder="Expressions to include in the dialogue..."
                className="mt-1.5 text-[13px] border-slate-200 h-10"
              />
            </div>
          </div>
        )}

        {/* Submit */}
        {errors.submit && <p className="text-[12px] text-red-500">{errors.submit}</p>}
        <Button
          onClick={handleSubmit}
          disabled={isSubmitting}
          className="w-full bg-indigo-500 hover:bg-indigo-600 text-white h-11 text-[13px] font-semibold disabled:opacity-60"
        >
          {isSubmitting ? (
            <span className="flex items-center gap-2">
              <Loader2 className="w-4 h-4 animate-spin" />
              {mode === 'audio' ? 'Creating...' : 'Generating...'}
            </span>
          ) : (
            <span className="flex items-center gap-2">
              {mode === 'audio' ? <Mic className="w-4 h-4" /> : <Sparkles className="w-4 h-4" />}
              {mode === 'audio' ? 'Create Audio Session' : 'Generate CUE Script'}
            </span>
          )}
        </Button>
      </div>
    </div>
  );
}
