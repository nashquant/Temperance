import { Card, CardContent } from '@/components/ui/card';

const glossaryItems = [
  {
    term: 'TSS',
    points: [
      'Estimate of overall training load, not a direct measure of fitness.',
      '`TSS = duration_h × IF^2 × 100 × specificity_factor`.',
      'Useful for tracking internal aerobic and metabolic stress across sessions.',
      'Temperance applies the specificity factor so cross-training can still contribute, but usually with less running-specific credit.',
    ],
  },
  {
    term: 'rTSS',
    points: [
      'More running-specific estimate of load, using running intensity and duration.',
      '`rTSS = duration_h × rIF^2 × 100`.',
      'Usually maps better to running-specific mechanical stress than generic TSS.',
      'Use caution with sharp rTSS jumps, because tissues often fail from sudden running spikes before aerobic fitness has time to catch up.',
    ],
  },
  {
    term: 'VDOT',
    points: [
      'Daniels running-performance score, often described as an effective VO2 max for pacing and race equivalence.',
      'It reflects race performance, running economy, and how much of your aerobic capacity you can actually use.',
      'Two runners can share a similar VO2 max but have different VDOT values if their economy or threshold durability differs.',
    ],
  },
  {
    term: 'VO2 max',
    points: [
      'Maximum rate at which you can take in, transport, and use oxygen during hard exercise.',
      'Important for endurance potential, but not the full story for running performance.',
      'Threshold, economy, durability, and pacing still matter, which is why VO2 max and VDOT should not be treated as interchangeable.',
    ],
  },
  {
    term: 'Fitness',
    points: [
      'Longer-term view of accumulated training load.',
      'Moves more slowly and helps show the base you have built.',
    ],
  },
  {
    term: 'Fatigue',
    points: [
      'Shorter-term view of recent training load.',
      'Moves faster and helps explain how loaded or tired you are right now.',
    ],
  },
];

const faqItems = [
  {
    question: 'What is the difference between planned, custom, and actual activities?',
    points: [
      'Planned activities come from workout-planning strings.',
      'Custom activities are manual entries you add yourself.',
      'Actual activities are imported records such as Garmin workouts.',
    ],
  },
  {
    question: 'Why do Garmin credentials sometimes need to be entered again?',
    points: [
      'Owner-scoped Garmin credentials are kept in backend memory only.',
      'They are intentionally not persisted to the database.',
      'You may need to enter them again after a restart or owner switch.',
    ],
  },
  {
    question: 'Any tips for planning activities from Week Planner or Dashboard?',
    points: [
      'Use Week Planner for week-level review and inline editing.',
      'Use the Dashboard `+` button for quick day-specific additions.',
      'Keep the date at the front of the workout string.',
      'Start with simple pace, HR, or IF notation and refine after saving.',
    ],
  },
  {
    question: 'How should I write workout strings?',
    points: [
      'Start with the date, then write the workout in the order it happens.',
      'Think in segments: warm-up, reps, recoveries, steady blocks, and cooldown all help the parser build cleaner splits.',
      'Use concise structures such as `2026-03-26: 10min run @4:50 + 5x6min @3:40/km + 2min easy + 10min cooldown`.',
      'Simple aerobic entries are also fine, for example `3Mar26: 80min elliptical @140bpm`.',
      'If recoveries matter, write them explicitly instead of implying them, for example `6x30s @3:00/km / 30s easy`.',
      'Temperance parses the string segment by segment, so better detail usually means better splits, TSS, rTSS, pace, and duration estimates.',
      'In Week Planner, you can bulk upload multiple activities at once by separating entries with new lines, commas, or semicolons.',
      'In Dashboard, the `+` flow is already tied to the selected day, so you do not need to pass the date, but you also cannot use it to plan for a different date.',
    ],
  },
  {
    question: 'What do specificity factors do?',
    points: [
      'They adjust how much training load to credit for less specific activities.',
      'They are especially useful for cross-training sessions.',
      'They help keep mixed training more comparable to your target discipline, which in Temperance is running.',
    ],
  },
  {
    question: 'How important is it to set LTHR and LT Pace curves correctly?',
    points: [
      'Very important, because these curves anchor how Temperance interprets intensity.',
      'If they are set too high or too low, zones, IF, TSS, rTSS, and split interpretation can all drift.',
      'Keep them updated when your fitness changes, especially after meaningful improvements or detraining.',
      'If the charts or workout estimates start to feel off, this is one of the first settings to review.',
    ],
  },
  {
    question: 'How should I think about TSS and rTSS progression?',
    points: [
      'TSS helps describe total training load, while rTSS is the more useful warning sign when running-specific stress rises too fast.',
      'A bigger TSS week is not automatically better: load only works when you can absorb it and recover from it.',
      'Build both metrics from your own recent baseline, not from the numbers of a fitter athlete.',
      'Short blocks of heavy training can be productive if recovery is planned, but repeated high-load weeks without recovery can turn functional overreach into non-functional overreach.',
      'For injury risk, watch sudden spikes in running load even more than the headline weekly total. Recent running data suggests a single run that is more than about 10% longer than your longest run in the prior 30 days already raises overuse-injury risk.',
      'If TSS is rising mostly from cross-training while rTSS stays stable, you may be building aerobic support with less musculoskeletal cost. If rTSS is rising aggressively, be more conservative.',
    ],
  },
  {
    question: 'What is overreach, and when is it a problem?',
    points: [
      'Functional overreaching is a short-term drop in freshness or performance that can be useful if followed by enough recovery.',
      'Non-functional overreaching is when the load-recovery balance stays off for too long and performance keeps drifting down instead of rebounding.',
      'Warning signs are not just tired legs: watch for unusual irritability, poor sleep, flat sessions, lingering soreness, illness, or paces that feel much harder than normal.',
      'Temperance can help you spot the pattern, but no single metric diagnoses overtraining. Use the charts together with how you are actually responding.',
    ],
  },
  {
    question: 'How should I think about VDOT and VO2 max?',
    points: [
      'VO2 max is your aerobic ceiling. VDOT is a practical running-performance model that also reflects economy and sustainable race execution.',
      'That means VDOT is often more useful for setting training paces, while VO2 max is more useful for understanding aerobic potential.',
      'Do not chase VO2 max workouts year-round. They are effective, but they are also some of the most demanding sessions you can do and should sit on top of a stable aerobic base.',
      'If your VDOT rises while VO2 max barely changes, that can still be real progress because threshold pace, economy, and durability often improve first.',
    ],
  },
];

export function FaqPage(): JSX.Element {
  const surfaceClassName =
    'overflow-hidden rounded-2xl border-border/70 bg-[radial-gradient(circle_at_top,rgba(56,189,248,0.12),transparent_42%),linear-gradient(180deg,rgba(15,23,42,0.92),rgba(2,6,23,0.96))] shadow-[0_18px_40px_rgba(2,6,23,0.32)]';

  return (
    <section className="space-y-6">
      <div>
        <h1 className="text-2xl font-semibold tracking-tight">FAQ</h1>
        <p className="mt-1 text-sm text-muted-foreground">Quick answers to the main Temperance workflows and behaviors.</p>
      </div>

      <Card className={surfaceClassName}>
        <CardContent className="space-y-2 p-4">
          <p className="text-sm font-semibold text-foreground">What Temperance Means</p>
          <p className="text-sm leading-6 text-slate-300/72">
            Temperance is about balance, discipline, and measured progression. In the app, that means building training load with intent,
            respecting recovery, and using planning plus analytics to support sustainable running development rather than chasing stress for
            its own sake.
          </p>
        </CardContent>
      </Card>

      <div className="space-y-3">
        <Card className={surfaceClassName}>
          <CardContent className="space-y-3 p-4">
            <p className="text-sm font-semibold text-foreground">Core Metrics</p>
            <div className="grid gap-2 md:hidden">
              {glossaryItems.map((item) => (
                <div key={item.term} className="rounded-xl border border-white/8 bg-white/[0.03] px-3 py-2.5">
                  <p className="text-[11px] font-semibold uppercase tracking-[0.16em] text-sky-200/74">{item.term}</p>
                  <ul className="mt-1.5 space-y-1 text-sm leading-6 text-slate-300/72">
                    {item.points.map((point) => (
                      <li key={point}>- {point}</li>
                    ))}
                  </ul>
                </div>
              ))}
            </div>
            <div className="hidden gap-3 md:grid md:grid-cols-2">
              {glossaryItems.map((item) => (
                <div key={item.term} className="rounded-xl border border-white/10 bg-black/15 p-3">
                  <p className="text-sm font-semibold text-foreground">{item.term}</p>
                  <ul className="mt-2 space-y-1 text-sm leading-6 text-slate-300/72">
                    {item.points.map((point) => (
                      <li key={point}>- {point}</li>
                    ))}
                  </ul>
                </div>
              ))}
            </div>
          </CardContent>
        </Card>

        <Card className={`${surfaceClassName} md:hidden`}>
          <CardContent className="grid gap-2 p-4">
            {faqItems.map((item) => (
              <div key={item.question} className="rounded-xl border border-white/8 bg-white/[0.03] px-3 py-2.5">
                <p className="text-[11px] font-semibold uppercase tracking-[0.16em] text-sky-200/74">{item.question}</p>
                <ul className="mt-1.5 space-y-1 text-sm leading-6 text-slate-300/72">
                  {item.points.map((point) => (
                    <li key={point}>- {point}</li>
                  ))}
                </ul>
              </div>
            ))}
          </CardContent>
        </Card>

        <div className="hidden space-y-3 md:block">
          {faqItems.map((item) => (
            <Card key={item.question} className={surfaceClassName}>
              <CardContent className="space-y-2 p-4">
                <p className="text-sm font-semibold text-foreground">{item.question}</p>
                <ul className="space-y-1 text-sm leading-6 text-slate-300/72">
                  {item.points.map((point) => (
                    <li key={point}>- {point}</li>
                  ))}
                </ul>
              </CardContent>
            </Card>
          ))}
        </div>
      </div>
    </section>
  );
}
