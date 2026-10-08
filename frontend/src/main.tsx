import { useEffect, useRef, useState } from 'react';
import type { FormEvent } from 'react';
import { createRoot } from 'react-dom/client';
import { Api, ApiError, errorMessage } from './api';
import type { Approval, ApprovalDetail, Identity, Run, RunDetail, Scenario, Step } from './api';
import './style.css';

const activeStates = new Set(['QUEUED', 'RUNNING', 'WAITING_APPROVAL']);
const pretty = (value: string) => value.toLowerCase().replaceAll('_', ' ').replaceAll('-', ' ');
const time = (value: number | null) =>
  value ? new Date(value * 1000).toLocaleString() : 'Not started';
const modeLabel = (mode: string) =>
  mode === 'authored_fixture'
    ? 'Scripted fixture · zero model trials'
    : mode === 'fresh_local_inference'
      ? 'Live local inference'
      : 'Execution mode unknown';

function Shield() {
  return (
    <svg viewBox="0 0 24 24" fill="none" aria-hidden="true">
      <path
        d="M12 3 4.5 6v6c0 4 4.5 7.5 7.5 9 3-1.5 7.5-5 7.5-9V6L12 3Z"
        stroke="currentColor"
        strokeWidth="1.6"
      />
      <path d="m8.5 12 2.3 2.3 4.7-4.8" stroke="currentColor" strokeWidth="1.6" />
    </svg>
  );
}
function Badge({ value }: { value: string }) {
  return <span className={`badge badge-${value.toLowerCase()}`}>{pretty(value)}</span>;
}
function Field({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <div className="field">
      <dt>{label}</dt>
      <dd>{children}</dd>
    </div>
  );
}
function App() {
  const [session, setSession] = useState<{ api: Api; identity: Identity } | null>(null);
  const [error, setError] = useState('');
  const [busy, setBusy] = useState(false);
  const credential = useRef<HTMLInputElement>(null);
  async function connect(event: FormEvent) {
    event.preventDefault();
    if (busy) return;
    const token = credential.current?.value.trim() ?? '';
    if (credential.current) credential.current.value = '';
    const api = new Api(token);
    setBusy(true);
    setError('');
    try {
      setSession({ api, identity: await api.get<Identity>('/api/identity') });
    } catch (error) {
      api.close();
      setError(errorMessage(error));
    } finally {
      setBusy(false);
    }
  }
  function logout(message = '') {
    session?.api.close();
    setSession(null);
    setError(message);
  }
  useEffect(() => {
    const clear = () => {
      session?.api.close();
      setSession(null);
    };
    const restored = (event: PageTransitionEvent) => {
      if (event.persisted) clear();
    };
    window.addEventListener('pagehide', clear);
    window.addEventListener('pageshow', restored);
    return () => {
      window.removeEventListener('pagehide', clear);
      window.removeEventListener('pageshow', restored);
    };
  }, [session]);
  return (
    <div className="app-shell">
      <header className="topbar">
        <a href="/" className="brand" aria-label="AgentGuard home">
          <span className="brand-mark">
            <Shield />
          </span>
          AgentGuard
          <span className="brand-divider" />{' '}
          <span className="brand-subtitle">Operator console</span>
        </a>
        <div className="header-meta">
          <span className="local-indicator">
            <i /> Local workspace
          </span>
          {session && (
            <button className="button subtle" onClick={() => logout()}>
              Disconnect
            </button>
          )}
        </div>
      </header>
      {session ? (
        <Console api={session.api} identity={session.identity} logout={logout} />
      ) : (
        <main className="login-layout">
          <section className="login-intro">
            <span className="eyebrow">SECURE AGENT EXECUTION</span>
            <h1>
              Useful agents.
              <br />
              Explicit boundaries.
            </h1>
            <p>
              Run a workplace task, inspect each policy decision, and review sensitive actions
              before they take effect.
            </p>
            <div className="boundary-flow">
              <span>Task</span>
              <b>→</b>
              <span>Policy</span>
              <b>→</b>
              <span>Review</span>
              <b>→</b>
              <span>Effect</span>
            </div>
            <p className="small">
              A local laboratory for agent authorization and adversarial evaluation.
            </p>
          </section>
          <form className="login-card" onSubmit={connect}>
            <span className="eyebrow">WORKSPACE ACCESS</span>
            <h2>Connect to your console</h2>
            <p>
              Use an operator token to run tasks and review actions, or an observer token to inspect
              runs.
            </p>
            <label htmlFor="credential">Access token</label>
            <input
              id="credential"
              ref={credential}
              type="password"
              autoComplete="off"
              autoCapitalize="none"
              spellCheck={false}
              required
              minLength={25}
              maxLength={480}
              placeholder="Paste your local access token"
              disabled={busy}
            />
            <p className="hint">
              Your token stays in memory for this tab. Reloading or disconnecting clears the
              session.
            </p>
            {error && (
              <div role="alert" className="notice error">
                {error}
              </div>
            )}
            <button className="button primary wide" disabled={busy}>
              {busy ? 'Connecting…' : 'Connect to workspace'} <span aria-hidden="true">→</span>
            </button>
            <details>
              <summary>Where do I find my token?</summary>
              <p>
                After running <code>agentguard control-init</code>, open <code>operator.token</code>{' '}
                or <code>observer.token</code> in your private control directory. The default is{' '}
                <code>artifacts/control/</code>.
              </p>
            </details>
          </form>
        </main>
      )}
      <footer>
        AgentGuard <span>Local execution. Reviewable authority.</span>
        <span>Local agent execution platform</span>
      </footer>
    </div>
  );
}

function Console({
  api,
  identity,
  logout,
}: {
  api: Api;
  identity: Identity;
  logout: (message?: string) => void;
}) {
  const [scenarios, setScenarios] = useState<Scenario[]>([]);
  const [runs, setRuns] = useState<Run[]>([]);
  const [scenarioId, setScenarioId] = useState('');
  const [selected, setSelected] = useState('');
  const [error, setError] = useState('');
  const [online, setOnline] = useState(false);
  const [submitting, setSubmitting] = useState(false);
  const [submitError, setSubmitError] = useState('');
  const [intent, setIntent] = useState<{ scenario: string; key: string } | null>(null);
  const [revision, setRevision] = useState(0);
  const alive = useRef(true);
  const mutation = useRef(false);
  useEffect(
    () => () => {
      alive.current = false;
    },
    [],
  );
  useEffect(() => {
    let cancelled = false;
    let timer: ReturnType<typeof setTimeout>;
    async function poll() {
      try {
        const [catalog, recent] = await Promise.all([
          api.get<Scenario[]>('/api/scenarios'),
          api.get<Run[]>('/api/runs'),
        ]);
        if (cancelled) return;
        setScenarios(catalog);
        setRuns(recent);
        setOnline(true);
        setError('');
        setScenarioId((current) => current || catalog[0]?.id || '');
        setSelected((current) => current || recent[0]?.episode_id || '');
      } catch (error) {
        if (cancelled) return;
        if (error instanceof ApiError && error.status === 401) {
          logout(errorMessage(error));
          return;
        }
        setOnline(false);
        setError(errorMessage(error));
      }
      if (!cancelled) timer = setTimeout(poll, 1500);
    }
    void poll();
    return () => {
      cancelled = true;
      clearTimeout(timer);
    };
  }, [api, revision]); // Session owns the API; responses from an old session are discarded.
  async function submit(event: FormEvent) {
    event.preventDefault();
    if (mutation.current || !online || !scenarioId) return;
    mutation.current = true;
    const pending = intent ?? { scenario: scenarioId, key: crypto.randomUUID() };
    setIntent(pending);
    setSubmitting(true);
    setSubmitError('');
    try {
      const result = await api.post<{ episode_id: string }>(
        '/api/runs',
        { scenario_id: pending.scenario },
        pending.key,
      );
      if (!alive.current) return;
      setIntent(null);
      setSelected(result.episode_id);
      setRevision((value) => value + 1);
    } catch (error) {
      if (!alive.current) return;
      if (error instanceof ApiError && error.status === 401) {
        logout(errorMessage(error));
        return;
      }
      if (
        error instanceof ApiError &&
        error.status >= 400 &&
        error.status < 500 &&
        error.status !== 409
      )
        setIntent(null);
      setSubmitError(errorMessage(error));
    } finally {
      mutation.current = false;
      if (alive.current) setSubmitting(false);
    }
  }
  const scenario = scenarios.find((item) => item.id === scenarioId);
  const operator = identity.role === 'operator';
  return (
    <main className="console">
      <div className="page-heading">
        <div>
          <div className="breadcrumb">
            WORKSPACE <span>/</span> {identity.workspace}
          </div>
          <h1>Run supervision</h1>
          <p>Follow each action from proposal to policy decision.</p>
        </div>
        <div className="session-status">
          <Badge value={identity.role} />
          <span className={online ? 'connection online' : 'connection'}>
            <i />
            {online ? 'Connected' : 'Connecting'}
          </span>
          <span className="small">Signed in as {identity.subject}</span>
        </div>
      </div>
      <div className="mode-strip">
        <span className="mode-symbol">◇</span>
        <strong>{modeLabel(identity.mode)}</strong>
        <span>Defended policy enforced on every application run.</span>
      </div>
      {error && (
        <div className="notice error" role="alert">
          {error}
        </div>
      )}
      <div className="metrics" aria-label="Recent run counts">
        <div>
          <span>Recent runs</span>
          <strong>
            {runs.length}
            <small>latest 50</small>
          </strong>
        </div>
        <div>
          <span>In progress</span>
          <strong>
            {runs.filter((run) => run.status === 'QUEUED' || run.status === 'RUNNING').length}
            <small>queued or running</small>
          </strong>
        </div>
        <div className="review-metric">
          <span>Awaiting review</span>
          <strong>
            {runs.filter((run) => run.status === 'WAITING_APPROVAL').length}
            <small>operator attention</small>
          </strong>
        </div>
        <div>
          <span>Execution finished</span>
          <strong>
            {runs.filter((run) => run.status === 'COMPLETED').length}
            <small>task grade separate</small>
          </strong>
        </div>
      </div>
      <div className="workspace-grid">
        <aside className="run-sidebar">
          <section className="panel new-run">
            <div className="section-label">
              <span className="eyebrow">START A WORKFLOW</span>
              <span aria-hidden="true">↗</span>
            </div>
            <h2>New run</h2>
            <form onSubmit={submit}>
              <label htmlFor="scenario">Scenario</label>
              <select
                id="scenario"
                value={scenarioId}
                onChange={(event) => setScenarioId(event.target.value)}
                disabled={!operator || submitting || !!intent}
              >
                {scenarios.map((task) => (
                  <option key={task.id} value={task.id}>
                    {pretty(task.id)}
                  </option>
                ))}
              </select>
              {scenario && (
                <>
                  <p className="task-preview">{scenario.task}</p>
                  <dl className="scope-list">
                    <Field label="Actor">{scenario.scope.actor}</Field>
                    <Field label="Projects">
                      {scenario.scope.project_ids.join(', ') || 'None'}
                    </Field>
                    <Field label="Tools">{scenario.scope.allowed_tools.join(', ')}</Field>
                    {scenario.scope.response_scope && (
                      <Field label="Response destination">
                        {scenario.scope.response_scope.recipient} ·{' '}
                        {scenario.scope.response_scope.max_classification} clearance
                        {scenario.scope.response_scope.effect_receipt &&
                          ' · Confirmed update receipt only'}
                      </Field>
                    )}
                    {scenario.scope.allowed_tools.includes('tickets.update') && (
                      <Field label="Editable tickets">
                        {scenario.scope.update_ticket_ids?.join(', ') ?? 'All in allowed projects'}
                        {scenario.scope.update_ticket_ids?.length === 0 && 'None'}
                      </Field>
                    )}
                  </dl>
                </>
              )}
              {!operator && (
                <p className="hint">
                  Observer access is read-only. Connect with an operator token to start or review
                  runs.
                </p>
              )}
              {submitError && (
                <div role="alert" className="notice error">
                  {submitError}
                </div>
              )}
              {intent && !submitting && (
                <p className="hint">
                  Submission is unresolved. Retry uses the same request ID to avoid a duplicate run.
                </p>
              )}
              <button
                className="button primary wide"
                disabled={!operator || !online || submitting || !scenario}
              >
                {submitting ? 'Submitting…' : intent ? 'Retry submission' : 'Start defended run'}
                <span aria-hidden="true">→</span>
              </button>
            </form>
          </section>
          <section className="panel recent-runs">
            <div className="panel-heading">
              <h2>Recent runs</h2>
              <span className="count">{runs.length}</span>
            </div>
            {runs.length === 0 ? (
              <p className="empty-small">Your runs will appear here.</p>
            ) : (
              <ul>
                {runs.map((run) => (
                  <li key={run.episode_id}>
                    <button
                      className={`run-item ${selected === run.episode_id ? 'selected' : ''}`}
                      onClick={() => setSelected(run.episode_id)}
                      aria-pressed={selected === run.episode_id}
                    >
                      <span className="run-name">{pretty(run.scenario_id)}</span>
                      <Badge value={run.status} />
                      <span className="run-id">
                        {run.episode_id.slice(0, 8)} <span>· {time(run.created_at)}</span>
                      </span>
                    </button>
                  </li>
                ))}
              </ul>
            )}
          </section>
        </aside>
        {selected ? (
          <RunPanel
            key={selected}
            api={api}
            id={selected}
            operator={operator}
            online={online}
            onChange={() => setRevision((value) => value + 1)}
            logout={logout}
          />
        ) : (
          <section className="panel welcome">
            <span className="welcome-shield">
              <Shield />
            </span>
            <span className="eyebrow">YOUR EXECUTION WORKSPACE</span>
            <h2>Start with a scoped task.</h2>
            <p>
              Choose a scenario to see the agent’s actions, policy decisions, and any requests for
              your approval.
            </p>
            <div className="welcome-steps">
              <div>
                <b>01</b>
                <strong>Choose a task</strong>
                <span>Authority comes from its trusted scope.</span>
              </div>
              <div>
                <b>02</b>
                <strong>Inspect the run</strong>
                <span>Follow allowed and denied actions.</span>
              </div>
              <div>
                <b>03</b>
                <strong>Review the effect</strong>
                <span>Approve only the exact action shown.</span>
              </div>
            </div>
          </section>
        )}
      </div>
    </main>
  );
}

function RunPanel({
  api,
  id,
  operator,
  online,
  onChange,
  logout,
}: {
  api: Api;
  id: string;
  operator: boolean;
  online: boolean;
  onChange: () => void;
  logout: (message?: string) => void;
}) {
  const [run, setRun] = useState<RunDetail | null>(null);
  const [steps, setSteps] = useState<Step[]>([]);
  const [approvals, setApprovals] = useState<Approval[]>([]);
  const [detail, setDetail] = useState<ApprovalDetail | null>(null);
  const [acknowledged, setAcknowledged] = useState(false);
  const [cancelConfirm, setCancelConfirm] = useState(false);
  const [error, setError] = useState('');
  const [notice, setNotice] = useState('');
  const [connected, setConnected] = useState(false);
  const [busy, setBusy] = useState(false);
  const [revision, setRevision] = useState(0);
  const [now, setNow] = useState(Date.now() / 1000);
  const alive = useRef(true);
  const mutation = useRef(false);
  const base = `/api/runs/${encodeURIComponent(id)}`;
  useEffect(
    () => () => {
      alive.current = false;
    },
    [],
  );
  useEffect(() => {
    const timer = setInterval(() => setNow(Date.now() / 1000), 1000);
    return () => clearInterval(timer);
  }, []);
  useEffect(() => {
    let cancelled = false;
    let timer: ReturnType<typeof setTimeout>;
    async function poll() {
      try {
        const [state, trace, requests] = await Promise.all([
          api.get<RunDetail>(base),
          api.get<Step[]>(`${base}/timeline`),
          api.get<Approval[]>(`${base}/approvals`),
        ]);
        if (cancelled) return;
        setRun(state);
        setSteps(trace);
        setApprovals(requests);
        setConnected(true);
      } catch (error) {
        if (cancelled) return;
        if (error instanceof ApiError && error.status === 401) {
          logout(errorMessage(error));
          return;
        }
        setConnected(false);
      }
      if (!cancelled) timer = setTimeout(poll, 1500);
    }
    void poll();
    return () => {
      cancelled = true;
      clearTimeout(timer);
    };
  }, [api, base, revision]);
  async function action(work: () => Promise<void>) {
    if (mutation.current) return;
    mutation.current = true;
    setBusy(true);
    setError('');
    setNotice('');
    try {
      await work();
    } catch (error) {
      if (!alive.current) return;
      if (error instanceof ApiError && error.status === 401) {
        logout(errorMessage(error));
        return;
      }
      setError(errorMessage(error));
      // Never replay a review automatically or silently replace the inspected snapshot.
      setDetail(null);
      setAcknowledged(false);
      setRevision((value) => value + 1);
    } finally {
      mutation.current = false;
      if (alive.current) setBusy(false);
    }
  }
  function refresh() {
    setRevision((value) => value + 1);
    onChange();
  }
  function inspect(approval: Approval) {
    void action(async () => {
      const snapshot = await api.get<ApprovalDetail>(
        `${base}/approvals/${encodeURIComponent(approval.id)}`,
      );
      if (alive.current) {
        setDetail(snapshot);
        setAcknowledged(false);
      }
    });
  }
  function review(approve: boolean) {
    if (!detail || (approve && !acknowledged) || !canReview) return;
    const snapshot = detail;
    void action(async () => {
      await api.post(`${base}/approvals/${encodeURIComponent(snapshot.id)}/review`, {
        expected_hash: snapshot.action_hash,
        nonce: snapshot.nonce,
        approve,
      });
      if (alive.current) {
        setDetail(null);
        setAcknowledged(false);
        setNotice(
          approve
            ? 'Action approved. The worker will recheck its scope before committing.'
            : 'Action rejected. The worker can continue within the remaining task budget.',
        );
        refresh();
      }
    });
  }
  const latest = approvals.find((item) => item.id === detail?.id);
  const canReview = !!(
    operator &&
    online &&
    connected &&
    !busy &&
    detail &&
    latest?.status === 'PENDING' &&
    detail.status === 'PENDING' &&
    !latest.consumed &&
    run?.status === 'WAITING_APPROVAL' &&
    detail.expires_at > now &&
    (!run.deadline || run.deadline > now)
  );
  return (
    <div className="run-content">
      <section className="panel execution-panel" aria-label="Selected run">
        <div className="panel-heading">
          <div>
            <span className="eyebrow">EXECUTION DETAIL</span>
            <h2>{run ? pretty(run.scenario_id) : 'Loading run…'}</h2>
          </div>
          <button className="button subtle" onClick={refresh} disabled={busy}>
            Refresh
          </button>
        </div>
        {!connected && (
          <div className="notice" role="status">
            Connecting to this run. Review actions are paused until its state is current.
          </div>
        )}
        {run && (
          <>
            <div className="run-summary">
              <Badge value={run.status} />
              <span className="small">{modeLabel(run.mode)}</span>
              <code>{id}</code>
            </div>
            <p className="original-task">{run.task}</p>
            <dl className="run-facts">
              <Field label="Started">{time(run.started_at)}</Field>
              <Field label="Deadline">{time(run.deadline)}</Field>
              <Field label="Worker claims">{run.claims}</Field>
              <Field label="Model calls">{run.result.model_calls ?? '—'}</Field>
            </dl>
            {run.status === 'COMPLETED' && (
              <div className="notice">
                Execution finished. Task success is determined separately by the evaluation grader.
              </div>
            )}
            {run.result.reason && run.result.reason !== 'FINAL_RESPONSE' && (
              <div className="notice">Run outcome: {pretty(run.result.reason)}</div>
            )}
            {operator && activeStates.has(run.status) && (
              <div className="cancel-row">
                {cancelConfirm ? (
                  <>
                    <span>Stop this run and prevent further effects?</span>
                    <button
                      className="button danger"
                      disabled={busy || !online || !connected}
                      onClick={() =>
                        void action(async () => {
                          const result = await api.post<{ status: string }>(`${base}/cancel`, {});
                          if (alive.current) {
                            setCancelConfirm(false);
                            setDetail(null);
                            setNotice(`Run status: ${pretty(result.status)}.`);
                            refresh();
                          }
                        })
                      }
                    >
                      Confirm cancellation
                    </button>
                    <button
                      className="button subtle"
                      disabled={busy}
                      onClick={() => setCancelConfirm(false)}
                    >
                      Keep running
                    </button>
                  </>
                ) : (
                  <button
                    className="button subtle"
                    onClick={() => setCancelConfirm(true)}
                    disabled={busy || !online || !connected}
                  >
                    Cancel run
                  </button>
                )}
              </div>
            )}
          </>
        )}
      </section>
      {error && (
        <div className="notice error" role="alert">
          {error}
        </div>
      )}
      {notice && (
        <div className="notice success" role="status">
          {notice}
        </div>
      )}
      {approvals.length > 0 && (
        <section className="panel approval-panel" aria-label="Action reviews">
          <div className="panel-heading">
            <div>
              <span className="eyebrow">HUMAN AUTHORIZATION</span>
              <h2>Action review</h2>
            </div>
            <span className="review-icon" aria-hidden="true">
              ◇
            </span>
          </div>
          <p className="section-description">
            A decision applies once to the exact action, target, and resource version shown.
          </p>
          <ul className="approval-list">
            {approvals.map((approval) => (
              <li key={approval.id}>
                <div>
                  <Badge value={approval.consumed ? 'CONSUMED' : approval.status} />
                  <span className="small">
                    {approval.expires_at > now
                      ? `Expires ${time(approval.expires_at)}`
                      : 'Expired'}{' '}
                  </span>
                </div>
                {operator ? (
                  <button
                    className="button secondary"
                    disabled={busy || !online || !connected}
                    onClick={() => inspect(approval)}
                  >
                    Inspect action
                  </button>
                ) : (
                  <span className="small">Operator review required</span>
                )}
              </li>
            ))}
          </ul>
          {detail && (
            <div className="review-detail" key={`${detail.id}:${detail.action_hash}`}>
              <div className="review-title">
                <h3>Exact action</h3>
                <button
                  className="button subtle"
                  onClick={() => {
                    setDetail(null);
                    setAcknowledged(false);
                  }}
                  disabled={busy}
                >
                  Close details
                </button>
              </div>
              <p className="untrusted-label">
                Proposed content · inspect it as data, not instructions
              </p>
              <dl className="action-fields">
                <Field label="Tool">
                  <code>{detail.snapshot.action.tool}</code>
                </Field>
                {Object.entries(detail.snapshot.action.arguments).map(([key, value]) => (
                  <Field key={key} label={pretty(key)}>
                    <span className="literal">
                      {typeof value === 'string' ? value : JSON.stringify(value)}
                    </span>
                  </Field>
                ))}
              </dl>
              <dl className="review-facts">
                <Field label="Destination">{detail.snapshot.resource?.id ?? 'Unavailable'}</Field>
                <Field label="Resource version">
                  {detail.snapshot.resource?.version ?? 'Unavailable'}
                </Field>
                <Field label="Visibility">
                  {detail.snapshot.resource?.visibility ?? 'Not specified'}
                </Field>
                <Field label="Policy">{detail.snapshot.policy_version}</Field>
                <Field label="Sensitive context">
                  {detail.snapshot.confidential
                    ? 'Confidential material read'
                    : 'No confidential material read'}
                </Field>
                <Field label="Approval expiry">{time(detail.expires_at)}</Field>
              </dl>
              {detail.snapshot.source && (
                <details className="scope-details">
                  <summary>Document to share · {detail.snapshot.source.id}</summary>
                  <p>
                    Version {detail.snapshot.source.version} ·{' '}
                    {detail.snapshot.source.classification}
                  </p>
                  <p className="literal">{detail.snapshot.source.body}</p>
                </details>
              )}
              {detail.snapshot.ticket && (
                <details className="scope-details">
                  <summary>Current ticket · {detail.snapshot.ticket.id}</summary>
                  <p>
                    Version {detail.snapshot.ticket.version} ·{' '}
                    {detail.snapshot.ticket.classification}
                  </p>
                  <p className="literal">{detail.snapshot.ticket.title}</p>
                  <p className="literal">{detail.snapshot.ticket.body}</p>
                </details>
              )}
              <details className="scope-details">
                <summary>Original task and authorization binding</summary>
                <p className="literal">{detail.task}</p>
                <dl>
                  <Field label="Actor">{detail.snapshot.contract.actor}</Field>
                  <Field label="Workspace">{detail.snapshot.contract.workspace}</Field>
                  <Field label="Allowed projects">
                    {detail.snapshot.contract.project_ids.join(', ') || 'None'}
                  </Field>
                  <Field label="Allowed documents">
                    {detail.snapshot.contract.document_ids.join(', ') || 'None'}
                  </Field>
                  <Field label="Allowed tools">
                    {detail.snapshot.contract.allowed_tools.join(', ')}
                  </Field>
                  {detail.snapshot.contract.allowed_tools.includes('tickets.update') && (
                    <Field label="Editable tickets">
                      {detail.snapshot.contract.update_ticket_ids?.join(', ') ??
                        'All in allowed projects'}
                      {detail.snapshot.contract.update_ticket_ids?.length === 0 && 'None'}
                    </Field>
                  )}
                  <Field label="Task version">{detail.snapshot.contract.version}</Field>
                  {detail.snapshot.contract.response_scope && (
                    <Field label="Response destination">
                      {detail.snapshot.contract.response_scope.recipient} ·{' '}
                      {detail.snapshot.contract.response_scope.max_classification} clearance
                      {detail.snapshot.contract.response_scope.effect_receipt &&
                        ' · Confirmed update receipt only'}
                    </Field>
                  )}
                  <Field label="Execution key">
                    <code>{detail.execution_key}</code>
                  </Field>
                  <Field label="Action hash">
                    <code>{detail.action_hash}</code>
                  </Field>
                </dl>
              </details>
              {!canReview && !busy && (
                <p className="notice">
                  This request cannot currently be reviewed. It may be decided, expired,
                  disconnected, or waiting for the run to pause.
                </p>
              )}
              <label className="acknowledgment">
                <input
                  type="checkbox"
                  checked={acknowledged}
                  disabled={!canReview}
                  onChange={(event) => setAcknowledged(event.target.checked)}
                />
                <span>I reviewed the exact action, destination, and original task.</span>
              </label>
              <div className="review-actions">
                <button
                  className="button primary"
                  disabled={!canReview || !acknowledged}
                  onClick={() => review(true)}
                >
                  {busy ? 'Saving…' : 'Approve exact action'}
                </button>
                <button
                  className="button danger"
                  disabled={!canReview}
                  onClick={() => review(false)}
                >
                  Reject action
                </button>
                <span className="small">Changes invalidate this approval.</span>
              </div>
            </div>
          )}
        </section>
      )}
      <section className="panel timeline-panel">
        <div className="panel-heading">
          <div>
            <span className="eyebrow">AUDIT TRAIL</span>
            <h2>Execution timeline</h2>
          </div>
          <span className="count">{steps.length} steps</span>
        </div>
        <p className="section-description">
          Policy decisions and in-scope targets. Document content and model responses are redacted.
        </p>
        {steps.length === 0 ? (
          <div className="timeline-empty">
            <span className="timeline-dot" />
            <div>
              <strong>Waiting for the worker</strong>
              <p>Steps appear here as responses are saved. Make sure the worker is running.</p>
            </div>
          </div>
        ) : (
          <ol className="timeline">
            {steps.map((step) => (
              <li key={step.step}>
                <div className={`step-marker ${step.decision?.outcome.toLowerCase() ?? ''}`}>
                  {step.step + 1}
                </div>
                <div className="step-body">
                  <div className="step-title">
                    <strong>
                      {step.tool || (step.kind === 'final' ? 'Final response' : pretty(step.state))}
                    </strong>
                    <Badge value={step.decision?.outcome ?? step.state} />
                  </div>
                  {step.target && (
                    <p>
                      Target <code>{step.target}</code>
                    </p>
                  )}
                  <div className="step-meta">
                    <span>{step.decision ? pretty(step.decision.reason) : pretty(step.state)}</span>
                    {step.approval_status && <span>Review: {pretty(step.approval_status)}</span>}
                    <span>{step.elapsed_seconds.toFixed(2)} s</span>
                  </div>
                </div>
              </li>
            ))}
          </ol>
        )}
      </section>
    </div>
  );
}

createRoot(document.getElementById('root')!).render(<App />);
