import { Card, CardContent } from '@/components/ui/card';

const glossaryItems = [
  {
    term: 'TSS',
    points: [
      'Proxy for general aerobic fitness load.',
      '`TSS = duration_h × IF^2 × 100 × specificity_factor`.',
      'Useful for tracking broader training stress across sessions.',
      'Temperance applies the specificity factor so x-train load can be adjusted before contributing to TSS.',
    ],
  },
  {
    term: 'rTSS',
    points: [
      'More running-specific proxy for mechanical load.',
      '`rTSS = duration_h × rIF^2 × 100`.',
      'Does not accumulate the same way with x-train sessions.',
      'Use caution with high rTSS, because it can signal heavier mechanical stress.',
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
      'TSS tolerance depends on the athlete: elite runners can usually absorb more total TSS than newer athletes.',
      'A weekly target should match your current training level, not the load of a much fitter athlete.',
      'Build TSS gradually toward the target so fitness can rise without drifting into unnecessary overreach.',
      'Be especially careful with weekly jumps in rTSS, because mechanical load tends to matter more for injury risk.',
      'If you want to progress safely, increase load progressively rather than stacking large TSS or rTSS jumps in a single week.',
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
            <div className="grid gap-3 md:grid-cols-2">
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
    </section>
  );
}
