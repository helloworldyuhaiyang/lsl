import { useMemo, useState } from 'react';
import { Link } from 'react-router-dom';
import {
  ArrowRight,
  AudioLines,
  CheckCircle2,
  CirclePlay,
  Headphones,
  Mic,
  RefreshCcw,
  Sparkles,
  UploadCloud,
  Wand2,
} from 'lucide-react';
import { Button } from '@/components/ui/button';
import { cn } from '@/lib/utils';
import { useI18n } from '@/i18n';

const cueOptions = [
  {
    cueKey: 'landing.cue.option1.cue',
    toneKey: 'landing.cue.option1.tone',
    textKey: 'landing.cue.option1.text',
    speed: '0.92x',
  },
  {
    cueKey: 'landing.cue.option2.cue',
    toneKey: 'landing.cue.option2.tone',
    textKey: 'landing.cue.option2.text',
    speed: '1.00x',
  },
  {
    cueKey: 'landing.cue.option3.cue',
    toneKey: 'landing.cue.option3.tone',
    textKey: 'landing.cue.option3.text',
    speed: '0.84x',
  },
] as const;

export function Landing() {
  const { t } = useI18n();
  const [activeCue, setActiveCue] = useState(0);
  const cue = cueOptions[activeCue];

  const sources = useMemo(() => [
    {
      icon: UploadCloud,
      label: t('landing.source.audio.label'),
      title: t('landing.source.audio.title'),
      description: t('landing.source.audio.description'),
      steps: [
        t('landing.source.audio.step1'),
        t('landing.source.audio.step2'),
        t('landing.source.audio.step3'),
      ],
      tone: 'indigo',
    },
    {
      icon: Sparkles,
      label: t('landing.source.script.label'),
      title: t('landing.source.script.title'),
      description: t('landing.source.script.description'),
      steps: [
        t('landing.source.script.step1'),
        t('landing.source.script.step2'),
        t('landing.source.script.step3'),
      ],
      tone: 'violet',
    },
  ], [t]);

  return (
    <div className="space-y-16 pb-12">
      <section className="landing-hero-bg -mx-4 -mt-6 border-b border-slate-200 px-4 py-12 sm:-mx-6 sm:px-6 sm:py-16 lg:-mx-8 lg:px-8">
        <div className="mx-auto grid max-w-[1100px] items-center gap-10 lg:grid-cols-[0.95fr_1.05fr]">
          <div className="min-w-0">
            <div className="mb-5 inline-flex items-center gap-2 rounded-lg border border-indigo-100 bg-white px-3 py-2 text-[12px] font-semibold text-indigo-600 shadow-sm">
              <RefreshCcw className="h-3.5 w-3.5" />
              {t('landing.loop')}
            </div>

            <h1 className="max-w-[640px] text-[36px] font-bold leading-[1.12] tracking-tight text-slate-950 sm:text-[46px]">
              {t('landing.hero.title')}
            </h1>
            <p className="mt-5 max-w-[620px] text-[15px] leading-8 text-slate-500">
              {t('landing.hero.subtitle')}
            </p>

            <div className="mt-8 flex flex-col gap-3 sm:flex-row">
              <Link to="/create">
                <Button className="h-11 w-full rounded-lg bg-indigo-500 px-5 text-[13px] font-semibold text-white shadow-sm shadow-indigo-200 hover:bg-indigo-600 sm:w-auto">
                  {t('landing.hero.primary')}
                  <ArrowRight className="h-4 w-4" />
                </Button>
              </Link>
              <Link
                to="/dashboard"
                className="inline-flex h-11 items-center justify-center gap-2 rounded-lg border border-slate-200 bg-white px-5 text-[13px] font-semibold text-slate-700 shadow-sm transition-colors hover:bg-slate-50"
              >
                <CirclePlay className="h-4 w-4 text-emerald-600" />
                {t('landing.hero.secondary')}
              </Link>
            </div>

            <div className="mt-8 grid max-w-[560px] grid-cols-3 gap-3">
              {[
                [t('landing.metric.sources.value'), t('landing.metric.sources.label')],
                [t('landing.metric.cue.value'), t('landing.metric.cue.label')],
                [t('landing.metric.loop.value'), t('landing.metric.loop.label')],
              ].map(([value, label]) => (
                <div key={label} className="rounded-xl border border-slate-200 bg-white p-4 shadow-sm">
                  <div className="text-[22px] font-bold leading-none text-slate-900">{value}</div>
                  <div className="mt-2 text-[11px] text-slate-500">{label}</div>
                </div>
              ))}
            </div>
          </div>

          <ProductPreview />
        </div>
      </section>

      <section id="workflow" className="space-y-8">
        <SectionHeading
          eyebrow={t('landing.workflow.eyebrow')}
          title={t('landing.workflow.title')}
          description={t('landing.workflow.description')}
        />

        <div className="grid gap-4 lg:grid-cols-2">
          {sources.map((source) => (
            <div key={source.title} className="rounded-xl border border-slate-200 bg-white p-5 shadow-sm">
              <div className="flex items-start justify-between gap-4">
                <div className="min-w-0">
                  <div
                    className={cn(
                      'mb-4 flex h-11 w-11 items-center justify-center rounded-xl',
                      source.tone === 'indigo' ? 'bg-indigo-50 text-indigo-600' : 'bg-violet-50 text-violet-600',
                    )}
                  >
                    <source.icon className="h-5 w-5" />
                  </div>
                  <h3 className="text-[18px] font-bold text-slate-900">{source.title}</h3>
                  <p className="mt-1.5 text-[13px] leading-6 text-slate-500">{source.description}</p>
                </div>
                <span className="rounded-full bg-slate-100 px-2.5 py-1 text-[10px] font-bold text-slate-500">
                  {source.label}
                </span>
              </div>

              <div className="mt-5 grid gap-2">
                {source.steps.map((step, index) => (
                  <div key={step} className="flex items-center gap-3 rounded-lg border border-slate-100 bg-slate-50 px-3 py-3">
                    <span
                      className={cn(
                        'flex h-6 w-6 shrink-0 items-center justify-center rounded-full text-[11px] font-bold text-white',
                        source.tone === 'indigo' ? 'bg-indigo-500' : 'bg-violet-500',
                      )}
                    >
                      {index + 1}
                    </span>
                    <span className="text-[13px] font-medium text-slate-600">{step}</span>
                  </div>
                ))}
              </div>
            </div>
          ))}
        </div>
      </section>

      <section id="cue" className="grid gap-8 lg:grid-cols-[0.78fr_1.22fr]">
        <SectionHeading
          eyebrow={t('landing.cue.eyebrow')}
          title={t('landing.cue.title')}
          description={t('landing.cue.description')}
        />

        <div className="min-w-0 rounded-xl border border-slate-200 bg-white p-5 shadow-sm">
          <div className="grid gap-2 sm:grid-cols-3">
            {cueOptions.map((option, index) => (
              <button
                key={option.cueKey}
                type="button"
                onClick={() => setActiveCue(index)}
                onMouseEnter={() => setActiveCue(index)}
                className={cn(
                  'rounded-lg border px-3 py-3 text-left transition-colors',
                  activeCue === index
                    ? 'border-indigo-200 bg-indigo-50 text-indigo-700'
                    : 'border-slate-200 bg-white text-slate-500 hover:bg-slate-50',
                )}
              >
                <div className="font-mono text-[11px] text-orange-600">[{t(option.cueKey)}]</div>
                <div className="mt-2 text-[12px] font-semibold">{t(option.toneKey)}</div>
              </button>
            ))}
          </div>

          <div className="mt-5 rounded-xl border border-slate-200 bg-slate-50 p-5">
            <div className="rounded-lg border border-slate-200 bg-white px-4 py-3 font-mono text-[13px] leading-7 text-slate-700">
              <span className="rounded-md bg-orange-50 px-1.5 py-0.5 font-semibold text-orange-600">
                [{t(cue.cueKey)}]
              </span>
              <span className="ml-2">{t(cue.textKey)}</span>
            </div>
            <div className="mt-5 flex items-end gap-1.5">
              {Array.from({ length: 26 }).map((_, index) => (
                <span
                  key={index}
                  className="landing-wave-bar block w-1.5 rounded-full bg-indigo-500"
                  style={{
                    height: `${10 + ((index * 17 + activeCue * 11) % 34)}px`,
                    animationDelay: `${index * 38}ms`,
                  }}
                />
              ))}
            </div>
            <div className="mt-5 grid grid-cols-3 gap-3">
              <Metric label={t('landing.cue.metricTone')} value={t(cue.toneKey)} />
              <Metric label={t('landing.cue.metricSpeed')} value={cue.speed} />
              <Metric label={t('landing.cue.metricOutput')} value={t('common.ready')} />
            </div>
          </div>
        </div>
      </section>

      <section id="demo" className="space-y-8">
        <SectionHeading
          eyebrow={t('landing.demo.eyebrow')}
          title={t('landing.demo.title')}
          description={t('landing.demo.description')}
        />

        <div className="grid gap-4 lg:grid-cols-3">
          {[
            [Wand2, t('landing.demo.script.title'), t('landing.demo.script.description')],
            [RefreshCcw, t('landing.demo.revise.title'), t('landing.demo.revise.description')],
            [Headphones, t('landing.demo.listen.title'), t('landing.demo.listen.description')],
          ].map(([Icon, title, description], index) => (
            <div key={String(title)} className="landing-demo-tile rounded-xl border border-slate-200 bg-white p-5 shadow-sm">
              <div className="flex items-center justify-between">
                <div className="flex h-10 w-10 items-center justify-center rounded-xl bg-indigo-50 text-indigo-600">
                  <Icon className="h-5 w-5" />
                </div>
                <span className="font-mono text-[11px] text-slate-400">0{index + 1}</span>
              </div>
              <h3 className="mt-5 text-[16px] font-bold text-slate-900">{String(title)}</h3>
              <p className="mt-2 min-h-[44px] text-[13px] leading-6 text-slate-500">{String(description)}</p>
              <MiniDemo index={index} />
            </div>
          ))}
        </div>
      </section>
    </div>
  );
}

function ProductPreview() {
  const { t } = useI18n();

  return (
    <div className="landing-console min-w-0 rounded-2xl border border-slate-200 bg-white p-4 shadow-sm">
      <div className="flex items-center justify-between border-b border-slate-100 pb-3">
        <div className="flex items-center gap-2">
          <div className="flex h-8 w-8 items-center justify-center rounded-lg bg-indigo-50 text-indigo-600">
            <Sparkles className="h-4 w-4" />
          </div>
          <div>
            <div className="text-[13px] font-bold text-slate-800">{t('landing.preview.title')}</div>
            <div className="text-[11px] text-slate-400">{t('landing.preview.subtitle')}</div>
          </div>
        </div>
        <span className="inline-flex items-center gap-1 rounded-full border border-emerald-200 bg-emerald-50 px-2.5 py-1 text-[11px] font-semibold text-emerald-700">
          <CheckCircle2 className="h-3.5 w-3.5" />
          {t('common.ready')}
        </span>
      </div>

      <div className="grid gap-3 pt-4 lg:grid-cols-[0.82fr_1.18fr]">
        <div className="rounded-xl border border-slate-200 bg-slate-50 p-4">
          <div className="mb-3 flex items-center gap-2 text-[12px] font-bold text-slate-700">
            <Mic className="h-4 w-4 text-indigo-500" />
            {t('landing.preview.target')}
          </div>
          <div className="rounded-lg border border-slate-200 bg-white p-4 font-mono text-[12px] leading-6 text-slate-600">
            <div className="text-indigo-500">{t('landing.preview.promptLabel')}</div>
            <div className="landing-terminal-line mt-2">{t('landing.preview.prompt')}</div>
          </div>
          <div className="mt-3 grid grid-cols-3 gap-2">
            {[t('landing.preview.turns'), t('landing.preview.voices'), t('landing.preview.level')].map((item) => (
              <div key={item} className="rounded-lg border border-slate-200 bg-white px-2 py-2 text-center text-[11px] font-semibold text-slate-500">
                {item}
              </div>
            ))}
          </div>
        </div>

        <div className="rounded-xl border border-slate-200 bg-slate-50 p-4">
          <div className="mb-3 flex items-center justify-between gap-3">
            <div className="flex items-center gap-2 text-[12px] font-bold text-slate-700">
              <AudioLines className="h-4 w-4 text-indigo-500" />
              {t('landing.preview.scriptLabel')}
            </div>
            <span className="rounded-full bg-indigo-50 px-2 py-1 text-[10px] font-bold text-indigo-600">
              {t('landing.preview.reviseReady')}
            </span>
          </div>
          <div className="space-y-2 font-mono text-[12px] leading-6">
            <ScriptLine delay={0} cue={t('landing.preview.line1.cue')} text={t('landing.preview.line1.text')} />
            <ScriptLine delay={1} cue={t('landing.preview.line2.cue')} text={t('landing.preview.line2.text')} />
            <ScriptLine delay={2} cue={t('landing.preview.line3.cue')} text={t('landing.preview.line3.text')} />
          </div>
        </div>
      </div>

      <div className="mt-3 rounded-xl border border-slate-200 bg-white p-4">
        <div className="flex items-center justify-between gap-4">
          <div className="flex items-center gap-3">
            <button type="button" className="flex h-10 w-10 items-center justify-center rounded-full bg-indigo-500 text-white shadow-sm shadow-indigo-200" aria-label={t('common.play')}>
              <CirclePlay className="h-5 w-5" />
            </button>
            <div>
              <div className="text-[12px] font-bold text-slate-800">{t('landing.preview.listening')}</div>
              <div className="mt-1 font-mono text-[11px] text-slate-400">{t('landing.preview.playerMeta')}</div>
            </div>
          </div>
          <div className="hidden items-end gap-1 sm:flex">
            {Array.from({ length: 34 }).map((_, index) => (
              <span
                key={index}
                className="landing-wave-bar block w-1 rounded-full bg-indigo-400"
                style={{
                  height: `${8 + ((index * 11) % 30)}px`,
                  animationDelay: `${index * 32}ms`,
                }}
              />
            ))}
          </div>
        </div>
        <div className="mt-4 h-1.5 overflow-hidden rounded-full bg-slate-100">
          <div className="landing-progress h-full rounded-full bg-indigo-500" />
        </div>
      </div>
    </div>
  );
}

function SectionHeading({
  eyebrow,
  title,
  description,
}: {
  eyebrow: string;
  title: string;
  description: string;
}) {
  return (
    <div className="max-w-[760px]">
      <p className="text-[11px] font-bold uppercase tracking-wider text-indigo-500">{eyebrow}</p>
      <h2 className="mt-2 text-[28px] font-bold leading-[1.2] tracking-tight text-slate-950 sm:text-[34px]">
        {title}
      </h2>
      <p className="mt-4 text-[13px] leading-7 text-slate-500">{description}</p>
    </div>
  );
}

function ScriptLine({ cue, text, delay }: { cue: string; text: string; delay: number }) {
  return (
    <div
      className="landing-script-line rounded-lg border border-slate-200 bg-white px-3 py-2"
      style={{ animationDelay: `${delay * 420}ms` }}
    >
      <span className="rounded-md bg-orange-50 px-1.5 py-0.5 font-semibold text-orange-600">[{cue}]</span>
      <span className="ml-2 text-slate-600">{text}</span>
    </div>
  );
}

function Metric({ label, value }: { label: string; value: string }) {
  return (
    <div className="rounded-lg border border-slate-200 bg-white px-3 py-3">
      <div className="text-[10px] font-bold uppercase tracking-wider text-slate-400">{label}</div>
      <div className="mt-1 text-[12px] font-bold text-slate-700">{value}</div>
    </div>
  );
}

function MiniDemo({ index }: { index: number }) {
  const { t } = useI18n();

  if (index === 0) {
    return (
      <div className="mt-5 rounded-xl border border-slate-200 bg-slate-50 p-3 font-mono text-[11px] leading-6">
        <div className="landing-mini-line text-orange-600">[{t('landing.preview.line1.cue')}]</div>
        <div className="landing-mini-line text-slate-600" style={{ animationDelay: '220ms' }}>
          {t('landing.preview.line1.text')}
        </div>
        <div className="landing-mini-line text-indigo-600" style={{ animationDelay: '440ms' }}>
          [{t('landing.preview.line2.cue')}]
        </div>
      </div>
    );
  }

  if (index === 1) {
    return (
      <div className="mt-5 space-y-2 rounded-xl border border-slate-200 bg-slate-50 p-3">
        <div className="flex items-center justify-between rounded-lg bg-white px-3 py-2">
          <span className="text-[11px] text-slate-400">{t('common.original')}</span>
          <span className="text-[12px] font-bold text-amber-600">72</span>
        </div>
        <div className="flex items-center justify-between rounded-lg bg-emerald-50 px-3 py-2">
          <span className="text-[11px] text-emerald-700">{t('common.revise')}</span>
          <span className="text-[12px] font-bold text-emerald-600">91</span>
        </div>
        <div className="flex gap-1.5">
          {['tone', 'clarity', 'natural'].map((tag) => (
            <span key={tag} className="landing-tag rounded-full bg-orange-50 px-2 py-1 text-[10px] font-bold text-orange-600">
              {tag}
            </span>
          ))}
        </div>
      </div>
    );
  }

  return (
    <div className="mt-5 rounded-xl border border-slate-200 bg-slate-50 p-3">
      <div className="flex items-center gap-2">
        <CirclePlay className="h-5 w-5 text-indigo-500" />
        <div className="h-1.5 flex-1 overflow-hidden rounded-full bg-slate-200">
          <div className="landing-progress h-full rounded-full bg-indigo-500" />
        </div>
        <span className="font-mono text-[10px] text-slate-400">0.9x</span>
      </div>
      <div className="mt-4 rounded-lg border border-indigo-100 bg-indigo-50 px-3 py-2 text-[11px] leading-5 text-slate-600">
        {t('landing.preview.line1.text')}
      </div>
    </div>
  );
}
