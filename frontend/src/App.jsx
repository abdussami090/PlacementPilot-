import { useCallback, useEffect, useRef, useState } from "react";
import { apiRequest, apiBlobRequest, formatDate, moneyLabel, statusClass } from "./api";
import "./App.css";

const STUDENT_NAV = [
  { id: "dashboard", label: "Overview", icon: "▦" },
  { id: "jobs", label: "Find jobs", icon: "⌕" },
  { id: "saved", label: "Saved jobs", icon: "☆" },
  { id: "applications", label: "Applications", icon: "▤" },
  { id: "rounds", label: "Placement rounds", icon: "◷" },
  { id: "timeline", label: "My timeline", icon: "⌁" },
  { id: "profile", label: "My profile", icon: "◎" },
];

const ADMIN_NAV = [
  { id: "admin-dashboard", label: "Overview", icon: "▦" },
  { id: "admin-applications", label: "Applications", icon: "▤" },
  { id: "admin-jobs", label: "Jobs", icon: "⌕" },
  { id: "admin-companies", label: "Companies", icon: "▣" },
  { id: "admin-cycles", label: "Placement cycles", icon: "◷" },
  { id: "admin-policies", label: "Placement policies", icon: "⚙" },
  { id: "admin-drives", label: "Recruitment drives", icon: "▤" },
  { id: "admin-rounds", label: "Round management", icon: "⌁" },
  { id: "admin-students", label: "Students", icon: "◎" },
];

const APPLICATION_STATUSES = [
  "Applied", "Under Review", "Shortlisted", "In Progress", "Selected", "Rejected", "Offer Released",
];

function App() {
  const [token, setToken] = useState(() => sessionStorage.getItem("placementpilot_token") || "");
  const [user, setUser] = useState(null);
  const [authLoading, setAuthLoading] = useState(Boolean(sessionStorage.getItem("placementpilot_token")));
  const [page, setPage] = useState("dashboard");
  const [pageData, setPageData] = useState(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");
  const [search, setSearch] = useState("");
  const [location, setLocation] = useState("");
  const [currentPage, setCurrentPage] = useState(1);
  const [selectedDriveId, setSelectedDriveId] = useState("");
  const [roundCandidates, setRoundCandidates] = useState({});

  const role = user?.role;
  const isAdmin = role === "admin";
  const navItems = isAdmin ? ADMIN_NAV : STUDENT_NAV;

  const logout = useCallback(() => {
    sessionStorage.removeItem("placementpilot_token");
    setToken("");
    setUser(null);
    setPage("dashboard");
    setPageData(null);
    setError("");
  }, []);

  useEffect(() => {
    let active = true;
    if (!token) return undefined;
    apiRequest("/auth/me", { token })
      .then((profile) => {
        if (active) {
          setUser(profile);
          setPage(profile.role === "admin" ? "admin-dashboard" : "dashboard");
        }
      })
      .catch(() => {
        sessionStorage.removeItem("placementpilot_token");
        if (active) {
          setToken("");
          setUser(null);
        }
      })
      .finally(() => active && setAuthLoading(false));
    return () => { active = false; };
  }, [token]);

  const loadPage = useCallback(async (target = page, overrides = {}) => {
    if (!token || !user) return;
    setLoading(true);
    setError("");
    try {
      let result;
      const pageNumber = overrides.page ?? currentPage;
      switch (target) {
        case "dashboard":
          result = await apiRequest("/student/dashboard", { token });
          break;
        case "jobs": {
          const params = new URLSearchParams({ page: String(pageNumber), page_size: "9" });
          const term = overrides.search ?? search;
          const place = overrides.location ?? location;
          if (term.trim()) params.set("search", term.trim());
          if (place.trim()) params.set("location", place.trim());
          result = await apiRequest(`/student/jobs?${params.toString()}`, { token });
          break;
        }
        case "saved":
          result = await apiRequest("/student/saved-jobs?page=1&page_size=50", { token });
          break;
        case "applications":
          result = await apiRequest("/applications", { token });
          break;
        case "rounds":
          result = await apiRequest("/student/rounds", { token });
          break;
        case "timeline":
          result = await apiRequest("/student/timeline", { token });
          break;
        case "profile": {
          const [profile, education, skills, resumes, uploadedResume] = await Promise.all([
            apiRequest("/profile", { token }).catch((err) => {
              if (err.status === 404) return null;
              throw err;
            }),
            apiRequest("/education", { token }),
            apiRequest("/skills", { token }),
            apiRequest("/resume", { token }),
            apiRequest("/resume/uploaded", { token }).catch((err) => {
              if (err.status === 404) return null;
              throw err;
            }),
          ]);
          const asRows = (value) => Array.isArray(value) ? value : Array.isArray(value?.items) ? value.items : value ? [value] : [];
          result = {
            profile,
            education: asRows(education),
            skills: asRows(skills),
            resumes: asRows(resumes),
            uploadedResume,
          };
          break;
        }
        case "admin-dashboard":
          result = await apiRequest("/admin/dashboard/overview", { token });
          break;
        case "admin-applications":
          result = await apiRequest("/admin/applications", { token });
          break;
        case "admin-jobs": {
          const [jobs, drives] = await Promise.all([
            apiRequest("/admin/jobs", { token }),
            apiRequest("/admin/recruitment-drives", { token }),
          ]);
          const rows = Array.isArray(jobs) ? jobs : [];
          const eligibilityEntries = await Promise.all(rows.map(async (job) => {
            try {
              return [job.id, await apiRequest(`/admin/jobs/${job.id}/eligibility`, { token })];
            } catch (err) {
              if (err.status === 404) return [job.id, null];
              throw err;
            }
          }));
          result = { rows, drives, eligibility: Object.fromEntries(eligibilityEntries) };
          break;
        }
        case "admin-companies":
          result = await apiRequest("/admin/companies", { token });
          break;
        case "admin-cycles":
          result = await apiRequest("/admin/cycles", { token });
          break;
        case "admin-policies": {
          const cycles = await apiRequest("/admin/cycles", { token });
          const policyEntries = await Promise.all(cycles.map(async (cycle) => {
            try {
              const policy = await apiRequest(`/admin/cycles/${cycle.id}/policy`, { token });
              return [cycle.id, policy];
            } catch (err) {
              if (err.status === 404) return [cycle.id, null];
              throw err;
            }
          }));
          result = { cycles, policies: Object.fromEntries(policyEntries) };
          break;
        }
        case "admin-drives": {
          const [rows, companies, cycles] = await Promise.all([
            apiRequest("/admin/recruitment-drives", { token }),
            apiRequest("/admin/companies", { token }),
            apiRequest("/admin/cycles", { token }),
          ]);
          result = { rows, companies, cycles };
          break;
        }
        case "admin-students":
          result = await apiRequest("/admin/users", { token });
          break;
        case "admin-rounds": {
          const drives = await apiRequest("/admin/recruitment-drives", { token });
          const driveId = overrides.driveId || selectedDriveId || drives?.[0]?.id;
          let rounds = [];
          if (driveId) rounds = await apiRequest(`/admin/recruitment-drives/${driveId}/rounds`, { token });
          result = { drives, rounds, driveId: driveId ? String(driveId) : "" };
          if (driveId) setSelectedDriveId(String(driveId));
          break;
        }
        default:
          result = null;
      }
      setPageData(result);
    } catch (err) {
      setError(err.message || "Unable to load this section.");
      setPageData(null);
    } finally {
      setLoading(false);
    }
  }, [token, user, page, currentPage, search, location, selectedDriveId]);

  const loadPageRef = useRef(loadPage);

  useEffect(() => {
    loadPageRef.current = loadPage;
  }, [loadPage]);

  useEffect(() => {
    if (user) {
      loadPageRef.current(page);
    }
  }, [user, page]);

  const notify = (message) => {
    setNotice(message);
    window.setTimeout(() => setNotice(""), 3200);
  };

  const navigate = (target) => {
    setPage(target);
    setPageData(null);
    setError("");
    setCurrentPage(1);
  };

  const doLogin = async (email, password) => {
    const form = new URLSearchParams({ username: email, password });
    const response = await apiRequest("/auth/login", { method: "POST", form });
    if (!response.access_token) throw new Error("Login response did not contain an access token.");
    sessionStorage.setItem("placementpilot_token", response.access_token);
    setToken(response.access_token);
    const current = await apiRequest("/auth/me", { token: response.access_token });
    setUser(current);
    setPage(current.role === "admin" ? "admin-dashboard" : "dashboard");
    notify(`Welcome, ${current.name || "user"}.`);
  };

  const doSignup = async (name, email, password) => {
    const response = await apiRequest("/auth/signup", { method: "POST", body: { name, email, password } });
    if (response.message?.toLowerCase().includes("already")) throw new Error(response.message);
    await doLogin(email, password);
  };

  const refresh = () => loadPage(page);

  const saveJob = async (jobId, currentlySaved) => {
    try {
      await apiRequest(`/student/saved-jobs/${jobId}`, { token, method: currentlySaved ? "DELETE" : "POST" });
      notify(currentlySaved ? "Removed from saved jobs." : "Job saved successfully.");
      await loadPage(page);
    } catch (err) { setError(err.message); }
  };

  const applyToJob = async (jobId) => {
    try {
      await apiRequest("/apply", { token, method: "POST", body: { job_id: jobId } });
      notify("Application submitted successfully.");
      await loadPage(page);
    } catch (err) { setError(err.message); }
  };

  const withdrawApplication = async (applicationId) => {
    if (!window.confirm("Withdraw this application?")) return;
    try {
      await apiRequest(`/application/${applicationId}`, { token, method: "DELETE" });
      notify("Application withdrawn.");
      await loadPage(page);
    } catch (err) { setError(err.message); }
  };

  const offerResponse = async (applicationId, decision) => {
    try {
      await apiRequest(`/application/${applicationId}/offer-response`, { token, method: "POST", body: { decision } });
      notify(decision === "accept" ? "Offer accepted." : "Offer declined.");
      await loadPage(page);
    } catch (err) { setError(err.message); }
  };

  const updateApplicationStatus = async (applicationId, status) => {
    try {
      await apiRequest(`/admin/applications/${applicationId}/status`, { token, method: "PUT", body: { status } });
      notify("Application status updated.");
      await loadPage(page);
    } catch (err) { setError(err.message); }
  };

  const viewStudentResume = async (studentId) => {
    // Open a tab synchronously from the button click so the browser does not block it.
    const preview = window.open("about:blank", "_blank");
    try {
      const blob = await apiBlobRequest(`/admin/students/${studentId}/resume`, { token });
      const objectUrl = URL.createObjectURL(blob);
      if (preview) {
        preview.location.href = objectUrl;
      } else {
        const anchor = document.createElement("a");
        anchor.href = objectUrl;
        anchor.download = `student-${studentId}-resume.pdf`;
        document.body.appendChild(anchor);
        anchor.click();
        anchor.remove();
      }
      window.setTimeout(() => URL.revokeObjectURL(objectUrl), 60000);
    } catch (err) {
      if (preview) preview.close();
      setError(err.message);
    }
  };

  if (authLoading) return <div className="boot-screen"><div className="loader"/><span>Opening PlacementPilot…</span></div>;
  if (!user) return <AuthScreen onLogin={doLogin} onSignup={doSignup} />;

  return (
    <div className="app-shell">
      <aside className="sidebar">
        <div className="brand-lockup"><div className="brand-mark">P</div><div><strong>PlacementPilot</strong><span>Campus placement suite</span></div></div>
        <div className="workspace-label">WORKSPACE</div>
        <nav className="side-nav">
          {navItems.map((item) => (
            <button key={item.id} className={`nav-item ${page === item.id ? "active" : ""}`} onClick={() => navigate(item.id)}>
              <span className="nav-icon">{item.icon}</span><span>{item.label}</span>
              {page === item.id && <span className="active-dot"/>}
            </button>
          ))}
        </nav>
        <div className="sidebar-bottom">
          <div className="support-card"><div className="support-icon">✦</div><strong>Stay placement-ready</strong><p>Keep your profile and academic details updated.</p></div>
          <button className="profile-mini" onClick={() => navigate(isAdmin ? "admin-dashboard" : "profile")}>
            <div className="avatar">{(user.name || user.email || "U").slice(0, 1).toUpperCase()}</div>
            <div className="profile-mini-copy"><strong>{user.name || "Account"}</strong><span>{user.role}</span></div>
            <span className="mini-arrow">↗</span>
          </button>
          <button className="logout-button" onClick={logout}>↪ &nbsp; Sign out</button>
        </div>
      </aside>

      <main className="main-area">
        <header className="topbar">
          <div><div className="eyebrow">{isAdmin ? "PLACEMENT ADMINISTRATION" : "STUDENT PORTAL"}</div><h1>{pageTitle(page)}</h1></div>
          <div className="topbar-right"><span className="system-status"><i/> System connected</span><div className="top-avatar">{(user.name || "U").slice(0, 1).toUpperCase()}</div></div>
        </header>
        <div className="content-area">
          {notice && <div className="toast success-toast">✓ {notice}</div>}
          {error && <div className="alert error-alert"><strong>Something needs attention</strong><span>{error}</span><button onClick={() => setError("")}>×</button></div>}
          {loading && <div className="loading-strip"><span/> Loading latest information…</div>}
          {/* A missing profile (GET /profile returns 404) is a valid first-time
              student state. Render the create form instead of the generic empty state. */}
          {!loading && (pageData !== null || (page === "profile" && !error)) && renderPage({
            page, data: pageData, user, token, search, setSearch, location, setLocation,
            currentPage, setCurrentPage, loadPage, notify, setError, saveJob, applyToJob,
            withdrawApplication, offerResponse, updateApplicationStatus, viewStudentResume, selectedDriveId,
            setSelectedDriveId, roundCandidates, setRoundCandidates,
          })}
          {!loading && pageData === null && page !== "profile" && !error && <EmptyState title="Nothing to display yet" description="Refresh this section or check whether your account has the required access." onRefresh={refresh}/>}
        </div>
        <footer className="app-footer"><span>PlacementPilot</span><span>College placement management · {new Date().getFullYear()}</span></footer>
      </main>
    </div>
  );
}

function pageTitle(page) {
  const all = [...STUDENT_NAV, ...ADMIN_NAV];
  return all.find((item) => item.id === page)?.label || "PlacementPilot";
}

function AuthScreen({ onLogin, onSignup }) {
  const [mode, setMode] = useState("login");
  const [name, setName] = useState("");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");

  const submit = async (event) => {
    event.preventDefault();
    setBusy(true); setError("");
    try {
      if (mode === "signup") await onSignup(name.trim(), email.trim(), password);
      else await onLogin(email.trim(), password);
    } catch (err) { setError(err.message || "Unable to sign in."); }
    finally { setBusy(false); }
  };

  return (
    <div className="auth-layout">
      <section className="auth-story">
        <div className="brand-lockup auth-brand"><div className="brand-mark">P</div><div><strong>PlacementPilot</strong><span>Campus placement suite</span></div></div>
        <div className="story-content"><div className="story-pill"><i/> REAL CAMPUS PLACEMENTS</div><h1>One clear path from <em>campus</em> to career.</h1><p>Discover verified placement opportunities, manage applications, and stay informed at every recruitment stage.</p><div className="story-metrics"><div><strong>01</strong><span>Discover opportunities</span></div><div><strong>02</strong><span>Track your progress</span></div><div><strong>03</strong><span>Move through rounds</span></div></div></div>
        <div className="story-footer">Built for students and college placement teams.</div>
      </section>
      <section className="auth-panel"><div className="auth-card"><div className="auth-heading"><span className="eyebrow">WELCOME TO PLACEMENTPILOT</span><h2>{mode === "login" ? "Sign in to your account" : "Create your student account"}</h2><p>{mode === "login" ? "Use your registered college account to continue." : "Use at least 12 characters for your password."}</p></div>
        <form onSubmit={submit} className="form-stack">
          {mode === "signup" && <Field label="Full name"><input required value={name} onChange={(e) => setName(e.target.value)} placeholder="Your full name"/></Field>}
          <Field label="Email address"><input type="email" required value={email} onChange={(e) => setEmail(e.target.value)} placeholder="you@college.edu" autoComplete="username"/></Field>
          <Field label="Password"><input type="password" required minLength={mode === "signup" ? 12 : undefined} value={password} onChange={(e) => setPassword(e.target.value)} placeholder="Enter your password" autoComplete={mode === "login" ? "current-password" : "new-password"}/></Field>
          {error && <div className="form-error">{error}</div>}
          <button className="primary-button wide-button" disabled={busy}>{busy ? "Please wait…" : mode === "login" ? "Sign in securely  →" : "Create account  →"}</button>
        </form>
        <div className="auth-switch">{mode === "login" ? "New student?" : "Already registered?"}<button onClick={() => { setMode(mode === "login" ? "signup" : "login"); setError(""); }}>{mode === "login" ? "Create an account" : "Sign in"}</button></div>
        <div className="auth-note">Admin accounts are created and managed by the placement administrator.</div>
      </div></section>
    </div>
  );
}

function renderPage(props) {
  const { page, data } = props;
  switch (page) {
    case "dashboard": return <StudentDashboard data={data} />;
    case "jobs": return <JobsPage {...props} />;
    case "saved": return <JobCollection title="Saved jobs" subtitle="Opportunities you bookmarked for later." data={data} {...props} />;
    case "applications": return <ApplicationsPage data={data} {...props} />;
    case "rounds": return <RoundsPage data={data} />;
    case "timeline": return <TimelinePage data={data} />;
    case "profile": return <ProfilePage data={data} {...props} />;
    case "admin-dashboard": return <AdminDashboard data={data} />;
    case "admin-applications": return <AdminApplications data={data} {...props} />;
    case "admin-jobs": return <><AdminEntityPage kind="jobs" data={data} {...props} /><AdminEligibilityManager data={data} token={props.token} loadPage={props.loadPage} notify={props.notify} setError={props.setError}/></>;
    case "admin-companies": return <AdminEntityPage kind="companies" data={data} {...props} />;
    case "admin-cycles": return <AdminEntityPage kind="cycles" data={data} {...props} />;
    case "admin-policies": return <AdminPolicyManager data={data} {...props} />;
    case "admin-drives": return <AdminEntityPage kind="drives" data={data} {...props} />;
    case "admin-students": return <AdminStudents data={data} {...props} />;
    case "admin-rounds": return <AdminRoundsPage {...props} />;
    default: return <EmptyState title="Page not found" description="Choose a section from the navigation."/>;
  }
}

function StudentDashboard({ data }) {
  const stats = data?.statistics || {};
  const rounds = data?.upcoming_rounds || [];
  return <>
    <div className="welcome-banner"><div><span className="eyebrow light-eyebrow">YOUR PLACEMENT JOURNEY</span><h2>Keep moving forward.</h2><p>Your applications, saved opportunities and upcoming rounds in one place.</p></div><div className="banner-graphic"><div className="orbit orbit-one"/><div className="orbit orbit-two"/><div className="orbit-center">P</div></div></div>
    <div className="stats-grid">
      <StatCard label="Total applications" value={stats.total_applications ?? 0} helper="All submitted applications" icon="▤"/>
      <StatCard label="Active applications" value={stats.active_applications ?? 0} helper="Currently in process" icon="◷"/>
      <StatCard label="Offers released" value={stats.offers_released ?? 0} helper="Awaiting your response" icon="✉"/>
      <StatCard label="Saved jobs" value={stats.saved_jobs ?? 0} helper="Bookmarked opportunities" icon="☆"/>
    </div>
    <div className="section-heading-row"><div><span className="eyebrow">UP NEXT</span><h2>Upcoming placement rounds</h2></div><span className="subtle-count">{rounds.length} scheduled</span></div>
    {rounds.length ? <div className="round-list">{rounds.map((round) => <div className="round-row" key={round.round_id}><div className="round-date"><strong>{new Date(round.scheduled_at).toLocaleDateString("en-IN", { day: "2-digit" })}</strong><span>{new Date(round.scheduled_at).toLocaleDateString("en-IN", { month: "short" })}</span></div><div className="round-info"><strong>{round.round_name}</strong><span>{round.company} · {round.job_role}</span><small>{formatDate(round.scheduled_at, true)}{round.venue ? ` · ${round.venue}` : ""}</small></div><StatusPill status={round.round_status}/></div>)}</div> : <EmptyState title="No upcoming rounds" description="When the placement team assigns you to a scheduled round, it will appear here."/>}
    <div className="section-heading-row"><div><span className="eyebrow">APPLICATION SNAPSHOT</span><h2>Current status breakdown</h2></div></div>
    <div className="status-summary">{Object.entries(data?.applications_by_status || {}).map(([status, count]) => <div key={status}><StatusPill status={status}/><strong>{count}</strong></div>)}</div>
  </>;
}

function JobsPage({ data, search, setSearch, location, setLocation, currentPage, setCurrentPage, loadPage, saveJob, applyToJob }) {
  const items = data?.items || [];
  const pagination = data?.pagination || {};
  return <>
    <div className="page-intro"><div><h2>Find your next opportunity</h2><p>Browse official opportunities shared by your college placement cell.</p></div><div className="verified-label"><i/> Placement-cell listings</div></div>
    <div className="filter-bar"><label className="search-field"><span>⌕</span><input value={search} onChange={(e) => setSearch(e.target.value)} placeholder="Search role, company or drive" onKeyDown={(e) => e.key === "Enter" && (setCurrentPage(1), loadPage("jobs", { page: 1 }))}/></label><label className="search-field location-field"><span>⌖</span><input value={location} onChange={(e) => setLocation(e.target.value)} placeholder="Location" onKeyDown={(e) => e.key === "Enter" && (setCurrentPage(1), loadPage("jobs", { page: 1 }))}/></label><button className="primary-button" onClick={() => { setCurrentPage(1); loadPage("jobs", { page: 1 }); }}>Search jobs</button></div>
    <div className="results-line"><span>{pagination.total_items ?? items.length} opportunities found</span><span>Page {pagination.page || currentPage} of {pagination.total_pages || 1}</span></div>
    {items.length ? <div className="job-grid">{items.map((job) => <JobCard key={job.id} job={job} saveJob={saveJob} applyToJob={applyToJob}/>)}</div> : <EmptyState title="No open opportunities found" description="Try a different search or check again when the placement cell publishes a new drive."/>}
    <div className="pagination"><button disabled={!pagination.has_previous} onClick={() => { const page = currentPage - 1; setCurrentPage(page); loadPage("jobs", { page }); }}>← Previous</button><span>Page {pagination.page || currentPage}</span><button disabled={!pagination.has_next} onClick={() => { const page = currentPage + 1; setCurrentPage(page); loadPage("jobs", { page }); }}>Next →</button></div>
  </>;
}

function JobCollection({ title, subtitle, data, saveJob, applyToJob }) {
  const items = data?.items || [];
  return <><div className="page-intro"><div><h2>{title}</h2><p>{subtitle}</p></div><span className="subtle-count">{items.length} saved</span></div>{items.length ? <div className="job-grid">{items.map((job) => <JobCard key={job.id} job={job} saveJob={saveJob} applyToJob={applyToJob}/>)}</div> : <EmptyState title="No saved jobs yet" description="Use the bookmark control on a job card to keep an opportunity here."/>}</>;
}

function JobCard({ job, saveJob, applyToJob }) {
  const eligible = job.eligibility?.eligible !== false;
  const reasons = job.eligibility?.reasons || [];
  return <article className="job-card"><div className="job-card-top"><div className="company-mark">{(job.company?.name || "C").slice(0, 1).toUpperCase()}</div><button className={`bookmark-button ${job.is_saved ? "bookmarked" : ""}`} title={job.is_saved ? "Remove saved job" : "Save job"} onClick={() => saveJob(job.id, Boolean(job.is_saved))}>{job.is_saved ? "★" : "☆"}</button></div><div className="job-company">{job.company?.name || "Company"}</div><h3>{job.role}</h3><div className="job-meta"><span>⌖ {job.location || "Location not specified"}</span><span>◈ {moneyLabel(job.package)}</span></div><div className="job-drive">{job.recruitment_drive?.name || "Recruitment drive"}</div><div className="eligibility-line"><span className={`eligibility-dot ${eligible ? "eligible" : "not-eligible"}`}/>{eligible ? "You meet the listed criteria" : "Eligibility criteria not met"}</div>{!eligible && reasons.length > 0 && <p className="eligibility-reasons">{reasons.slice(0, 2).join(" · ")}</p>}<div className="job-card-actions"><button className="primary-button" disabled={!eligible} onClick={() => applyToJob(job.id)}>{eligible ? "Apply now →" : "Not eligible"}</button><span>Deadline {formatDate(job.recruitment_drive?.application_deadline)}</span></div></article>;
}

function ApplicationsPage({ data, withdrawApplication, offerResponse }) {
  const rows = Array.isArray(data) ? data : [];
  return <><div className="page-intro"><div><h2>Your application history</h2><p>Track every role you have applied for and respond to released offers.</p></div><span className="subtle-count">{rows.length} applications</span></div>
    {rows.length ? <div className="table-card"><div className="table-wrap"><table><thead><tr><th>Role & company</th><th>Placement drive</th><th>Package</th><th>Status</th><th>Action</th></tr></thead><tbody>{rows.map((app) => <tr key={app.application_id}><td><strong>{app.role || `Job #${app.job_id}`}</strong><small>{app.company || "Company"}</small></td><td>{app.recruitment_drive || "—"}</td><td>{moneyLabel(app.package)}</td><td><StatusPill status={app.status}/></td><td><div className="inline-actions">{app.status === "Offer Released" ? <><button className="small-action positive" onClick={() => offerResponse(app.application_id, "accept")}>Accept</button><button className="small-action negative" onClick={() => offerResponse(app.application_id, "decline")}>Decline</button></> : !["Rejected", "Withdrawn", "Offer Accepted", "Offer Declined", "Joined"].includes(app.status) ? <button className="text-action" onClick={() => withdrawApplication(app.application_id)}>Withdraw</button> : <span className="muted-dash">—</span>}</div></td></tr>)}</tbody></table></div></div> : <EmptyState title="No applications yet" description="When you apply to a published opportunity, its progress will be shown here."/>}
  </>;
}

function RoundsPage({ data }) {
  const rows = Array.isArray(data) ? data : [];
  return <><div className="page-intro"><div><h2>Your recruitment schedule</h2><p>Round timing, venue and result details assigned by the placement team.</p></div><span className="subtle-count">{rows.length} assigned rounds</span></div>
    {rows.length ? <div className="table-card"><div className="table-wrap"><table><thead><tr><th>Round</th><th>Company / role</th><th>Schedule</th><th>Attendance</th><th>Result</th><th>Score</th></tr></thead><tbody>{rows.map((round) => <tr key={`${round.application_id}-${round.round_id}`}><td><strong>{round.round_sequence}. {round.round_name}</strong><small>{round.recruitment_drive}</small></td><td>{round.job_role}</td><td>{formatDate(round.scheduled_at, true)}<small>{round.venue || (round.meeting_link ? "Online" : "To be announced")}</small>{round.meeting_link && <small><a href={round.meeting_link} target="_blank" rel="noreferrer">Open meeting link ↗</a></small>}</td><td><StatusPill status={round.attendance}/></td><td><StatusPill status={round.result}/>{round.feedback && <small>{round.feedback}</small>}</td><td>{round.score ?? "—"}</td></tr>)}</tbody></table></div></div> : <EmptyState title="No rounds assigned" description="Your placement round schedule will appear here after the administrator assigns you."/>}
  </>;
}

function TimelinePage({ data }) {
  const applications = data?.applications || [];
  const events = data?.events || [];
  return <><div className="page-intro"><div><h2>Placement activity</h2><p>A consolidated view of applications and recruitment-round updates.</p></div></div>
    <div className="timeline-layout"><section className="timeline-panel"><h3>Recent events</h3>{events.length ? <div className="activity-list">{events.map((event, index) => <div className="activity-item" key={`${event.event_type}-${event.round_id}-${index}`}><div className="activity-marker"/><div><strong>{event.event_type} · {event.round_name}</strong><span>{event.company} · {event.job_role}</span><small>{formatDate(event.occurred_at, true)} · Attendance: {event.attendance} · Result: {event.result}{event.score !== undefined && event.score !== null ? ` · Score: ${event.score}` : ""}</small>{event.feedback && <p>{event.feedback}</p>}</div></div>)}</div> : <p className="empty-inline">No round events have been recorded yet.</p>}</section>
      <section className="timeline-panel"><h3>Applications</h3>{applications.length ? applications.map((app) => <div className="application-mini" key={app.application_id}><div><strong>{app.job_role}</strong><span>{app.company} · {app.drive}</span></div><StatusPill status={app.current_status}/></div>) : <p className="empty-inline">No application history yet.</p>}</section></div>
  </>;
}

function ProfilePage({ data, token, loadPage, notify, setError }) {
  const profile = data?.profile || null;
  const educationRows = Array.isArray(data?.education) ? data.education : [];
  const skillRows = Array.isArray(data?.skills) ? data.skills : [];
  const resumeRows = Array.isArray(data?.resumes) ? data.resumes : [];
  const uploadedResume = data?.uploadedResume || null;
  const [section, setSection] = useState("profile");

  const [profileForm, setProfileForm] = useState(() => ({
    college: profile?.college || "",
    branch: profile?.branch || "",
    year: profile?.year || "",
    linkedin: profile?.linkedin || "",
    github: profile?.github || "",
    skills: profile?.skills || "",
  }));
  const [profileBusy, setProfileBusy] = useState(false);

  const emptyEducation = {
    degree: "", college: "", year: "", cgpa: "",
    graduation_year: new Date().getFullYear(), active_backlogs: 0,
  };
  const [educationForm, setEducationForm] = useState(emptyEducation);
  const [editingEducationId, setEditingEducationId] = useState(null);
  const [educationBusy, setEducationBusy] = useState(false);

  const [skillName, setSkillName] = useState("");
  const [skillBusy, setSkillBusy] = useState(false);
  const [deletingSkillId, setDeletingSkillId] = useState(null);

  const [resumeFile, setResumeFile] = useState(null);
  const [resumeBusy, setResumeBusy] = useState(false);
  const [deletingResumeId, setDeletingResumeId] = useState(null);
  const [deletingUploadedResume, setDeletingUploadedResume] = useState(false);

  const saveProfile = async (event) => {
    event.preventDefault();
    setProfileBusy(true);
    try {
      // The current Pydantic schema requires all six keys. Empty social URLs
      // are sent as empty strings, so students can leave them blank.
      await apiRequest("/profile", {
        token,
        method: profile ? "PUT" : "POST",
        body: {
          ...profileForm,
          linkedin: profileForm.linkedin.trim(),
          github: profileForm.github.trim(),
        },
      });
      notify("Profile saved successfully.");
      await loadPage("profile");
    } catch (err) {
      setError(err.message);
    } finally {
      setProfileBusy(false);
    }
  };

  const saveEducation = async (event) => {
    event.preventDefault();
    setEducationBusy(true);
    const payload = {
      degree: educationForm.degree.trim(),
      college: educationForm.college.trim(),
      year: educationForm.year.trim(),
      cgpa: educationForm.cgpa.trim(),
      graduation_year: Number(educationForm.graduation_year),
      active_backlogs: Number(educationForm.active_backlogs),
    };
    try {
      await apiRequest(
        editingEducationId ? `/education/${editingEducationId}` : "/education",
        { token, method: editingEducationId ? "PUT" : "POST", body: payload },
      );
      notify(editingEducationId ? "Education record updated." : "Education record added.");
      setEducationForm(emptyEducation);
      setEditingEducationId(null);
      await loadPage("profile");
    } catch (err) {
      setError(err.message);
    } finally {
      setEducationBusy(false);
    }
  };

  const editEducation = (row) => {
    setEducationForm({
      degree: row.degree || "",
      college: row.college || "",
      year: row.year || "",
      cgpa: row.cgpa === null || row.cgpa === undefined ? "" : String(row.cgpa),
      graduation_year: row.graduation_year ?? new Date().getFullYear(),
      active_backlogs: row.active_backlogs ?? 0,
    });
    setEditingEducationId(row.id);
    setSection("education");
  };

  const deleteEducation = async (id) => {
    if (!window.confirm("Delete this academic record?")) return;
    try {
      await apiRequest(`/education/${id}`, { token, method: "DELETE" });
      notify("Education record deleted.");
      await loadPage("profile");
    } catch (err) {
      setError(err.message);
    }
  };

  const addSkill = async (event) => {
    event.preventDefault();
    const cleanName = skillName.trim();
    if (!cleanName) return;
    setSkillBusy(true);
    try {
      await apiRequest("/skill", { token, method: "POST", body: { skill_name: cleanName } });
      setSkillName("");
      notify("Skill added successfully.");
      await loadPage("profile");
    } catch (err) {
      setError(err.message);
    } finally {
      setSkillBusy(false);
    }
  };

  const deleteSkill = async (id) => {
    if (!window.confirm("Remove this skill?")) return;
    setDeletingSkillId(id);
    try {
      await apiRequest(`/skill/${id}`, { token, method: "DELETE" });
      notify("Skill removed.");
      await loadPage("profile");
    } catch (err) {
      setError(err.message);
    } finally {
      setDeletingSkillId(null);
    }
  };

  const uploadResumePdf = async (event) => {
    event.preventDefault();
    if (!resumeFile) { setError("Choose a PDF resume first."); return; }
    if (!resumeFile.name.toLowerCase().endsWith(".pdf") || resumeFile.type !== "application/pdf") {
      setError("Only PDF files are accepted."); return;
    }
    if (resumeFile.size > 5 * 1024 * 1024) { setError("PDF must be 5 MB or smaller."); return; }
    if (uploadedResume && !window.confirm("Replace your current PDF resume with this file?")) return;

    setResumeBusy(true);
    try {
      const formData = new FormData();
      formData.append("file", resumeFile);
      const uploadResult = await apiRequest("/resume/upload", { token, method: "POST", body: formData });
      setResumeFile(null);
      const input = document.getElementById("resume-pdf-input");
      if (input) input.value = "";
      notify(uploadResult.cleanup_warning
        ? "Resume saved, but old-file cleanup requires administrator attention."
        : uploadedResume ? "PDF resume replaced successfully." : "PDF resume uploaded successfully.");
      await loadPage("profile");
    } catch (err) {
      setError(err.message);
    } finally {
      setResumeBusy(false);
    }
  };

  const downloadResumePdf = async () => {
    if (!uploadedResume) return;
    try {
      const blob = await apiBlobRequest(`/resume/uploaded/${uploadedResume.id}/download`, { token });
      const objectUrl = URL.createObjectURL(blob);
      const anchor = document.createElement("a");
      anchor.href = objectUrl;
      anchor.download = uploadedResume.original_filename || "resume.pdf";
      document.body.appendChild(anchor);
      anchor.click();
      anchor.remove();
      window.setTimeout(() => URL.revokeObjectURL(objectUrl), 30000);
    } catch (err) {
      setError(err.message);
    }
  };

  const deleteUploadedResume = async () => {
    if (!uploadedResume || !window.confirm("Delete your uploaded PDF resume?")) return;
    setDeletingUploadedResume(true);
    try {
      await apiRequest(`/resume/uploaded/${uploadedResume.id}`, { token, method: "DELETE" });
      notify("Uploaded PDF resume deleted.");
      await loadPage("profile");
    } catch (err) {
      setError(err.message);
    } finally {
      setDeletingUploadedResume(false);
    }
  };

  const deleteResume = async (id) => {
    if (!window.confirm("Remove this resume record?")) return;
    setDeletingResumeId(id);
    try {
      await apiRequest(`/resume/${id}`, { token, method: "DELETE" });
      notify("Resume record removed.");
      await loadPage("profile");
    } catch (err) {
      setError(err.message);
    } finally {
      setDeletingResumeId(null);
    }
  };

  const tabs = [
    ["profile", "Profile"],
    ["education", "Education"],
    ["skills", "Skills"],
    ["resume", "Resume"],
  ];

  return <>
    <div className="page-intro">
      <div><h2>Student information</h2><p>Manage your profile, academic history, skills and resume details.</p></div>
      <span className="subtle-count">{profile ? "Profile created" : "Profile setup required"}</span>
    </div>

    <div className="profile-tabs" role="tablist" aria-label="Student information sections">
      {tabs.map(([id, label]) => (
        <button key={id} type="button" role="tab" aria-selected={section === id}
          className={`profile-tab ${section === id ? "active" : ""}`} onClick={() => setSection(id)}>
          {label}
          {id === "education" && <span>{educationRows.length}</span>}
          {id === "skills" && <span>{skillRows.length}</span>}
          {id === "resume" && <span>{resumeRows.length + (uploadedResume ? 1 : 0)}</span>}
        </button>
      ))}
    </div>

    {section === "profile" && <>
      <form className="form-card profile-form" onSubmit={saveProfile}>
        <div className="form-section-title"><div className="form-section-icon">◎</div><div><strong>Personal and academic profile</strong><span>College, branch and professional links used by the placement portal.</span></div></div>
        <div className="form-grid">
          <Field label="College name"><input required value={profileForm.college} onChange={(e) => setProfileForm((old) => ({ ...old, college: e.target.value }))}/></Field>
          <Field label="Branch"><input required value={profileForm.branch} onChange={(e) => setProfileForm((old) => ({ ...old, branch: e.target.value }))} placeholder="Computer Science and Engineering"/></Field>
          <Field label="Graduation year"><input required value={profileForm.year} onChange={(e) => setProfileForm((old) => ({ ...old, year: e.target.value }))} placeholder="2028"/></Field>
          <Field label="Skills summary"><input required value={profileForm.skills} onChange={(e) => setProfileForm((old) => ({ ...old, skills: e.target.value }))} placeholder="Python, Java, SQL"/></Field>
          <Field label="LinkedIn URL (optional)"><input type="url" value={profileForm.linkedin} onChange={(e) => setProfileForm((old) => ({ ...old, linkedin: e.target.value }))} placeholder="https://linkedin.com/in/your-username"/></Field>
          <Field label="GitHub URL (optional)"><input type="url" value={profileForm.github} onChange={(e) => setProfileForm((old) => ({ ...old, github: e.target.value }))} placeholder="https://github.com/your-username"/></Field>
        </div>
        <div className="form-actions"><span className="muted-help">LinkedIn and GitHub are optional. Leave either field blank when not available.</span><button className="primary-button" disabled={profileBusy}>{profileBusy ? "Saving…" : "Save profile →"}</button></div>
      </form>
    </>}

    {section === "education" && <div className="profile-section-grid">
      <form className="form-card profile-record-form" onSubmit={saveEducation}>
        <div className="form-section-title"><div className="form-section-icon">▤</div><div><strong>{editingEducationId ? "Edit education record" : "Add education record"}</strong><span>Store each qualification separately.</span></div></div>
        <div className="form-stack">
          <Field label="Degree / qualification"><input required value={educationForm.degree} onChange={(e) => setEducationForm((old) => ({ ...old, degree: e.target.value }))} placeholder="B.Tech in Computer Science"/></Field>
          <Field label="College / institution"><input required value={educationForm.college} onChange={(e) => setEducationForm((old) => ({ ...old, college: e.target.value }))} placeholder="College or university name"/></Field>
          <Field label="Study period / year"><input required value={educationForm.year} onChange={(e) => setEducationForm((old) => ({ ...old, year: e.target.value }))} placeholder="2024–2028"/></Field>
          <Field label="CGPA / percentage"><input required value={educationForm.cgpa} onChange={(e) => setEducationForm((old) => ({ ...old, cgpa: e.target.value }))} placeholder="9.17"/></Field>
          <div className="form-grid">
            <Field label="Graduation year"><input required type="number" min="2000" max="2100" value={educationForm.graduation_year} onChange={(e) => setEducationForm((old) => ({ ...old, graduation_year: e.target.value }))}/></Field>
            <Field label="Active backlogs"><input required type="number" min="0" step="1" value={educationForm.active_backlogs} onChange={(e) => setEducationForm((old) => ({ ...old, active_backlogs: e.target.value }))}/></Field>
          </div>
        </div>
        <div className="form-actions"><span className="muted-help">Enter the latest confirmed academic details.</span><div className="form-button-row">{editingEducationId && <button type="button" className="secondary-button" onClick={() => { setEditingEducationId(null); setEducationForm(emptyEducation); }}>Cancel</button>}<button className="primary-button" disabled={educationBusy}>{educationBusy ? "Saving…" : editingEducationId ? "Update record" : "Add education"}</button></div></div>
      </form>
      <section className="form-card profile-record-list">
        <div className="section-heading-row"><div><span className="eyebrow">ACADEMIC HISTORY</span><h2>Saved records</h2></div><span className="subtle-count">{educationRows.length} records</span></div>
        {educationRows.length ? educationRows.map((row) => <div className="profile-record-item" key={row.id}>
          <div><strong>{row.degree}</strong><span>{row.college}</span><small>{row.year} · Graduation {row.graduation_year ?? "—"} · CGPA {row.cgpa ?? "—"} · Backlogs {row.active_backlogs ?? "—"}</small></div>
          <div className="record-actions"><button className="small-action" onClick={() => editEducation(row)}>Edit</button><button className="small-action danger-action" onClick={() => deleteEducation(row.id)}>Delete</button></div>
        </div>) : <p className="empty-inline">No education records have been added yet.</p>}
      </section>
    </div>}

    {section === "skills" && <div className="profile-section-grid skills-section-grid">
      <form className="form-card profile-record-form" onSubmit={addSkill}>
        <div className="form-section-title"><div className="form-section-icon">✦</div><div><strong>Add a skill</strong><span>Keep skills as separate searchable records.</span></div></div>
        <div className="form-stack"><Field label="Skill name"><input required value={skillName} onChange={(e) => setSkillName(e.target.value)} placeholder="Python, Java, SQL, React…"/></Field><button className="primary-button" disabled={skillBusy}>{skillBusy ? "Adding…" : "Add skill →"}</button></div>
        <p className="muted-help">To change a skill name, remove the old record and add the corrected name.</p>
      </form>
      <section className="form-card profile-record-list">
        <div className="section-heading-row"><div><span className="eyebrow">YOUR SKILLS</span><h2>Skill list</h2></div><span className="subtle-count">{skillRows.length} skills</span></div>
        {skillRows.length ? <div className="skill-chip-list">{skillRows.map((row) => <div className="skill-chip" key={row.id}><span>{row.skill_name}</span><button type="button" aria-label={`Remove ${row.skill_name}`} disabled={deletingSkillId === row.id} onClick={() => deleteSkill(row.id)}>{deletingSkillId === row.id ? "…" : "×"}</button></div>)}</div> : <p className="empty-inline">No skills added yet.</p>}
      </section>
    </div>}

    {section === "resume" && <div className="profile-section-grid skills-section-grid">
      <form className="form-card profile-record-form" onSubmit={uploadResumePdf}>
        <div className="form-section-title"><div className="form-section-icon">▧</div><div><strong>{uploadedResume ? "Replace your PDF resume" : "Upload your PDF resume"}</strong><span>Select a PDF directly from your device.</span></div></div>
        <div className="form-stack">
          <Field label="Resume PDF">
            <input id="resume-pdf-input" type="file" accept=".pdf,application/pdf" required onChange={(e) => setResumeFile(e.target.files?.[0] || null)}/>
          </Field>
          {resumeFile && <p className="muted-help">Selected: {resumeFile.name} · {(resumeFile.size / (1024 * 1024)).toFixed(2)} MB</p>}
          <button className="primary-button" disabled={resumeBusy || !resumeFile}>{resumeBusy ? "Uploading…" : uploadedResume ? "Replace PDF resume →" : "Upload PDF resume →"}</button>
        </div>
        <p className="muted-help">PDF only · Maximum size 5 MB. Uploading a new PDF replaces your current uploaded resume.</p>
      </form>
      <section className="form-card profile-record-list">
        <div className="section-heading-row"><div><span className="eyebrow">RESUME LIBRARY</span><h2>Uploaded resume</h2></div><span className="subtle-count">{uploadedResume ? "1 PDF" : "No PDF"}</span></div>
        {uploadedResume ? <div className="profile-record-item">
          <div><strong>{uploadedResume.original_filename}</strong><span>Private PDF · {(uploadedResume.file_size / (1024 * 1024)).toFixed(2)} MB</span><small>Uploaded {formatDate(uploadedResume.uploaded_at, true)}</small></div>
          <div className="record-actions"><button className="small-action" onClick={downloadResumePdf}>Download</button><button className="small-action danger-action" disabled={deletingUploadedResume} onClick={deleteUploadedResume}>{deletingUploadedResume ? "Removing…" : "Delete"}</button></div>
        </div> : <p className="empty-inline">No PDF uploaded yet. Choose a file to add your resume.</p>}
        {resumeRows.length > 0 && <div className="legacy-resume-list"><div className="section-heading-row"><div><span className="eyebrow">EXISTING LINKS</span><h3>Previously saved resume links</h3></div></div>
          {resumeRows.map((row) => <div className="profile-record-item" key={row.id}><div><strong>{row.resume_name}</strong><span>Legacy saved link</span><small><a href={row.resume_link} target="_blank" rel="noopener noreferrer">Open link ↗</a></small></div><div className="record-actions"><button className="small-action danger-action" disabled={deletingResumeId === row.id} onClick={() => deleteResume(row.id)}>{deletingResumeId === row.id ? "Removing…" : "Remove link"}</button></div></div>)}
        </div>}
      </section>
    </div>}
  </>;
}

function AdminDashboard({ data }) {
  const apps = data?.applications_by_status || {};
  return <><div className="welcome-banner admin-banner"><div><span className="eyebrow light-eyebrow">PLACEMENT CELL CONTROL ROOM</span><h2>Manage the placement lifecycle.</h2><p>Monitor students, drives, opportunities and candidate progress.</p></div><div className="banner-graphic"><div className="orbit orbit-one"/><div className="orbit orbit-two"/><div className="orbit-center">P</div></div></div>
    <div className="stats-grid admin-stats"><StatCard label="Registered students" value={data?.users?.students ?? 0} helper="Student accounts" icon="◎"/><StatCard label="Active cycles" value={data?.placement_cycles_active ?? 0} helper="Placement seasons" icon="◷"/><StatCard label="Published drives" value={data?.recruitment_drives_published ?? 0} helper="Open for applications" icon="▤"/><StatCard label="Open jobs" value={data?.open_jobs ?? 0} helper="Available positions" icon="⌕"/><StatCard label="Total applications" value={data?.total_applications ?? 0} helper="All candidate records" icon="▣"/><StatCard label="Upcoming rounds" value={data?.upcoming_rounds ?? 0} helper="Scheduled assessment rounds" icon="◉"/></div>
    <div className="section-heading-row"><div><span className="eyebrow">RECRUITMENT PIPELINE</span><h2>Applications by status</h2></div></div><div className="status-summary">{Object.entries(apps).map(([status, count]) => <div key={status}><StatusPill status={status}/><strong>{count}</strong></div>)}</div>
  </>;
}

function AdminApplications({ data, updateApplicationStatus, viewStudentResume }) {
  const rows = Array.isArray(data) ? data : [];
  const [drafts, setDrafts] = useState({});
  return <><div className="page-intro"><div><h2>Candidate applications</h2><p>Review applicants and update their recruitment progress.</p></div><span className="subtle-count">{rows.length} records</span></div>
    {rows.length ? <div className="table-card"><div className="table-wrap"><table><thead><tr><th>Candidate</th><th>Company / drive</th><th>Position</th><th>Current status</th><th>Resume</th><th>Update status</th></tr></thead><tbody>{rows.map((app) => <tr key={app.application_id}><td><strong>{app.student_name}</strong><small>{app.student_email}</small></td><td><strong>{app.company || "—"}</strong><small>{app.recruitment_drive || "—"}</small></td><td>{app.role}</td><td><StatusPill status={app.status}/></td><td>{app.student_id ? <button className="small-action" onClick={() => viewStudentResume(app.student_id)}>View PDF</button> : "—"}</td><td><div className="status-editor"><select value={drafts[app.application_id] || app.status} onChange={(e) => setDrafts((old) => ({ ...old, [app.application_id]: e.target.value }))}>{APPLICATION_STATUSES.map((status) => <option key={status}>{status}</option>)}</select><button className="small-action" onClick={() => updateApplicationStatus(app.application_id, drafts[app.application_id] || app.status)}>Save</button></div></td></tr>)}</tbody></table></div></div> : <EmptyState title="No applications received" description="Applications will appear here as students apply to published jobs."/>}
  </>;
}

function AdminRoundsPage({ data, token, loadPage, setError, notify, selectedDriveId, setSelectedDriveId, roundCandidates, setRoundCandidates }) {
  const drives = data?.drives || [];
  const rounds = data?.rounds || [];
  const [form, setForm] = useState({ name: "", sequence: "1", description: "", scheduled_at: "", scheduled_end: "", venue: "", meeting_link: "", status: "Scheduled" });
  const [busy, setBusy] = useState(false);
  const [expandedRound, setExpandedRound] = useState(null);
  const selectedDrive = selectedDriveId || data?.driveId || "";

  const selectDrive = async (value) => { setSelectedDriveId(value); await loadPage("admin-rounds", { driveId: value }); };
  const createRound = async (event) => {
    event.preventDefault();
    if (!selectedDrive) return setError("Select a recruitment drive first.");
    setBusy(true);
    const payload = { ...form, sequence: Number(form.sequence), scheduled_at: form.scheduled_at ? `${form.scheduled_at}:00` : null, scheduled_end: form.scheduled_end ? `${form.scheduled_end}:00` : null, venue: form.venue || null, meeting_link: form.meeting_link || null, description: form.description || null };
    try {
      await apiRequest(`/admin/recruitment-drives/${selectedDrive}/rounds`, { token, method: "POST", body: payload });
      notify("Placement round created.");
      setForm({ name: "", sequence: String(rounds.length + 2), description: "", scheduled_at: "", scheduled_end: "", venue: "", meeting_link: "", status: "Scheduled" });
      await loadPage("admin-rounds", { driveId: selectedDrive });
    } catch (err) { setError(err.message); }
    finally { setBusy(false); }
  };
  const viewCandidates = async (roundId) => {
    if (expandedRound === roundId) return setExpandedRound(null);
    try {
      const candidates = await apiRequest(`/admin/rounds/${roundId}/candidates`, { token });
      setRoundCandidates((old) => ({ ...old, [roundId]: candidates }));
      setExpandedRound(roundId);
    } catch (err) { setError(err.message); }
  };
  const assignAll = async (roundId) => {
    try { const result = await apiRequest(`/admin/rounds/${roundId}/assign-candidates`, { token, method: "POST" }); notify(`Assignment completed. ${result.assigned_count ?? ""} candidates assigned.`); await loadPage("admin-rounds", { driveId: selectedDrive }); }
    catch (err) { setError(err.message); }
  };
  const setRoundStatus = async (round, status) => {
    try {
      const payload = { name: round.name, sequence: round.sequence, description: round.description, scheduled_at: round.scheduled_at, scheduled_end: round.scheduled_end, venue: round.venue, meeting_link: round.meeting_link, status };
      await apiRequest(`/admin/rounds/${round.id}`, { token, method: "PUT", body: payload });
      notify(`Round status changed to ${status}.`); await loadPage("admin-rounds", { driveId: selectedDrive });
    } catch (err) { setError(err.message); }
  };
  return <><div className="page-intro"><div><h2>Configure assessment stages</h2><p>Create rounds, assign eligible candidates and review attendance and results.</p></div><span className="subtle-count">{rounds.length} rounds</span></div>
    <div className="form-card drive-select-card"><Field label="Recruitment drive"><select value={selectedDrive} onChange={(e) => selectDrive(e.target.value)}><option value="">Choose a drive</option>{drives.map((drive) => <option key={drive.id} value={drive.id}>{drive.name} · {drive.company_name}</option>)}</select></Field></div>
    {selectedDrive && <div className="admin-round-layout"><section className="timeline-panel"><div className="section-heading-row compact-heading"><div><h3>Rounds in this drive</h3><p>Progression follows the previous round's Pass result.</p></div></div>{rounds.length ? rounds.map((round) => <div className="admin-round-item" key={round.id}><div className="round-sequence">{round.sequence}</div><div className="admin-round-copy"><strong>{round.name}</strong><span>{formatDate(round.scheduled_at, true)} · {round.venue || "Venue to be announced"}</span><div className="admin-round-actions"><StatusPill status={round.status}/><button className="text-action" onClick={() => viewCandidates(round.id)}>{expandedRound === round.id ? "Hide candidates" : "Candidates"}</button><button className="text-action" onClick={() => assignAll(round.id)}>Assign eligible</button><select aria-label="Round status" value={round.status} onChange={(e) => setRoundStatus(round, e.target.value)}><option>Draft</option><option>Scheduled</option><option>In Progress</option><option>Completed</option><option>Cancelled</option></select></div>{expandedRound === round.id && <div className="candidate-list">{(roundCandidates[round.id] || []).length ? roundCandidates[round.id].map((candidate) => <CandidateAssessment key={candidate.application_id} candidate={candidate} roundId={round.id} token={token} setError={setError} notify={notify} afterSave={async () => { const refreshed = await apiRequest(`/admin/rounds/${round.id}/candidates`, { token }); setRoundCandidates((old) => ({ ...old, [round.id]: refreshed })); }}/>) : <p>No candidates assigned to this round yet.</p>}</div>}</div></div>) : <p className="empty-inline">No rounds have been created for this drive.</p>}</section>
      <form className="form-card create-round-card" onSubmit={createRound}><div className="form-section-title"><div className="form-section-icon">＋</div><div><strong>Create a placement round</strong><span>Choose a clear sequence and schedule.</span></div></div><div className="form-stack"><Field label="Round name"><input required minLength={3} value={form.name} onChange={(e) => setForm({ ...form, name: e.target.value })} placeholder="Technical Interview"/></Field><Field label="Sequence number"><input required type="number" min="1" value={form.sequence} onChange={(e) => setForm({ ...form, sequence: e.target.value })}/></Field><Field label="Description"><textarea rows="2" value={form.description} onChange={(e) => setForm({ ...form, description: e.target.value })}/></Field><Field label="Start date and time"><input type="datetime-local" required value={form.scheduled_at} onChange={(e) => setForm({ ...form, scheduled_at: e.target.value })}/></Field><Field label="End date and time"><input type="datetime-local" value={form.scheduled_end} onChange={(e) => setForm({ ...form, scheduled_end: e.target.value })}/></Field><Field label="Venue"><input value={form.venue} onChange={(e) => setForm({ ...form, venue: e.target.value })} placeholder="Online / College auditorium"/></Field><Field label="Meeting link"><input type="url" value={form.meeting_link} onChange={(e) => setForm({ ...form, meeting_link: e.target.value })}/></Field></div><button className="primary-button wide-button" disabled={busy}>{busy ? "Creating…" : "Create round →"}</button></form></div>}
    {!selectedDrive && <EmptyState title="Select a recruitment drive" description="Choose a drive to view, create and manage its assessment rounds."/>}
  </>;
}

function AdminEligibilityManager({ data, token, loadPage, notify, setError }) {
  const jobs = data?.rows || [];
  const [selectedJobId, setSelectedJobId] = useState("");
  const selectedJob = jobs.find((job) => String(job.id) === selectedJobId);
  const eligibility = selectedJob ? data?.eligibility?.[selectedJob.id] : null;

  return <section className="form-card eligibility-editor">
    <div className="form-section-title">
      <div className="form-section-icon">✓</div>
      <div><strong>Job eligibility criteria</strong><span>Set the academic requirements checked before applications are accepted.</span></div>
    </div>
    {jobs.length ? <>
      <Field label="Job position">
        <select aria-label="Job position for eligibility" value={selectedJobId} onChange={(event) => setSelectedJobId(event.target.value)}>
          <option value="">Select a job</option>
          {jobs.map((job) => <option key={job.id} value={job.id}>{job.role} · {job.company || "Company"}</option>)}
        </select>
      </Field>
      {selectedJob && <AdminEligibilityEditor
        key={`${selectedJob.id}-${eligibility?.id || "new"}-${eligibility?.updated_at || ""}`}
        job={selectedJob}
        eligibility={eligibility}
        token={token}
        loadPage={loadPage}
        notify={notify}
        setError={setError}
      />}
    </> : <p className="empty-inline">Create a job position before configuring eligibility.</p>}
  </section>;
}

function AdminEligibilityEditor({ job, eligibility, token, loadPage, notify, setError }) {
  const [courses, setCourses] = useState((eligibility?.eligible_courses || []).join(", "));
  const [branches, setBranches] = useState((eligibility?.eligible_branches || []).join(", "));
  const [graduationYears, setGraduationYears] = useState((eligibility?.graduation_years || []).join(", "));
  const [minCgpa, setMinCgpa] = useState(eligibility?.min_cgpa ?? "");
  const [maxBacklogs, setMaxBacklogs] = useState(eligibility?.max_active_backlogs ?? "");
  const [notes, setNotes] = useState(eligibility?.notes || "");
  const [busy, setBusy] = useState(false);

  const submit = async (event) => {
    event.preventDefault();
    const years = graduationYears.split(",").map((value) => value.trim()).filter(Boolean);
    if (years.some((year) => !/^\d{4}$/.test(year))) {
      setError("Enter graduation years as four-digit years separated by commas.");
      return;
    }

    const payload = {
      eligible_courses: courses.split(",").map((value) => value.trim()).filter(Boolean),
      eligible_branches: branches.split(",").map((value) => value.trim()).filter(Boolean),
      graduation_years: years.map(Number),
      min_cgpa: minCgpa === "" ? null : Number(minCgpa),
      max_active_backlogs: maxBacklogs === "" ? null : Number(maxBacklogs),
      notes: notes.trim() || null,
    };
    setBusy(true);
    try {
      await apiRequest(`/admin/jobs/${job.id}/eligibility`, {
        token,
        method: eligibility ? "PUT" : "POST",
        body: payload,
      });
      notify(eligibility ? "Job eligibility updated." : "Job eligibility created.");
      await loadPage("admin-jobs");
    } catch (err) {
      setError(err.message);
    } finally {
      setBusy(false);
    }
  };

  const remove = async () => {
    if (!window.confirm(`Remove eligibility criteria for "${job.role}"?`)) return;
    setBusy(true);
    try {
      await apiRequest(`/admin/jobs/${job.id}/eligibility`, { token, method: "DELETE" });
      notify("Job eligibility removed.");
      await loadPage("admin-jobs");
    } catch (err) {
      setError(err.message);
    } finally {
      setBusy(false);
    }
  };

  return <form className="form-stack eligibility-fields" onSubmit={submit}>
    <p className="muted-copy">{eligibility ? "Criteria are configured. Save to replace the current requirements." : "No criteria are configured; eligible courses and branches may be left blank."}</p>
    <Field label="Eligible courses"><input value={courses} onChange={(event) => setCourses(event.target.value)} placeholder="B.Tech, B.Sc"/></Field>
    <Field label="Eligible branches"><input value={branches} onChange={(event) => setBranches(event.target.value)} placeholder="Computer Science, Electronics"/></Field>
    <Field label="Graduation years"><input value={graduationYears} onChange={(event) => setGraduationYears(event.target.value)} placeholder="2026, 2027"/></Field>
    <div className="inline-form-fields">
      <Field label="Minimum CGPA"><input type="number" min="0" max="10" step="0.01" value={minCgpa} onChange={(event) => setMinCgpa(event.target.value)}/></Field>
      <Field label="Maximum active backlogs"><input type="number" min="0" max="50" value={maxBacklogs} onChange={(event) => setMaxBacklogs(event.target.value)}/></Field>
    </div>
    <Field label="Eligibility notes"><textarea rows="2" value={notes} onChange={(event) => setNotes(event.target.value)}/></Field>
    <div className="form-button-row">
      <button className="primary-button" disabled={busy}>{busy ? "Saving…" : eligibility ? "Update criteria →" : "Save criteria →"}</button>
      {eligibility && <button className="secondary-button" type="button" disabled={busy} onClick={remove}>Remove criteria</button>}
    </div>
  </form>;
}

function AdminEntityPage({ kind, data, token, loadPage, notify, setError }) {
  const configs = {
    companies: {
      title: "Companies", subtitle: "Recruiters registered by the placement cell.", rows: Array.isArray(data) ? data : [],
      columns: ["id", "name", "website", "contact_person", "contact_email", "is_active"],
      empty: { name: "", description: "", website: "", contact_person: "", contact_email: "" },
      endpoint: "/admin/companies", singular: "company",
    },
    cycles: {
      title: "Placement cycles", subtitle: "Academic placement seasons managed by your team.", rows: Array.isArray(data) ? data : [],
      columns: ["id", "name", "academic_year", "start_date", "end_date", "status"],
      empty: { name: "", academic_year: "2026-2027", description: "", start_date: "", end_date: "", status: "Draft" },
      endpoint: "/admin/cycles", singular: "placement cycle",
    },
    drives: {
      title: "Recruitment drives", subtitle: "Company hiring drives within placement cycles.", rows: data?.rows || [],
      columns: ["id", "name", "company_name", "cycle_name", "application_start_date", "application_deadline", "status"],
      empty: { company_id: "", placement_cycle_id: "", name: "", description: "", application_start_date: "", application_deadline: "", status: "Draft" },
      endpoint: "/admin/recruitment-drives", singular: "recruitment drive",
    },
    jobs: {
      title: "Job positions", subtitle: "Jobs attached to recruitment drives.", rows: data?.rows || [],
      columns: ["id", "role", "company", "recruitment_drive", "package", "location", "status"],
      empty: { recruitment_drive_id: "", role: "", package: "", location: "", status: "Open" },
      endpoint: "/admin/jobs", singular: "job position",
    },
  };
  const config = configs[kind];
  const [form, setForm] = useState(config.empty);
  const [busy, setBusy] = useState(false);
  const [editingId, setEditingId] = useState(null);
  const update = (key, value) => setForm((old) => ({ ...old, [key]: value }));
  const resetForm = () => { setForm(config.empty); setEditingId(null); };
  const dateInput = (value) => value ? String(value).slice(0, 10) : "";

  const beginEdit = (row) => {
    setEditingId(row.id);
    if (kind === "companies") {
      setForm({ name: row.name || "", description: row.description || "", website: row.website || "", contact_person: row.contact_person || "", contact_email: row.contact_email || "" });
    } else if (kind === "cycles") {
      setForm({ name: row.name || "", academic_year: row.academic_year || "", description: row.description || "", start_date: dateInput(row.start_date), end_date: dateInput(row.end_date), status: row.status || "Draft" });
    } else if (kind === "drives") {
      setForm({ company_id: String(row.company_id ?? ""), placement_cycle_id: String(row.placement_cycle_id ?? ""), name: row.name || "", description: row.description || "", application_start_date: dateInput(row.application_start_date), application_deadline: dateInput(row.application_deadline), status: row.status || "Draft" });
    } else {
      setForm({ recruitment_drive_id: String(row.recruitment_drive_id ?? ""), role: row.role || "", package: row.package || "", location: row.location || "", status: row.status || "Open" });
    }
    setError("");
  };

  const submit = async (event) => {
    event.preventDefault();
    setBusy(true);
    const payload = { ...form };
    if (kind === "drives") {
      payload.company_id = Number(payload.company_id);
      payload.placement_cycle_id = Number(payload.placement_cycle_id);
      payload.application_start_date = payload.application_start_date || null;
      payload.application_deadline = payload.application_deadline || null;
    }
    if (kind === "jobs") {
      if (editingId === null) payload.recruitment_drive_id = Number(payload.recruitment_drive_id);
      else delete payload.recruitment_drive_id; // Existing backend update schema updates the position, not its parent drive.
    }
    if (kind === "cycles") {
      payload.start_date = payload.start_date || null;
      payload.end_date = payload.end_date || null;
    }
    try {
      const url = editingId === null ? config.endpoint : `${config.endpoint}/${editingId}`;
      await apiRequest(url, { token, method: editingId === null ? "POST" : "PUT", body: payload });
      notify(editingId === null ? `${config.singular} created successfully.` : `${config.singular} updated successfully.`);
      resetForm();
      await loadPage(`admin-${kind}`);
    } catch (err) { setError(err.message); }
    finally { setBusy(false); }
  };

  const removeRow = async (row) => {
    const label = row.name || row.role || `${config.singular} #${row.id}`;
    if (!window.confirm(`Delete ${config.singular} "${label}"? This cannot be undone.`)) return;
    try {
      await apiRequest(`${config.endpoint}/${row.id}`, { token, method: "DELETE" });
      notify(`${config.singular} deleted successfully.`);
      if (editingId === row.id) resetForm();
      await loadPage(`admin-${kind}`);
    } catch (err) { setError(err.message); }
  };

  return <>
    <div className="page-intro"><div><h2>{config.title}</h2><p>{config.subtitle}</p></div><span className="subtle-count">{config.rows.length} records</span></div>
    <div className="admin-entity-layout">
      <div>{config.rows.length ? <div className="table-card"><div className="table-wrap"><table><thead><tr>{config.columns.map((column) => <th key={column}>{humanize(column)}</th>)}<th>Actions</th></tr></thead><tbody>{config.rows.map((row, index) => <tr key={row.id ?? index}>{config.columns.map((column) => <td key={column}>{typeof row[column] === "boolean" ? row[column] ? "Yes" : "No" : row[column] ?? "—"}</td>)}<td><div className="record-actions"><button className="small-action" onClick={() => beginEdit(row)}>Edit</button><button className="small-action danger-action" onClick={() => removeRow(row)}>Delete</button></div></td></tr>)}</tbody></table></div></div> : <EmptyState title={`No ${config.title.toLowerCase()} yet`} description="Create the first record using the form."/>}</div>
      <form className="form-card entity-form" onSubmit={submit}>
        <div className="form-section-title"><div className="form-section-icon">{editingId === null ? "＋" : "✎"}</div><div><strong>{editingId === null ? `Add ${config.singular}` : `Edit ${config.singular}`}</strong><span>{editingId === null ? "New records are stored in your backend database." : `Editing record #${editingId}. Save your changes when ready.`}</span></div></div>
        <div className="form-stack">
          {kind === "companies" && <>
            <Field label="Company name"><input required value={form.name} onChange={(e) => update("name", e.target.value)}/></Field>
            <Field label="Description"><textarea rows="2" value={form.description} onChange={(e) => update("description", e.target.value)}/></Field>
            <Field label="Website"><input type="url" value={form.website} onChange={(e) => update("website", e.target.value)}/></Field>
            <Field label="Contact person"><input value={form.contact_person} onChange={(e) => update("contact_person", e.target.value)}/></Field>
            <Field label="Contact email"><input type="email" value={form.contact_email} onChange={(e) => update("contact_email", e.target.value)}/></Field>
          </>}
          {kind === "cycles" && <>
            <Field label="Cycle name"><input required minLength={3} value={form.name} onChange={(e) => update("name", e.target.value)} placeholder="Campus Placements 2026-27"/></Field>
            <Field label="Academic year"><input required value={form.academic_year} onChange={(e) => update("academic_year", e.target.value)}/></Field>
            <Field label="Description"><textarea rows="2" value={form.description} onChange={(e) => update("description", e.target.value)}/></Field>
            <Field label="Start date"><input type="date" value={form.start_date} onChange={(e) => update("start_date", e.target.value)}/></Field>
            <Field label="End date"><input type="date" value={form.end_date} onChange={(e) => update("end_date", e.target.value)}/></Field>
            <Field label="Status"><select value={form.status} onChange={(e) => update("status", e.target.value)}><option>Draft</option><option>Active</option><option>Completed</option><option>Cancelled</option></select></Field>
          </>}
          {kind === "drives" && <>
            <Field label="Company"><select required value={form.company_id} onChange={(e) => update("company_id", e.target.value)}><option value="">Select company</option>{(data?.companies || []).map((row) => <option key={row.id} value={row.id}>{row.name}</option>)}</select></Field>
            <Field label="Placement cycle"><select required value={form.placement_cycle_id} onChange={(e) => update("placement_cycle_id", e.target.value)}><option value="">Select cycle</option>{(data?.cycles || []).map((row) => <option key={row.id} value={row.id}>{row.name}</option>)}</select></Field>
            <Field label="Drive name"><input required minLength={3} value={form.name} onChange={(e) => update("name", e.target.value)}/></Field>
            <Field label="Description"><textarea rows="2" value={form.description} onChange={(e) => update("description", e.target.value)}/></Field>
            <Field label="Application start"><input type="date" value={form.application_start_date} onChange={(e) => update("application_start_date", e.target.value)}/></Field>
            <Field label="Application deadline"><input type="date" value={form.application_deadline} onChange={(e) => update("application_deadline", e.target.value)}/></Field>
            <Field label="Status"><select value={form.status} onChange={(e) => update("status", e.target.value)}><option>Draft</option><option>Published</option><option>Closed</option><option>Cancelled</option></select></Field>
          </>}
          {kind === "jobs" && <>
            <Field label="Recruitment drive"><select required disabled={editingId !== null} value={form.recruitment_drive_id} onChange={(e) => update("recruitment_drive_id", e.target.value)}><option value="">Select drive</option>{(data?.drives || []).map((row) => <option key={row.id} value={row.id}>{row.name} · {row.company_name || row.company}</option>)}</select></Field>
            <Field label="Job role"><input required value={form.role} onChange={(e) => update("role", e.target.value)} placeholder="Software Engineer"/></Field>
            <Field label="Package"><input required value={form.package} onChange={(e) => update("package", e.target.value)} placeholder="6 LPA"/></Field>
            <Field label="Location"><input required value={form.location} onChange={(e) => update("location", e.target.value)} placeholder="Pune"/></Field>
            <Field label="Status"><select value={form.status} onChange={(e) => update("status", e.target.value)}><option>Open</option><option>Closed</option><option>Cancelled</option></select></Field>
          </>}
        </div>
        <div className="form-button-row"><button className="primary-button wide-button" disabled={busy}>{busy ? "Saving…" : editingId === null ? "Create record →" : "Save changes →"}</button>{editingId !== null && <button type="button" className="small-action" onClick={resetForm}>Cancel edit</button>}</div>
      </form>
    </div>
  </>;
}

function AdminStudents({ data, token, user, loadPage, notify, setError }) {
  const rows = Array.isArray(data) ? data : [];
  const removeStudent = async (student) => {
    if (student.role !== "student") return;
    if (!window.confirm(`Delete student account for ${student.name || student.email}? This action cannot be undone.`)) return;
    try {
      await apiRequest(`/admin/users/${student.id}`, { token, method: "DELETE" });
      notify("Student account deleted.");
      await loadPage("admin-students");
    } catch (err) { setError(err.message); }
  };
  return <><div className="page-intro"><div><h2>Registered students</h2><p>View student accounts created in PlacementPilot. Accounts with applications or related records may be protected by database constraints.</p></div><span className="subtle-count">{rows.filter((row) => row.role === "student").length} students</span></div>
    {rows.length ? <div className="table-card"><div className="table-wrap"><table><thead><tr><th>ID</th><th>Name</th><th>Email</th><th>Role</th><th>Action</th></tr></thead><tbody>{rows.map((row) => <tr key={row.id}><td>{row.id}</td><td>{row.name || "—"}</td><td>{row.email}</td><td>{row.role}</td><td>{row.role === "student" && row.id !== user?.id ? <button className="small-action danger-action" onClick={() => removeStudent(row)}>Delete account</button> : "—"}</td></tr>)}</tbody></table></div></div> : <EmptyState title="No users registered" description="Student accounts will appear here after signup."/>}
  </>;
}

const DEFAULT_PLACEMENT_POLICY = {
  max_active_applications: 1,
  allow_reapply_after_rejection: true,
  allow_reapply_after_withdrawal: true,
  allow_multiple_positions_same_drive: false,
  allow_withdraw_after_shortlisting: false,
  allow_applications_after_offer_release: true,
  lock_after_offer_acceptance: true,
  allow_reapply_after_offer_declined: true,
};

function policyFormValues(policy) {
  if (!policy) return DEFAULT_PLACEMENT_POLICY;
  return {
    max_active_applications: policy.max_active_applications ?? 1,
    allow_reapply_after_rejection: policy.allow_reapply_after_rejection ?? true,
    allow_reapply_after_withdrawal: policy.allow_reapply_after_withdrawal ?? true,
    allow_multiple_positions_same_drive: policy.allow_multiple_positions_same_drive ?? false,
    allow_withdraw_after_shortlisting: policy.allow_withdraw_after_shortlisting ?? false,
    allow_applications_after_offer_release: policy.allow_applications_after_offer_release ?? true,
    lock_after_offer_acceptance: policy.lock_after_offer_acceptance ?? true,
    allow_reapply_after_offer_declined: policy.allow_reapply_after_offer_declined ?? true,
  };
}

function AdminPolicyManager({ data, token, loadPage, notify, setError }) {
  const cycles = data?.cycles ?? EMPTY_ARRAY;
  const policies = data?.policies || {};
  const [cycleId, setCycleId] = useState("");
  const initialCycleId = cycles[0] ? String(cycles[0].id) : "";
  const [form, setForm] = useState(() => policyFormValues(policies[initialCycleId]));
  const [busy, setBusy] = useState(false);
  const selectedId = cycleId || (cycles[0] ? String(cycles[0].id) : "");
  const selectedPolicy = selectedId ? policies[selectedId] : null;
  const selectCycle = (id) => {
    setCycleId(id);
    setForm(policyFormValues(policies[id]));
  };
  const update = (key, value) => setForm((old) => ({ ...old, [key]: value }));
  const submit = async (event) => {
    event.preventDefault();
    if (!selectedId) return setError("Create a placement cycle before configuring policies.");
    setBusy(true);
    try {
      const method = selectedPolicy ? "PUT" : "POST";
      await apiRequest(`/admin/cycles/${selectedId}/policy`, { token, method, body: { ...form, max_active_applications: Number(form.max_active_applications) } });
      notify(selectedPolicy ? "Placement policy updated." : "Placement policy created.");
      await loadPage("admin-policies");
    } catch (err) { setError(err.message); }
    finally { setBusy(false); }
  };
  const toggles = [
    ["allow_reapply_after_rejection", "Allow reapplication after rejection"],
    ["allow_reapply_after_withdrawal", "Allow reapplication after withdrawal"],
    ["allow_multiple_positions_same_drive", "Allow multiple positions in one drive"],
    ["allow_withdraw_after_shortlisting", "Allow withdrawal after shortlisting"],
    ["allow_applications_after_offer_release", "Allow applications after an offer is released"],
    ["lock_after_offer_acceptance", "Lock further applications after offer acceptance"],
    ["allow_reapply_after_offer_declined", "Allow reapplication after declining an offer"],
  ];
  return <>
    <div className="page-intro"><div><h2>Placement policies</h2><p>Configure application limits and student reapplication rules for each placement cycle.</p></div><span className="subtle-count">{cycles.length} cycles</span></div>
    {!cycles.length ? <EmptyState title="Create a placement cycle first" description="Policy settings belong to a placement cycle. Create one under Placement cycles, then return here."/> : <div className="policy-layout">
      <form className="form-card policy-card" onSubmit={submit}>
        <div className="form-section-title"><div className="form-section-icon">⚙</div><div><strong>Cycle application rules</strong><span>These rules are applied by the backend when students apply for jobs.</span></div></div>
        <Field label="Placement cycle"><select value={selectedId} onChange={(e) => selectCycle(e.target.value)}>{cycles.map((cycle) => <option key={cycle.id} value={cycle.id}>{cycle.name} · {cycle.academic_year}</option>)}</select></Field>
        <Field label="Maximum active applications"><input type="number" min="1" max="50" required value={form.max_active_applications} onChange={(e) => update("max_active_applications", e.target.value)}/></Field>
        <div className="policy-toggle-list">{toggles.map(([key, label]) => <label className="policy-toggle" key={key}><input type="checkbox" checked={Boolean(form[key])} onChange={(e) => update(key, e.target.checked)}/><span>{label}</span></label>)}</div>
        <div className="form-button-row"><button className="primary-button" disabled={busy}>{busy ? "Saving…" : selectedPolicy ? "Save policy changes →" : "Create policy →"}</button><span className="muted-help">{selectedPolicy ? "Existing policy will be updated." : "No policy exists for this cycle yet."}</span></div>
      </form>
      <section className="form-card policy-card"><div className="section-heading-row"><div><span className="eyebrow">CURRENT CONFIGURATION</span><h2>{cycles.find((cycle) => String(cycle.id) === selectedId)?.name || "Selected cycle"}</h2></div><StatusPill status={selectedPolicy ? "Configured" : "Not configured"}/></div>
        <div className="policy-summary-row"><strong>Maximum active applications</strong><span>{selectedPolicy?.max_active_applications ?? DEFAULT_PLACEMENT_POLICY.max_active_applications}</span></div>
        {toggles.map(([key, label]) => <div className="policy-summary-row" key={key}><span>{label}</span><strong>{(selectedPolicy ? selectedPolicy[key] : DEFAULT_PLACEMENT_POLICY[key]) ? "Yes" : "No"}</strong></div>)}
      </section>
    </div>}
  </>;
}

function CandidateAssessment({ candidate, roundId, token, setError, notify, afterSave }) {
  const [attendance, setAttendance] = useState(candidate.attendance || "Pending");
  const [result, setResult] = useState(candidate.result || "Pending");
  const [score, setScore] = useState(candidate.score ?? "");
  const [feedback, setFeedback] = useState(candidate.feedback || "");
  const [busy, setBusy] = useState(false);
  const submit = async () => {
    setBusy(true);
    try {
      await apiRequest(`/admin/rounds/${roundId}/candidates/${candidate.application_id}/result`, {
        token, method: "PUT",
        body: { attendance, result, score: score === "" ? null : Number(score), feedback: feedback || null },
      });
      notify(`Updated ${candidate.student_name}'s round result.`);
      afterSave();
    } catch (err) { setError(err.message); }
    finally { setBusy(false); }
  };
  return <div className="candidate-assessment"><div className="candidate-summary"><strong>{candidate.student_name}</strong><span>{candidate.student_email} · {candidate.job_role}</span></div><div className="candidate-fields"><select value={attendance} onChange={(e) => setAttendance(e.target.value)}><option>Pending</option><option>Present</option><option>Absent</option></select><select value={result} onChange={(e) => setResult(e.target.value)}><option>Pending</option><option>Pass</option><option>Fail</option><option>On Hold</option></select><input type="number" min="0" max="100" step="0.5" placeholder="Score" value={score} onChange={(e) => setScore(e.target.value)}/><input placeholder="Feedback" value={feedback} onChange={(e) => setFeedback(e.target.value)}/><button className="small-action" disabled={busy} onClick={submit}>{busy ? "Saving" : "Save result"}</button></div></div>;
}


function StatCard({ label, value, helper, icon }) { return <div className="stat-card"><div className="stat-top"><span>{label}</span><div className="stat-icon">{icon}</div></div><strong>{value}</strong><small>{helper}</small></div>; }
function StatusPill({ status }) { return <span className={`status-pill ${statusClass(status)}`}>{status || "Pending"}</span>; }
function Field({ label, children }) { return <label className="field"><span>{label}</span>{children}</label>; }
function EmptyState({ title, description, onRefresh }) { return <div className="empty-state"><div className="empty-icon">⌁</div><h3>{title}</h3><p>{description}</p>{onRefresh && <button className="secondary-button" onClick={onRefresh}>Refresh</button>}</div>; }
function humanize(value) { return value.replaceAll("_", " ").replace(/\b\w/g, (letter) => letter.toUpperCase()); }

export default App;
