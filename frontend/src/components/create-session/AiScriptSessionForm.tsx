import { useCallback, useEffect, useRef, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { Loader2, Sparkles } from 'lucide-react';
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
import { generateScriptSession } from '@/lib/api/scripts';
import { mapSessionItem } from '@/lib/domain';
import { useI18n } from '@/i18n';

type AiScriptSessionFormProps = {
  active: boolean;
};

export function AiScriptSessionForm({ active }: AiScriptSessionFormProps) {
  const navigate = useNavigate();
  const { dispatch, refreshSessions } = useApp();
  const { t, language: uiLanguage } = useI18n();
  const [targetLanguage, setTargetLanguage] = useState('en-US');
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [errors, setErrors] = useState<Record<string, string>>({});
  const [sessionName, setSessionName] = useState('');
  const [sessionDescription, setSessionDescription] = useState('');
  const [scenarioPrompt, setScenarioPrompt] = useState('');
  const [turnCount, setTurnCount] = useState('8');
  const [speakerCount, setSpeakerCount] = useState('2');
  const [difficulty, setDifficulty] = useState<Difficulty>('Beginner');
  const [cueStyle, setCueStyle] = useState(() => t('create.defaultCueStyle'));
  const [mustInclude, setMustInclude] = useState('');
  const scenarioPromptRef = useRef<HTMLTextAreaElement | null>(null);

  const clearErrors = useCallback(() => setErrors({}), []);
  const adjustScenarioPromptHeight = useCallback((element?: HTMLTextAreaElement | null) => {
    if (!element) return;
    element.style.height = 'auto';
    element.style.height = `${element.scrollHeight}px`;
  }, []);

  useEffect(() => {
    if (!active) {
      clearErrors();
    }
  }, [active, clearErrors]);

  useEffect(() => {
    adjustScenarioPromptHeight(scenarioPromptRef.current);
  }, [scenarioPrompt, adjustScenarioPromptHeight]);

  const handleSubmit = useCallback(async () => {
    clearErrors();
    const newErrors: Record<string, string> = {};

    if (!sessionName.trim()) {
      newErrors.name = t('validation.sessionNameRequired');
    } else if (sessionName.trim().length < 2) {
      newErrors.name = t('validation.sessionNameTooShort');
    }

    if (!scenarioPrompt.trim()) {
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
      const result = await generateScriptSession({
        title: sessionName,
        description: sessionDescription,
        targetLanguage,
        cueLanguage: uiLanguage,
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
      void refreshSessions();
    } catch (error) {
      setErrors({
        submit: error instanceof Error ? error.message : t('error.createSession'),
      });
    } finally {
      setIsSubmitting(false);
    }
  }, [
    clearErrors,
    cueStyle,
    difficulty,
    dispatch,
    mustInclude,
    navigate,
    refreshSessions,
    scenarioPrompt,
    sessionDescription,
    sessionName,
    speakerCount,
    t,
    targetLanguage,
    turnCount,
    uiLanguage,
  ]);

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

      <div className="space-y-5">
        <div>
          <Label className="text-[12px] font-semibold text-slate-700">
            {t('create.scenarioPrompt')} <span className="text-red-400">*</span>
          </Label>
          <p className="mb-1.5 mt-0.5 text-[11px] text-slate-400">
            {t('create.scenarioHelp')}
          </p>
          <Textarea
            ref={scenarioPromptRef}
            value={scenarioPrompt}
            onChange={(event) => {
              setScenarioPrompt(event.target.value);
              adjustScenarioPromptHeight(event.target);
              clearErrors();
            }}
            placeholder={t('create.scenarioPlaceholder')}
            className={`resize-none overflow-hidden border-slate-200 text-[13px] focus:border-indigo-300 ${errors.prompt ? 'border-red-300' : ''}`}
            rows={4}
          />
          {errors.prompt && <p className="mt-1 text-[11px] text-red-500">{errors.prompt}</p>}
        </div>

        <div className="grid grid-cols-3 gap-4">
          <div>
            <Label className="text-[12px] font-semibold text-slate-700">{t('create.turns')}</Label>
            <Select value={turnCount} onValueChange={setTurnCount}>
              <SelectTrigger className="mt-1.5 h-10 border-slate-200 text-[13px]"><SelectValue /></SelectTrigger>
              <SelectContent>{['8', '12', '16', '20', '24'].map((value) => <SelectItem key={value} value={value}>{value}</SelectItem>)}</SelectContent>
            </Select>
          </div>
          <div>
            <Label className="text-[12px] font-semibold text-slate-700">{t('create.speakers')}</Label>
            <Select value={speakerCount} onValueChange={setSpeakerCount}>
              <SelectTrigger className="mt-1.5 h-10 border-slate-200 text-[13px]"><SelectValue /></SelectTrigger>
              <SelectContent>{['2', '3', '4'].map((value) => <SelectItem key={value} value={value}>{value}</SelectItem>)}</SelectContent>
            </Select>
          </div>
          <div>
            <Label className="text-[12px] font-semibold text-slate-700">{t('create.difficulty')}</Label>
            <Select value={difficulty} onValueChange={(value) => setDifficulty(value as Difficulty)}>
              <SelectTrigger className="mt-1.5 h-10 border-slate-200 text-[13px]"><SelectValue /></SelectTrigger>
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
            onChange={(event) => setCueStyle(event.target.value)}
            placeholder={t('create.cueStylePlaceholder')}
            className="mt-1.5 h-10 border-slate-200 text-[13px]"
          />
        </div>

        <div>
          <Label className="text-[12px] font-semibold text-slate-700">
            {t('create.mustInclude')} <span className="font-normal text-slate-400">({t('common.optional')})</span>
          </Label>
          <Input
            value={mustInclude}
            onChange={(event) => setMustInclude(event.target.value)}
            placeholder={t('create.mustIncludePlaceholder')}
            className="mt-1.5 h-10 border-slate-200 text-[13px]"
          />
        </div>
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
            {t('create.generating')}
          </span>
        ) : (
          <span className="flex items-center gap-2">
            <Sparkles className="h-4 w-4" />
            {t('create.generateScript')}
          </span>
        )}
      </Button>
    </div>
  );
}
