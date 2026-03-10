import { Card, CardContent } from '@/components/ui/card';

const glossaryItems = [
  {
    term: 'TSS',
    summary: 'Overall training-load estimate.',
    formula: 'TSS = duration_h x IF^2 x 100 x specificity_factor',
    points: ['Best for total aerobic and metabolic load across mixed training.', 'Not a direct measure of fitness, durability, or injury risk.'],
  },
  {
    term: 'rTSS',
    summary: 'Running-specific load estimate.',
    formula: 'rTSS = duration_h x rIF^2 x 100',
    points: ['Usually the better signal for running-specific musculoskeletal cost.', 'Sharp jumps matter because tissues often fail before aerobic fitness does.'],
  },
  {
    term: 'VDOT',
    summary: 'Daniels running-performance score.',
    points: ['Useful for race equivalence and training paces.', 'Reflects performance, economy, and sustainable aerobic use, not just lab capacity.'],
  },
  {
    term: 'VO2 max',
    summary: 'Your aerobic ceiling.',
    points: ['Important for endurance potential, but not the whole performance story.', 'Threshold, economy, durability, and pacing still decide a lot on race day.'],
  },
  {
    term: 'Fitness',
    summary: 'Longer-term load trend.',
    points: ['Moves slowly and reflects the base you have built.'],
  },
  {
    term: 'Fatigue',
    summary: 'Shorter-term load trend.',
    points: ['Moves quickly and helps explain current tiredness or freshness.'],
  },
];

const workflowFaqItems = [
  {
    question: 'What is the difference between planned, custom, and actual activities?',
    points: [
      'Planned activities come from workout-planning strings.',
      'Custom activities are manual entries you add yourself.',
      'Actual activities are imported records such as Garmin workouts.',
    ],
  },
  {
    question: 'How should I write workout strings?',
    points: [
      'Start with the date, then write the workout in the order it happens.',
      'Think in segments: warm-up, reps, recoveries, steady work, cooldown.',
      'Explicit recoveries produce better splits and better TSS, rTSS, pace, and duration estimates.',
      'Example: `2026-03-26: 10min run @4:50 + 5x6min @3:40/km + 2min easy + 10min cooldown`.',
    ],
  },
  {
    question: 'What do specificity factors do?',
    points: [
      'They adjust how much load to credit for less specific activities.',
      'This matters most for cross-training, where aerobic benefit may be real but running-specific transfer is smaller.',
      'In Temperance, they help total TSS stay useful without pretending every session stresses running equally.',
    ],
  },
  {
    question: 'How important is it to set LTHR and LT Pace curves correctly?',
    points: [
      'Very important. These curves anchor how Temperance interprets intensity.',
      'If they are wrong, zones, IF, TSS, rTSS, and split interpretation all drift.',
      'When workouts or charts stop matching reality, review these settings first.',
    ],
  },
];

const trainingFaqItems = [
  {
    question: 'How should I think about TSS and rTSS progression?',
    points: [
      'TSS helps describe total training load, while rTSS is the more useful warning sign when running-specific stress rises too fast.',
      'A bigger TSS week is not automatically better: load only works when you can absorb it and recover from it.',
      'Build both metrics from your own recent baseline, not from the numbers of a fitter athlete.',
      'For injury risk, watch sudden running spikes even more than the weekly headline total. If TSS rises mostly from cross-training while rTSS stays stable, that is usually easier to absorb than the same rise coming from pure running.',
    ],
  },
  {
    question: 'What is a reasonable weekly TSS for different kinds of runners?',
    points: [
      'There is no universal correct number, but for running-focused weeks these rough bands are a useful starting point: hobby jogger about 150-300 TSS, amateur or recreational racer about 250-450, sub-elite about 400-700, and elite about 650-1000+ in peak blocks.',
      'Treat those as approximate peak-week bands, not year-round averages or requirements.',
      'The difference is not just fitness. Better-trained runners usually have more training history, more frequency, better economy, and more tissue tolerance, so they can absorb more running-specific work.',
      'The same headline TSS can also come from very different weeks. A 500-TSS week built mostly from running is usually harder on the legs than a 500-TSS week with substantial cycling, elliptical, or pool work.',
    ],
  },
  {
    question: 'Does the right TSS goal change with training approach?',
    points: [
      'Yes. A high-volume aerobic or pyramidal block usually spreads stress across more low-intensity running, so weekly TSS can be fairly high without every session feeling extreme.',
      'A polarized, threshold-heavy, or race-specific block may keep similar total TSS but concentrate more stress into fewer hard sessions, so recovery demand rises faster than the weekly total suggests.',
      'If your approach uses more cross-training, total TSS may stay high while rTSS stays moderate. That is often a good trade when the aerobic system can handle more work but the legs cannot.',
      'Use TSS as the budget, rTSS as the running-specific cost, and your actual response as the final check.',
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
      'They can look closer in well-trained runners whose economy and threshold durability are close to the assumptions in Daniels-style race modeling. In that case, race performance is expressing a large fraction of the aerobic engine you already have.',
      'They do not reliably converge for every athlete. A runner with strong lab VO2 max but weak economy or poor durability can have a lower VDOT than expected, while an economical, durable runner can perform above what raw VO2 max alone would predict.',
      'So the useful question is not whether they match perfectly. It is whether your race-derived VDOT is converting your aerobic capacity into running speed well. If not, economy, threshold, fueling, or event-specific endurance may be the limiter rather than VO2 max itself.',
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

      <div className="space-y-6">
        <Card className={surfaceClassName}>
          <CardContent className="space-y-3 p-4">
            <div className="flex items-center justify-between gap-3">
              <div>
                <p className="text-sm font-semibold text-foreground">Core Metrics</p>
                <p className="text-xs text-slate-400/80">The few terms that matter most when you read the charts.</p>
              </div>
            </div>
            <div className="grid gap-2 md:hidden">
              {glossaryItems.map((item) => (
                <div key={item.term} className="rounded-xl border border-white/8 bg-white/[0.03] px-3 py-3">
                  <div className="flex items-baseline justify-between gap-3">
                    <p className="text-[11px] font-semibold uppercase tracking-[0.16em] text-sky-200/74">{item.term}</p>
                    <p className="text-[11px] text-slate-400/75">{item.summary}</p>
                  </div>
                  {item.formula ? (
                    <div className="mt-2 rounded-lg border border-sky-300/12 bg-slate-950/65 px-2.5 py-2 font-mono text-[11px] text-sky-100/88">
                      {item.formula}
                    </div>
                  ) : null}
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
                  <div className="flex items-baseline justify-between gap-3">
                    <p className="text-sm font-semibold text-foreground">{item.term}</p>
                    <p className="text-xs text-slate-400/80">{item.summary}</p>
                  </div>
                  {item.formula ? (
                    <div className="mt-2 rounded-lg border border-sky-300/12 bg-slate-950/65 px-3 py-2 font-mono text-xs text-sky-100/88">
                      {item.formula}
                    </div>
                  ) : null}
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

        {[
          { title: 'Using Temperance', subtitle: 'Workflow details that affect parsing and planning.', items: workflowFaqItems },
          { title: 'Training Load', subtitle: 'The practical stuff behind TSS, rTSS, overreach, and pacing models.', items: trainingFaqItems },
        ].map((section) => (
          <Card key={section.title} className={surfaceClassName}>
            <CardContent className="space-y-4 p-4">
              <div>
                <p className="text-sm font-semibold text-foreground">{section.title}</p>
                <p className="mt-1 text-xs text-slate-400/80">{section.subtitle}</p>
              </div>
              <div className="grid gap-3 md:grid-cols-2">
                {section.items.map((item) => (
                  <div key={item.question} className="rounded-xl border border-white/8 bg-white/[0.03] px-3 py-3">
                    <p className="text-[11px] font-semibold uppercase tracking-[0.16em] text-sky-200/74">{item.question}</p>
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
        ))}
      </div>
    </section>
  );
}
