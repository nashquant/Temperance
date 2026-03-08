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

export default function App() {
  const [health, setHealth] = useState("loading");
  const [token, setToken] = useState(() => localStorage.getItem(TOKEN_KEY) || "");
  const [userCtx, setUserCtx] = useState(null);
  const [owners, setOwners] = useState([]);
  const [owner, setOwner] = useState("");

  const [days, setDays] = useState("42");
  const [sport, setSport] = useState("");
  const [startDay, setStartDay] = useState("");
  const [endDay, setEndDay] = useState("");

  const [overview, setOverview] = useState(null);
  const [dashboard, setDashboard] = useState(null);
  const [weekly, setWeekly] = useState(null);
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
        const me = await parseOrThrow(
          await fetch("/api/v1/auth/me", { headers: authHeaders(token) })
        );
        setUserCtx(me);
        const ownerData = await parseOrThrow(
          await fetch("/api/v1/auth/owners", { headers: authHeaders(token) })
        );
        const ownerOptions = ownerData.owners || [];
        setOwners(ownerOptions);
        setOwner((prev) => prev || me.owner || ownerOptions[0] || "");
      } catch (err) {
        if (!token) {
          // When auth is enabled and no token is present, show login state.
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
      qs.set("days", String(Number(days) || 42));
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

      const [overviewData, dashboardData, weeklyData] = await Promise.all([
        parseOrThrow(
          await fetch(`/api/v1/overview?owner=${encodeURIComponent(owner || "")}`, {
            headers: authHeaders(token),
          })
        ),
        parseOrThrow(await fetch(`/api/v1/dashboard?${qs.toString()}`, { headers: authHeaders(token) })),
        parseOrThrow(await fetch(`/api/v1/weekly-summary?${qs.toString()}`, { headers: authHeaders(token) })),
      ]);

      setOverview(overviewData);
      setDashboard(dashboardData);
      setWeekly(weeklyData);
      setSelectedActivityId("");
      setActivityDetail(null);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed loading dashboard");
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
        await fetch(`/api/v1/activities/${encodeURIComponent(activityId)}?${qs.toString()}`, {
          headers: authHeaders(token),
        })
      );
      setSelectedActivityId(activityId);
      setActivityDetail(detail);
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
    setSelectedActivityId("");
    setActivityDetail(null);
  }

  useEffect(() => {
    if (canLoadData) {
      loadDashboard();
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [canLoadData, owner]);

  return (
    <main className="app-shell">
      <header className="header-row">
        <div>
          <h1>Temperance v2</h1>
          <p>React + FastAPI running alongside Streamlit v1.</p>
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
              <input
                type="password"
                value={loginPass}
                onChange={(e) => setLoginPass(e.target.value)}
                required
              />
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
              <h2>Session</h2>
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
                <input
                  placeholder="run, cycle, treadmill..."
                  value={sport}
                  onChange={(e) => setSport(e.target.value)}
                />
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

          <section className="card">
            <h2>Current data snapshot</h2>
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

          <section className="card">
            <h2>Dashboard</h2>
            {!dashboard ? (
              <p>Load data to see dashboard metrics.</p>
            ) : (
              <>
                <div className="kpi-grid">
                  <div className="kpi-item">
                    <span className="kpi-label">Distance</span>
                    <strong>{dashboard.kpis.distance_km} km</strong>
                  </div>
                  <div className="kpi-item">
                    <span className="kpi-label">Proxy distance</span>
                    <strong>{dashboard.kpis.distance_proxy_km} km</strong>
                  </div>
                  <div className="kpi-item">
                    <span className="kpi-label">Total TSS</span>
                    <strong>{dashboard.kpis.tss_total}</strong>
                  </div>
                  <div className="kpi-item">
                    <span className="kpi-label">Activities</span>
                    <strong>{dashboard.kpis.activities}</strong>
                  </div>
                </div>
                <p className="subtle">Days with training: {dashboard.kpis.days_with_training}</p>
              </>
            )}
          </section>

          <section className="card">
            <h2>Daily load series (latest 21 days)</h2>
            {!dashboard ? (
              <p>No daily series loaded yet.</p>
            ) : dashboard.daily.length === 0 ? (
              <p>No daily rows available.</p>
            ) : (
              <table>
                <thead>
                  <tr>
                    <th>Day</th>
                    <th>Distance (km)</th>
                    <th>Proxy (km)</th>
                    <th>TSS</th>
                  </tr>
                </thead>
                <tbody>
                  {dashboard.daily.slice(-21).map((row) => (
                    <tr key={row.day_utc}>
                      <td>{row.day_utc}</td>
                      <td>{row.distance_km}</td>
                      <td>{row.distance_proxy_km}</td>
                      <td>{row.tss_total}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            )}
          </section>

          <section className="card">
            <h2>Weekly summary</h2>
            {!weekly ? (
              <p>Load data to see weekly summary.</p>
            ) : weekly.weeks.length === 0 ? (
              <p>No weekly rows available for this filter set.</p>
            ) : (
              <>
                <p className="subtle">
                  Weeks: {weekly.summary.weeks} | Activities: {weekly.summary.total_activities} | Distance:{" "}
                  {weekly.summary.total_distance_km} km | TSS: {weekly.summary.total_tss}
                </p>
                <table>
                  <thead>
                    <tr>
                      <th>Week start</th>
                      <th>Distance (km)</th>
                      <th>Proxy (km)</th>
                      <th>TSS</th>
                      <th>rTSS</th>
                      <th>Activities</th>
                    </tr>
                  </thead>
                  <tbody>
                    {weekly.weeks.map((row) => (
                      <tr key={row.week_start}>
                        <td>{row.week_start}</td>
                        <td>{row.distance_km}</td>
                        <td>{row.distance_proxy_km}</td>
                        <td>{row.tss}</td>
                        <td>{row.rtss}</td>
                        <td>{row.runs}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </>
            )}
          </section>

          <section className="card">
            <h2>Activities</h2>
            {!dashboard ? (
              <p>Load data to see activities.</p>
            ) : dashboard.activities.length === 0 ? (
              <p>No activities found for this filter set.</p>
            ) : (
              <table>
                <thead>
                  <tr>
                    <th>Date</th>
                    <th>Sport</th>
                    <th>Distance</th>
                    <th>Duration</th>
                    <th>Pace</th>
                    <th>TSS</th>
                    <th>Action</th>
                  </tr>
                </thead>
                <tbody>
                  {dashboard.activities.map((row) => (
                    <tr
                      key={row.activity_id}
                      className={selectedActivityId === row.activity_id ? "selected-row" : ""}
                    >
                      <td>{row.date}</td>
                      <td>{row.sport_type}</td>
                      <td>{row.distance_km} km</td>
                      <td>{row.duration_min} min</td>
                      <td>{row.avg_pace_display}</td>
                      <td>{row.tss || row.rtss}</td>
                      <td>
                        <button onClick={() => loadActivityDetail(row.activity_id)}>View detail</button>
                      </td>
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
                  <p>
                    <strong>ID:</strong> {activityDetail.activity.activity_id}
                  </p>
                  <p>
                    <strong>Date:</strong> {activityDetail.activity.date}
                  </p>
                  <p>
                    <strong>Sport:</strong> {activityDetail.activity.sport_type}
                  </p>
                  <p>
                    <strong>Distance:</strong> {activityDetail.activity.distance_km} km
                  </p>
                  <p>
                    <strong>Duration:</strong> {activityDetail.activity.duration_min} min
                  </p>
                  <p>
                    <strong>TSS / rTSS:</strong> {activityDetail.activity.tss} / {activityDetail.activity.rtss}
                  </p>
                </div>

                <h3>Records ({activityDetail.records.length})</h3>
                {activityDetail.records.length === 0 ? (
                  <p>No records available.</p>
                ) : (
                  <table>
                    <thead>
                      <tr>
                        <th>Time</th>
                        <th>HR</th>
                        <th>Speed</th>
                        <th>Distance</th>
                        <th>Cadence</th>
                      </tr>
                    </thead>
                    <tbody>
                      {activityDetail.records.slice(0, 120).map((row, idx) => (
                        <tr key={`${row.record_time_utc}-${idx}`}>
                          <td>{row.record_time_utc}</td>
                          <td>{row.heart_rate}</td>
                          <td>{row.speed}</td>
                          <td>{row.distance}</td>
                          <td>{row.cadence}</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                )}
              </>
            )}
          </section>
        </>
      )}
    </main>
  );
}
