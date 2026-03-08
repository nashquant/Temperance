import { useEffect, useMemo, useState } from "react";

const TOKEN_KEY = "temperance_v2_token";

function authHeaders(token) {
  if (!token) {
    return {};
  }
  return { Authorization: `Bearer ${token}` };
}

async function parseOrThrow(response) {
  const data = await response.json().catch(() => ({}));
  if (!response.ok) {
    const detail = data?.detail || `HTTP ${response.status}`;
    throw new Error(String(detail));
  }
  return data;
}

function compareLabel(compareKey) {
  return {
    planned: "Planned",
    previous_week: "Previous week",
    two_weeks_ago: "2 weeks ago",
    three_weeks_ago: "3 weeks ago",
    four_weeks_ago: "4 weeks ago",
  }[compareKey] || "Compare";
}

function metricLabel(metricKey) {
  return {
    tss: "TSS",
    rtss: "rTSS",
    distance_eqv_km: "Distance Eqv (km)",
  }[metricKey] || "Metric";
}

function isIntegerMetric(metricKey) {
  return metricKey === "tss" || metricKey === "rtss";
}

function formatMetricValue(value, metricKey) {
  const n = Number(value);
  if (!Number.isFinite(n)) {
    return "-";
  }
  if (isIntegerMetric(metricKey)) {
    return String(Math.round(n));
  }
  const rounded = Math.round(n * 10) / 10;
  return Number.isInteger(rounded) ? String(Math.trunc(rounded)) : rounded.toFixed(1);
}

function formatNumber(value, digits = 1) {
  const n = Number(value);
  if (!Number.isFinite(n)) {
    return "-";
  }
  if (digits <= 0) {
    return String(Math.round(n));
  }
  const factor = 10 ** digits;
  const rounded = Math.round(n * factor) / factor;
  return Number.isInteger(rounded) ? String(Math.trunc(rounded)) : rounded.toFixed(digits);
}

function WeekOutlookChart({ rows, metricKey, compareKey }) {
  if (!rows || rows.length === 0) {
    return <p>No chart data available.</p>;
  }

  const allValues = rows.flatMap((row) => [Number(row.current || 0), Number(row.compare || 0)]);
  const maxValue = Math.max(1, ...allValues);

  return (
    <div className="wk-chart">
      <div className="wk-grid">
        {rows.map((row) => {
          const cur = Number(row.current || 0);
          const comp = Number(row.compare || 0);
          const curPct = cur > 0 ? Math.max(2, (cur / maxValue) * 100) : 0;
          const compPct = comp > 0 ? Math.max(2, (comp / maxValue) * 100) : 0;
          const dayShort = String(row.day_label || "").split(" ").slice(-1)[0]?.replace(/[()]/g, "") || row.day_label;
          const currentBarClass = row.is_today ? "wk-bar wk-bar-current-today" : "wk-bar wk-bar-current";
          return (
            <div key={row.day} className="wk-col">
              <div className="wk-bars">
                <div className="wk-bar-wrap">
                  <div className="wk-bar-shell">
                    <div
                      className="wk-bar wk-bar-compare"
                      style={{ height: `${compPct}%` }}
                      title={`${compareLabel(compareKey)}: ${formatMetricValue(comp, metricKey)}`}
                    />
                  </div>
                  <span className="wk-bar-value">{comp > 0 ? formatMetricValue(comp, metricKey) : ""}</span>
                </div>
                <div className="wk-bar-wrap">
                  <div className="wk-bar-shell">
                    <div
                      className={currentBarClass}
                      style={{ height: `${curPct}%` }}
                      title={`Current: ${formatMetricValue(cur, metricKey)}`}
                    />
                  </div>
                  <span className="wk-bar-value">{cur > 0 ? formatMetricValue(cur, metricKey) : ""}</span>
                </div>
              </div>
              <div className="wk-day">{dayShort}</div>
            </div>
          );
        })}
      </div>
      <div className="wk-legend">
        <span><i className="wk-dot wk-dot-current" /> Current</span>
        <span><i className="wk-dot wk-dot-compare" /> {compareLabel(compareKey)}</span>
        <span>{metricLabel(metricKey)}</span>
      </div>
    </div>
  );
}

export default function App() {
  const [activeTab, setActiveTab] = useState("weekly_outlook");

  const [health, setHealth] = useState("loading");
  const [token, setToken] = useState(() => localStorage.getItem(TOKEN_KEY) || "");
  const [userCtx, setUserCtx] = useState(null);
  const [owners, setOwners] = useState([]);
  const [owner, setOwner] = useState("");

  const [days, setDays] = useState("84");
  const [sport, setSport] = useState("");
  const [startDay, setStartDay] = useState("");
  const [endDay, setEndDay] = useState("");
  const [weekMetric, setWeekMetric] = useState("tss");
  const [weekCompare, setWeekCompare] = useState("planned");
  const [weekStart, setWeekStart] = useState("");

  const [overview, setOverview] = useState(null);
  const [dashboard, setDashboard] = useState(null);
  const [weekly, setWeekly] = useState(null);
  const [weekOutlook, setWeekOutlook] = useState(null);
  const [selectedActivityId, setSelectedActivityId] = useState("");
  const [activityDetail, setActivityDetail] = useState(null);

  const [loginUser, setLoginUser] = useState("");
  const [loginPass, setLoginPass] = useState("");

  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");

  useEffect(() => {
    fetch("/health")
      .then((r) => parseOrThrow(r))
      .then((data) => setHealth(data.status || "unknown"))
      .catch(() => setHealth("error"));
  }, []);

  useEffect(() => {
    async function loadIdentity() {
      try {
        setError("");
        const me = await parseOrThrow(await fetch("/api/v1/auth/me", { headers: authHeaders(token) }));
        setUserCtx(me);
        const ownerData = await parseOrThrow(await fetch("/api/v1/auth/owners", { headers: authHeaders(token) }));
        const ownerOptions = ownerData.owners || [];
        setOwners(ownerOptions);
        setOwner((prev) => prev || me.owner || ownerOptions[0] || "");
      } catch (err) {
        if (!token) {
          setUserCtx(null);
          setOwners([]);
          setOwner("");
          return;
        }
        setUserCtx(null);
        setOwners([]);
        setOwner("");
        setDashboard(null);
        setWeekly(null);
        setWeekOutlook(null);
        setOverview(null);
        setSelectedActivityId("");
        setActivityDetail(null);
        setToken("");
        localStorage.removeItem(TOKEN_KEY);
        setError(err instanceof Error ? err.message : "Auth failed");
      }
    }

    loadIdentity();
  }, [token]);

  const canLoadData = useMemo(() => {
    if (!userCtx) {
      return false;
    }
    if (userCtx.role === "admin") {
      return !!owner;
    }
    return true;
  }, [owner, userCtx]);

  async function loadDashboard() {
    if (!canLoadData) {
      return;
    }

    try {
      setLoading(true);
      setError("");
      const qs = new URLSearchParams();
      qs.set("days", String(Number(days) || 84));
      qs.set("limit", "60");
      if (owner) {
        qs.set("owner", owner);
      }
      if (sport.trim()) {
        qs.set("sport", sport.trim());
      }
      if (startDay) {
        qs.set("start_day", startDay);
      }
      if (endDay) {
        qs.set("end_day", endDay);
      }

      const outlookQs = new URLSearchParams(qs.toString());
      outlookQs.set("metric", weekMetric);
      outlookQs.set("compare", weekCompare);
      if (weekStart) {
        outlookQs.set("week_start", weekStart);
      }

      const [overviewData, dashboardData, weeklyData, weekOutlookData] = await Promise.all([
        parseOrThrow(await fetch(`/api/v1/overview?owner=${encodeURIComponent(owner || "")}`, { headers: authHeaders(token) })),
        parseOrThrow(await fetch(`/api/v1/dashboard?${qs.toString()}`, { headers: authHeaders(token) })),
        parseOrThrow(await fetch(`/api/v1/weekly-summary?${qs.toString()}`, { headers: authHeaders(token) })),
        parseOrThrow(await fetch(`/api/v1/week-outlook?${outlookQs.toString()}`, { headers: authHeaders(token) })),
      ]);

      setOverview(overviewData);
      setDashboard(dashboardData);
      setWeekly(weeklyData);
      setWeekOutlook(weekOutlookData);
      if ((!weekStart || weekStart.trim() === "") && weekOutlookData?.week_start) {
        setWeekStart(String(weekOutlookData.week_start));
      }
      setSelectedActivityId("");
      setActivityDetail(null);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed loading data");
    } finally {
      setLoading(false);
    }
  }

  async function loadActivityDetail(activityId) {
    if (!activityId) {
      return;
    }
    try {
      setLoading(true);
      setError("");
      const qs = new URLSearchParams();
      if (owner) {
        qs.set("owner", owner);
      }
      qs.set("records_limit", "500");
      const detail = await parseOrThrow(
        await fetch(`/api/v1/activities/${encodeURIComponent(activityId)}?${qs.toString()}`, { headers: authHeaders(token) })
      );
      setSelectedActivityId(activityId);
      setActivityDetail(detail);
      setActiveTab("activities");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed loading activity detail");
    } finally {
      setLoading(false);
    }
  }

  async function submitLogin(event) {
    event.preventDefault();
    try {
      setLoading(true);
      setError("");
      const response = await fetch("/api/v1/auth/login", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ username: loginUser, password: loginPass }),
      });
      const data = await parseOrThrow(response);
      const newToken = String(data.token || "");
      if (!newToken) {
        throw new Error("Missing token in login response");
      }
      localStorage.setItem(TOKEN_KEY, newToken);
      setToken(newToken);
      setLoginPass("");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Login failed");
    } finally {
      setLoading(false);
    }
  }

  function logout() {
    localStorage.removeItem(TOKEN_KEY);
    setToken("");
    setUserCtx(null);
    setOwners([]);
    setOwner("");
    setOverview(null);
    setDashboard(null);
    setWeekly(null);
    setWeekOutlook(null);
    setSelectedActivityId("");
    setActivityDetail(null);
  }

  function shiftOutlookWeek(daysDelta) {
    const base = weekStart || weekOutlook?.week_start;
    if (!base) {
      return;
    }
    const parsed = new Date(`${base}T00:00:00`);
    if (Number.isNaN(parsed.getTime())) {
      return;
    }
    parsed.setDate(parsed.getDate() + daysDelta);
    const shifted = parsed.toISOString().slice(0, 10);
    setWeekStart(shifted);
    setTimeout(() => {
      loadDashboard();
    }, 0);
  }

  useEffect(() => {
    if (canLoadData) {
      loadDashboard();
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [canLoadData, owner]);

  useEffect(() => {
    if (canLoadData) {
      loadDashboard();
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [weekMetric, weekCompare, weekStart]);

  return (
    <main className="app-shell">
      <header className="header-row">
        <div>
          <h1>Temperance v2</h1>
          <p>Focus mode: Weekly Outlook parity from v1.</p>
        </div>
        <div className="status-pill">Backend health: {health}</div>
      </header>

      {!userCtx ? (
        <section className="card">
          <h2>Sign in</h2>
          <form className="form-grid" onSubmit={submitLogin}>
            <label>
              User
              <input value={loginUser} onChange={(e) => setLoginUser(e.target.value)} required />
            </label>
            <label>
              Password
              <input type="password" value={loginPass} onChange={(e) => setLoginPass(e.target.value)} required />
            </label>
            <button type="submit" disabled={loading}>
              {loading ? "Signing in..." : "Sign in"}
            </button>
          </form>
          {error ? <p className="error">{error}</p> : null}
        </section>
      ) : (
        <>
          <section className="card">
            <div className="row-between">
              <h2>Session & Filters</h2>
              <button onClick={logout}>Logout</button>
            </div>
            <p>
              Signed in as <strong>{userCtx.user}</strong> ({userCtx.role})
            </p>
            <form
              className="form-grid compact"
              onSubmit={(e) => {
                e.preventDefault();
                loadDashboard();
              }}
            >
              {userCtx.role === "admin" ? (
                <label>
                  Data owner
                  <select value={owner} onChange={(e) => setOwner(e.target.value)}>
                    {owners.map((opt) => (
                      <option value={opt} key={opt}>
                        {opt}
                      </option>
                    ))}
                  </select>
                </label>
              ) : null}
              <label>
                Days
                <input value={days} onChange={(e) => setDays(e.target.value)} />
              </label>
              <label>
                Sport filter
                <input placeholder="run, cycle, treadmill..." value={sport} onChange={(e) => setSport(e.target.value)} />
              </label>
              <label>
                Start day
                <input type="date" value={startDay} onChange={(e) => setStartDay(e.target.value)} />
              </label>
              <label>
                End day
                <input type="date" value={endDay} onChange={(e) => setEndDay(e.target.value)} />
              </label>
              <button type="submit" disabled={loading || !canLoadData}>
                {loading ? "Loading..." : "Apply filters"}
              </button>
            </form>
            {error ? <p className="error">{error}</p> : null}
          </section>

          <section className="tabs-row">
            <button className={activeTab === "weekly_outlook" ? "tab-btn active" : "tab-btn"} onClick={() => setActiveTab("weekly_outlook")}>Weekly Outlook</button>
            <button className={activeTab === "dashboard" ? "tab-btn active" : "tab-btn"} onClick={() => setActiveTab("dashboard")}>Dashboard</button>
            <button className={activeTab === "weekly_summary" ? "tab-btn active" : "tab-btn"} onClick={() => setActiveTab("weekly_summary")}>Weekly Summary</button>
            <button className={activeTab === "activities" ? "tab-btn active" : "tab-btn"} onClick={() => setActiveTab("activities")}>Activities</button>
          </section>

          {activeTab === "weekly_outlook" ? (
            <section className="card">
              {!weekOutlook ? (
                <p>Load data to see week outlook.</p>
              ) : (
                <>
                  <h2>Week Outlook</h2>
                  <h3 className="wk-range-title">
                    {new Date(`${weekOutlook.week_start}T00:00:00`).toLocaleDateString("en-US", {
                      month: "long",
                      day: "numeric",
                    })}{" "}
                    -{" "}
                    {new Date(`${weekOutlook.week_end}T00:00:00`).toLocaleDateString("en-US", {
                      day: "numeric",
                    })}
                  </h3>
                  <div className="wk-controls">
                    <button type="button" onClick={() => shiftOutlookWeek(-7)} disabled={loading}>◀</button>
                    <button type="button" onClick={() => shiftOutlookWeek(7)} disabled={loading}>▶</button>
                    <select value={weekCompare} onChange={(e) => setWeekCompare(e.target.value)}>
                      <option value="planned">Plan</option>
                      <option value="previous_week">Previous week</option>
                      <option value="two_weeks_ago">2 weeks ago</option>
                      <option value="three_weeks_ago">3 weeks ago</option>
                      <option value="four_weeks_ago">4 weeks ago</option>
                    </select>
                    <select value={weekMetric} onChange={(e) => setWeekMetric(e.target.value)}>
                      <option value="tss">TSS</option>
                      <option value="rtss">rTSS</option>
                      <option value="distance_eqv_km">Distance Eqv (km)</option>
                    </select>
                    <span className="wk-goal-pill">
                      {metricLabel(weekOutlook.metric)} - {Math.round(Number(weekOutlook.goal || 0))}
                    </span>
                  </div>
                  <div className="kpi-grid">
                    <div className="kpi-item"><span className="kpi-label">WTD (Current)</span><strong>{formatMetricValue(weekOutlook.wtd_current, weekOutlook.metric)}</strong></div>
                    <div className="kpi-item"><span className="kpi-label">WTD ({compareLabel(weekOutlook.compare)})</span><strong>{formatMetricValue(weekOutlook.wtd_compare, weekOutlook.metric)}</strong></div>
                    {weekOutlook.compare === "planned" ? (
                      <>
                        <div className="kpi-item"><span className="kpi-label">Remaining To Go</span><strong>{formatMetricValue(weekOutlook.remaining_to_go ?? 0, weekOutlook.metric)}</strong></div>
                        <div className="kpi-item"><span className="kpi-label">Projected Finish</span><strong>{formatMetricValue(weekOutlook.projected_finish, weekOutlook.metric)}</strong></div>
                        <div className="kpi-item"><span className="kpi-label">Estimated Fatigue EoW</span><strong>{formatNumber(weekOutlook.estimated_fatigue_eow, 1)}</strong></div>
                      </>
                    ) : (
                      <div className="kpi-item"><span className="kpi-label">{compareLabel(weekOutlook.compare)} Total</span><strong>{formatMetricValue(weekOutlook.week_total_compare, weekOutlook.metric)}</strong></div>
                    )}
                  </div>
                  <div className="goal-progress-track"><div className="goal-progress-fill" style={{ width: `${Math.max(0, Math.min(weekOutlook.goal_progress_pct, 200))}%` }} /></div>
                  <WeekOutlookChart rows={weekOutlook.rows} metricKey={weekOutlook.metric} compareKey={weekOutlook.compare} />
                </>
              )}
            </section>
          ) : null}

          {activeTab === "dashboard" ? (
            <section className="card">
              <h2>Dashboard</h2>
              {!dashboard ? (
                <p>Load data to see dashboard metrics.</p>
              ) : (
                <>
                  <div className="kpi-grid">
                    <div className="kpi-item"><span className="kpi-label">Distance</span><strong>{dashboard.kpis.distance_km} km</strong></div>
                    <div className="kpi-item"><span className="kpi-label">Proxy distance</span><strong>{dashboard.kpis.distance_proxy_km} km</strong></div>
                    <div className="kpi-item"><span className="kpi-label">Total TSS</span><strong>{dashboard.kpis.tss_total}</strong></div>
                    <div className="kpi-item"><span className="kpi-label">Activities</span><strong>{dashboard.kpis.activities}</strong></div>
                  </div>
                </>
              )}
            </section>
          ) : null}

          {activeTab === "weekly_summary" ? (
            <section className="card">
              <h2>Weekly Summary</h2>
              {!weekly ? (
                <p>Load data to see weekly summary.</p>
              ) : weekly.weeks.length === 0 ? (
                <p>No weekly rows available for this filter set.</p>
              ) : (
                <>
                  <p className="subtle">Weeks: {weekly.summary.weeks} | Activities: {weekly.summary.total_activities} | Distance: {weekly.summary.total_distance_km} km | TSS: {weekly.summary.total_tss}</p>
                  <table>
                    <thead>
                      <tr><th>Week start</th><th>Distance (km)</th><th>Proxy (km)</th><th>TSS</th><th>rTSS</th><th>Activities</th></tr>
                    </thead>
                    <tbody>
                      {weekly.weeks.map((row) => (
                        <tr key={row.week_start}><td>{row.week_start}</td><td>{row.distance_km}</td><td>{row.distance_proxy_km}</td><td>{row.tss}</td><td>{row.rtss}</td><td>{row.runs}</td></tr>
                      ))}
                    </tbody>
                  </table>
                </>
              )}
            </section>
          ) : null}

          {activeTab === "activities" ? (
            <>
              <section className="card">
                <h2>Activities</h2>
                {!dashboard ? (
                  <p>Load data to see activities.</p>
                ) : dashboard.activities.length === 0 ? (
                  <p>No activities found for this filter set.</p>
                ) : (
                  <table>
                    <thead>
                      <tr><th>Date</th><th>Sport</th><th>Distance</th><th>Duration</th><th>Pace</th><th>TSS</th><th>Action</th></tr>
                    </thead>
                    <tbody>
                      {dashboard.activities.map((row) => (
                        <tr key={row.activity_id} className={selectedActivityId === row.activity_id ? "selected-row" : ""}>
                          <td>{row.date}</td><td>{row.sport_type}</td><td>{row.distance_km} km</td><td>{row.duration_min} min</td><td>{row.avg_pace_display}</td><td>{row.tss || row.rtss}</td>
                          <td><button onClick={() => loadActivityDetail(row.activity_id)}>View detail</button></td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                )}
              </section>

              <section className="card">
                <h2>Activity detail</h2>
                {!activityDetail ? (
                  <p>Select an activity to inspect detail + records.</p>
                ) : (
                  <>
                    <div className="detail-grid">
                      <p><strong>ID:</strong> {activityDetail.activity.activity_id}</p>
                      <p><strong>Date:</strong> {activityDetail.activity.date}</p>
                      <p><strong>Sport:</strong> {activityDetail.activity.sport_type}</p>
                      <p><strong>Distance:</strong> {activityDetail.activity.distance_km} km</p>
                      <p><strong>Duration:</strong> {activityDetail.activity.duration_min} min</p>
                      <p><strong>TSS / rTSS:</strong> {activityDetail.activity.tss} / {activityDetail.activity.rtss}</p>
                    </div>
                    <h3>Records ({activityDetail.records.length})</h3>
                    {activityDetail.records.length === 0 ? (
                      <p>No records available.</p>
                    ) : (
                      <table>
                        <thead><tr><th>Time</th><th>HR</th><th>Speed</th><th>Distance</th><th>Cadence</th></tr></thead>
                        <tbody>
                          {activityDetail.records.slice(0, 120).map((row, idx) => (
                            <tr key={`${row.record_time_utc}-${idx}`}><td>{row.record_time_utc}</td><td>{row.heart_rate}</td><td>{row.speed}</td><td>{row.distance}</td><td>{row.cadence}</td></tr>
                          ))}
                        </tbody>
                      </table>
                    )}
                  </>
                )}
              </section>
            </>
          ) : null}

          <section className="card">
            <h2>Data snapshot</h2>
            {!overview ? (
              <p>Loading overview...</p>
            ) : (
              <ul>
                <li>Owner: {overview.owner}</li>
                <li>DB path: {overview.db_path}</li>
                <li>Activities: {overview.activities}</li>
                <li>Activity details: {overview.activity_details}</li>
                <li>Wellness rows: {overview.wellness_daily}</li>
              </ul>
            )}
          </section>
        </>
      )}
    </main>
  );
}
