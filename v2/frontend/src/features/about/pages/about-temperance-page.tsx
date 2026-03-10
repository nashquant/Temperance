import { useState } from 'react';
import { ChevronDown } from 'lucide-react';

import { Card, CardContent } from '@/components/ui/card';
import { cn } from '@/lib/utils';

type AboutBlock = {
  id: string;
  title: string;
  summary: string;
  body: string[];
};

const aboutBlocks: AboutBlock[] = [
  {
    id: 'The Philosophy',
    title: 'The Philosophy',
    summary: 'Temperance means balance, restraint, and good judgment',
    body: [
      'Built for runners who also use cross-training, it helps make training load more coherent and easier to interpret.',
      
      'Adaptation requires sufficient load, but injury risk rises when mechanical stress outpaces tissue capacity. For endurance athletes, the real problem is not maximizing training load, but regulating it intelligently.',
      
      'Most training systems measure load through physiological signals such as heart rate, pace, power, or perceived exertion, capturing the aerobic stimulus of training. But runners are constrained by more than metabolism alone. They are also limited by mechanical tolerance - the capacity of bones, tendons, muscles, and connective tissue to absorb and adapt to stress on a slower and often less forgiving timeline.',
      
      'By measuring intensity relative to your personal thresholds, Temperance gives context to the work you do. And by separating total stress from running-specific stress, it recognizes a simple truth: not all load is created equal.',
      
      'The result is a clearer view of training - one that helps you push adaptation while staying in control of durability.',
    ],
  },
  {
    id: 'The Model',
    title: 'The Model',
    summary: 'Temperance begins with your personal heart-rate and pace thresholds.',
    body: [
      'Those inputs need to be set correctly, because threshold is what gives effort meaning. Rather than reading sessions in absolute terms, the platform interprets them relative to your own physiology - the same principle that underpins modern threshold-based training models.',

      'Temperance does not prescribe your thresholds for you. Those need to come from your own testing methodology, judgment, or coaching context. The platform is built to interpret training once those inputs are set, not to replace the process of determining them. That said, Temperance can assist with pace-threshold estimation by analyzing roughly the last 200 days of activity and inferring your current VDOT-like fitness, which can serve as a useful hint for likely LT pace.',

      'From there, it derives the metrics that make training easier to understand. The two core ones are TSS and rTSS. TSS reflects overall aerobic stress, following the broader logic of TRIMP and threshold-based load models: how long you train matters, but how hard that work is relative to your threshold matters more.',

      'rTSS narrows the lens to running. Because it is anchored to pace relative to threshold pace, it captures the cost of run-specific work more directly than a generic load number. It is not a literal measure of tissue damage or mechanical force, but it is a useful proxy for how much running-specific demand you are accumulating - and therefore a useful complement when thinking about economy, durability, and injury risk.',

      'That distinction matters because running has a specificity that cross-training does not fully reproduce. Non-running sessions can add meaningful aerobic load, but they usually place less stress on the structures that make running possible: the legs, tendons, and connective tissues that absorb impact and repetition. Temperance keeps those worlds connected, but not confused.',

      'Because threshold reflects your current performance level, it also gives a rough sense of training capacity. In broad terms, more developed athletes are often able to tolerate and benefit from higher loads than less adapted athletes. Temperance uses the thresholds you provide to contextualize stress targets accordingly - not as a guarantee of safety, but as a way to anchor load expectations to the athlete current level.',

      'That distinction matters because tolerance is not only aerobic. Running load is constrained by mechanical durability as well, and injury risk rises when loading outpaces tissue capacity or progresses too aggressively. Temperance is designed to make that balance easier to see, so higher targets are treated as context-sensitive rather than universally safe.',

      'For cross-training, Temperance also accepts a specificity factor. This scales down the running-equivalent contribution of non-running activities to reflect a simple principle: an activity may produce meaningful aerobic stress without reproducing the same running-specific mechanical and neuromuscular stimulus. In that sense, cross-training still counts for fitness, but not as a one-for-one substitute for running.',

      'Temperance also helps translate cross-training into the language runners still care about most: weekly mileage. When heart-rate zones and specificity are set correctly, it can derive a proxy distance and proxy pace for non-running sessions, so their contribution can be integrated into weekly proxy mileage.',

      'That estimate comes from creating parity between scaled TSS - adjusted by specificity - and rTSS. The result is a running-equivalent view of cross-training load: not a claim of perfect equivalence, but a practical way to reflect how non-running work contributes to the training week.',

      'Another side of Temperance is that it looks forward, not just back. By projecting weekly TSS and rTSS, it helps you plan load before it becomes a problem, rather than only recognizing overreaching after the fact. It also brings together raw and derived metrics - such as acute load, chronic load, fatigue, and fitness - and contrasts them with Garmin wellness signals to give training context beyond the session itself.',

      'While Temperance is built with Garmin users in mind, it remains flexible by design. Custom activities can still be added, and the platform will do its best to account for their contribution in a way that remains consistent with the rest of your training.',
    ],
  },
  {
    id: 'The Workflow',
    title: 'The Workflow',
    summary: 'Understand what each Temperance tab does.',
    body: [
      'Dashboard: a single place to plan activities, review weekly totals, add custom sessions, and read the main aggregates at a glance.',

      'Weekly Planner: is where planning becomes more precise. It is built for shaping the week ahead, adjusting details at session level, and making bulk changes when the structure of the week needs to move. Activity inputs follow a compact string-based syntax, documented separately.',

      'Athlete Progression and Wellness: is the analytical layer, where long-term progression, load, fatigue, fitness, and recovery can be tracked more closely and contrasted with wellness signals.',

      'Data Extract: is where Garmin sync and custom activity ingestion are managed, including bulk entry when needed, so the data behind the platform stays complete and usable.',

      'User Settings: Is the foundation. Thresholds, zones, and specificity factors need to be configured correctly - otherwise Temperance cannot produce meaningful output.',
      
    ],
  },
  {
    id: 'The Syntax',
    title: 'The Syntax',
    summary: 'Codify activities effectively in Temperance.',
    body: [
      'Planned and custom activities follow the same compact string syntax. It is designed to stay quick to type while giving Temperance enough structure to estimate duration, intensity, TSS, rTSS, and running-equivalent load.',

      'Each entry follows a simple pattern: date, then activity. Multiple entries can be separated by a new line, semicolon, or comma. Supported date formats include absolute dates such as `2026-03-26`, compact forms such as`3Mar26`, and relative forms such as `T`, `T+2`, or `T-1`.',

      'Activity types include running and treadmill, as well as cross-training modes such as elliptical, bike, and cycling. Every segment requires an intensity token. Temperance accepts heart rate inputs such as `@140bpm`, intensity factor inputs such as `@70%`, pace inputs such as `@4:50/km` for running-like sessions, and explicit load targets such as `@70TSS`. If no activity type is specified, Temperance assumes the session is a run.',

      'Duration can be expressed as either time or distance. Examples include `90min`, `1h`,`45s`, `10km`, or `400m`. Distance-only entries require the running or treadmill token together with pace or intensity, since the parser needs enough context to infer time and load.',

      'Segments can be chained with `+`, making it possible to describe a session in the order it happens, such as`10min run @4:50/km + 5x6min @3:40/km + 2min easy + 10min cooldown`. Interval blocks can also be written in repeated time or distance form, such as `5x6min @3:40/km`, `10x400m @3:35/km`, or`6x1km @3:45/km`.',

      'The practical rule is simple: use pace for running, and use heart rate or `%IF` for non-running work. When that structure is followed, Temperance can interpret planned and custom sessions consistently and fold them into the same weekly load model.',
    ],
  },
];

export function AboutTemperancePage(): JSX.Element {
  const surfaceClassName =
    'overflow-hidden rounded-2xl border-border/70 bg-[radial-gradient(circle_at_top,rgba(56,189,248,0.12),transparent_42%),linear-gradient(180deg,rgba(15,23,42,0.92),rgba(2,6,23,0.96))] shadow-[0_18px_40px_rgba(2,6,23,0.32)]';
  const [openSections, setOpenSections] = useState<Set<string>>(new Set(['overview']));

  const toggleSection = (sectionId: string) => {
    setOpenSections((current) => {
      const next = new Set(current);
      if (next.has(sectionId)) next.delete(sectionId);
      else next.add(sectionId);
      return next;
    });
  };

  return (
    <section className="space-y-6">

      <Card className={surfaceClassName}>
        <CardContent className="p-0">
          <div className="divide-y divide-white/8">
            {aboutBlocks.map((block, index) => {
              const isOpen = openSections.has(block.id);

              return (
                <div key={block.id} className="px-4 sm:px-5">
                  <button
                    type="button"
                    className="flex w-full items-start gap-4 py-4 text-left transition-colors hover:text-slate-50"
                    onClick={() => toggleSection(block.id)}
                    aria-expanded={isOpen}
                  >
                    <div className="flex min-w-9 items-center justify-center pt-0.5">
                      <span className="text-[11px] font-semibold uppercase tracking-[0.14em] text-sky-200/72">
                        {String(index + 1).padStart(2, '0')}
                      </span>
                    </div>

                    <div className="min-w-0 flex-1">
                      <div className="flex items-start justify-between gap-3">
                        <div className="min-w-0">
                          <p className="text-sm font-semibold text-slate-50">{block.title}</p>
                          <p className="mt-1 text-sm leading-6 text-slate-400/80">{block.summary}</p>
                        </div>

                        <div
                          className={cn(
                            'mt-0.5 flex h-8 w-8 shrink-0 items-center justify-center rounded-full border border-white/10 bg-white/[0.03] text-slate-300/78 transition-all duration-200',
                            isOpen ? 'rotate-180 bg-white/[0.06]' : '',
                          )}
                        >
                          <ChevronDown className="h-4 w-4" />
                        </div>
                      </div>
                    </div>
                  </button>

                  {isOpen ? (
                    <div className="pb-4 pl-[3.25rem] sm:pl-[3.5rem]">
                      <div className="rounded-2xl border border-white/8 bg-black/15 px-4 py-3">
                        <div className="space-y-3 text-sm leading-7 text-slate-300/78">
                          {block.body.map((paragraph) => (
                            <p key={paragraph}>{paragraph}</p>
                          ))}
                        </div>
                      </div>
                    </div>
                  ) : null}
                </div>
              );
            })}
          </div>
        </CardContent>
      </Card>
    </section>
  );
}
