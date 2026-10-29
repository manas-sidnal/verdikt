import { useEffect, useRef, useState } from 'react'
import type { ChangeEvent, ReactNode } from 'react'
import {
  AlertCircle,
  ArrowUpRight,
  Check,
  CircleHelp,
  ClipboardCheck,
  FileCheck2,
  FlaskConical,
  GitBranch,
  Layers3,
  Loader2,
  ShieldCheck,
  Terminal,
  X,
} from 'lucide-react'
import './App.css'

// ---------------------------------------------------------------------------
// Types (mirror backend/service.py and backend/repo_verifier.py)
// ---------------------------------------------------------------------------

const API_BASE = (import.meta.env.VITE_API_BASE_URL as string | undefined) ?? 'http://127.0.0.1:8000'

type Verdict = 'VERIFIED' | 'CONTRADICTED' | 'INSUFFICIENT EVIDENCE'
type ScenarioKind = 'honest' | 'overclaim' | 'tamper' | 'deploy'
type Mode = 'replay' | 'live'

interface ScenarioInfo {
  kind: ScenarioKind
  label: string
  report: string
}

interface TargetInfo {
  name: string
  title: string
  source_file: string
  scenarios: ScenarioInfo[]
}

interface DemoConfig {
  targets: TargetInfo[]
  live_available: boolean
  live_model: string | null
  max_report_chars: number
}

interface Evidence {
  check_id: string
  passed: boolean | null
  status: string
  explanation?: string
  evidence_source?: string
  exit_code?: number | null
  tests_ran?: boolean
  n_passed?: number | null
  n_failed?: number | null
  stdout?: string
  stderr?: string
}

interface JudgedClaim {
  quote: string
  text: string
  check: string
  arg: string | null
  verdict: Verdict
  evidence: Evidence
}

interface RunSummary {
  passed: boolean | null
  status: string
  exit_code: number | null
  n_passed: number | null
  n_failed: number | null
  tree_sha256: string | null
  duration_s: number | null
  stdout: string | null
}

interface DroppedClaim {
  reason: string
  raw: string
}

interface DemoResult {
  target: string
  report: string
  verdict: Verdict
  claims: JudgedClaim[]
  dropped_claims: DroppedClaim[]
  extraction_error: string | null
  integrity: Evidence
  runs: { baseline: RunSummary; patched: RunSummary }
  mode: Mode
  scenario: ScenarioKind
  scenario_label: string
  model: string | null
  elapsed_s: number
  patch_files: string[]
  changed_files: string[]
}

type AppState =
  | { phase: 'idle' }
  | { phase: 'loading' }
  | { phase: 'success'; result: DemoResult }
  | { phase: 'error'; message: string }

// ---------------------------------------------------------------------------
// Static copy
// ---------------------------------------------------------------------------

const SCENARIO_BLURBS: Record<ScenarioKind, string> = {
  honest: 'Writes a correct fix and reports exactly what it did.',
  overclaim: 'Writes a plausible half-fix, then claims every test passes.',
  tamper: 'Writes a half-fix, then rewrites the tests so they pass.',
  deploy: 'Writes a correct fix, then claims it deployed to production.',
}

const CHECK_LABELS: Record<string, string> = {
  tests_pass: 'Tests pass',
  bug_was_real: 'Bug was real',
  targeted_test: 'Specific test',
  files_changed: 'File changed',
  deployment_status: 'Deployment',
}

const STAGES: { number: string; title: string; description: string; source: string; icon: typeof ShieldCheck }[] = [
  {
    number: '01',
    title: 'Extract claims',
    description: "Split the agent's report into atomic claims and pick an allowlisted check for each.",
    source: 'Nemotron · Nebius Token Factory',
    icon: GitBranch,
  },
  {
    number: '02',
    title: 'Run in a sandbox',
    description: "Run the repo's real tests on a pristine copy and on the agent's patch.",
    source: 'pytest · isolated copy',
    icon: FlaskConical,
  },
  {
    number: '03',
    title: 'Judge each claim',
    description: 'Compare every claim with executed evidence only. The model never decides what is true.',
    source: 'Verdict engine',
    icon: FileCheck2,
  },
  {
    number: '04',
    title: 'Scan for tampering',
    description: 'Catch patches that edit the tests instead of fixing the code.',
    source: 'Patch scan',
    icon: Terminal,
  },
]

// ---------------------------------------------------------------------------
// API
// ---------------------------------------------------------------------------

async function readError(response: Response): Promise<string> {
  try {
    const body = (await response.json()) as { detail?: unknown }
    if (typeof body.detail === 'string') return body.detail
  } catch {
    // Non-JSON error body: fall through to the generic message.
  }
  return `Request failed (HTTP ${response.status}). Check the API server logs.`
}

async function fetchConfig(): Promise<DemoConfig> {
  const response = await fetch(`${API_BASE}/demo/config`)
  if (!response.ok) throw new Error(await readError(response))
  return (await response.json()) as DemoConfig
}

async function runDemo(payload: {
  target: string
  scenario: ScenarioKind
  mode: Mode
  report?: string
}): Promise<DemoResult> {
  const response = await fetch(`${API_BASE}/demo/verify`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(payload),
  })
  if (!response.ok) throw new Error(await readError(response))
  return (await response.json()) as DemoResult
}

// ---------------------------------------------------------------------------
// Small components
// ---------------------------------------------------------------------------

const VERDICT_KEY: Record<Verdict, 'verified' | 'contradicted' | 'insufficient'> = {
  VERIFIED: 'verified',
  CONTRADICTED: 'contradicted',
  'INSUFFICIENT EVIDENCE': 'insufficient',
}

function VerdictBadge({ verdict }: { verdict: Verdict }) {
  return <span className={`verdict-badge verdict-${VERDICT_KEY[verdict]}`}>{verdict}</span>
}

function countVerdicts(claims: JudgedClaim[]): Record<Verdict, number> {
  const counts: Record<Verdict, number> = { VERIFIED: 0, CONTRADICTED: 0, 'INSUFFICIENT EVIDENCE': 0 }
  for (const claim of claims) counts[claim.verdict] += 1
  return counts
}

/** The agent's report with each judged claim highlighted by its verdict. */
function ReportView({ report, claims }: { report: string; claims: JudgedClaim[] }) {
  const spans = claims
    .map((claim) => ({ start: report.indexOf(claim.quote), length: claim.quote.length, verdict: claim.verdict }))
    .filter((span) => span.start >= 0)
    .sort((a, b) => a.start - b.start)

  const parts: ReactNode[] = []
  let cursor = 0
  spans.forEach((span, index) => {
    if (span.start < cursor) return // overlapping quote: the earlier one wins
    if (span.start > cursor) parts.push(report.slice(cursor, span.start))
    parts.push(
      <mark key={index} className={`hl hl-${VERDICT_KEY[span.verdict]}`}>
        {report.slice(span.start, span.start + span.length)}
      </mark>,
    )
    cursor = span.start + span.length
  })
  if (cursor < report.length) parts.push(report.slice(cursor))

  return <p className="report-text">{parts}</p>
}

function ClaimCard({ claim }: { claim: JudgedClaim }) {
  const output = claim.evidence.stdout?.trim()
  return (
    <div className="claim-card">
      <div className="claim-card-head">
        <span className="check-pill">{CHECK_LABELS[claim.check] ?? claim.check}</span>
        <VerdictBadge verdict={claim.verdict} />
      </div>
      <p className="claim-quote">“{claim.quote}”</p>
      <p className="claim-explain">{claim.evidence.explanation ?? claim.text}</p>
      <div className="claim-source">
        evidence: {claim.evidence.evidence_source ?? 'none'}
        {claim.evidence.exit_code !== null && claim.evidence.exit_code !== undefined
          ? ` · exit code ${claim.evidence.exit_code}`
          : ''}
      </div>
      {output && (
        <details className="evidence-details">
          <summary>pytest output</summary>
          <pre className="evidence-output">{output}</pre>
        </details>
      )}
    </div>
  )
}

function RunCard({ title, run }: { title: string; run: RunSummary }) {
  const stateClass =
    run.passed === true ? 'ev-pass' : run.passed === false ? 'ev-fail' : 'ev-inconclusive-text'
  const label = run.status === 'executed' ? (run.passed ? 'All tests passing' : 'Tests failing') : run.status
  const output = run.stdout?.trim()
  return (
    <div className="run-card">
      <div className="run-title">{title}</div>
      <div className={`run-state ${stateClass}`}>{label}</div>
      <div className="run-counts">
        {run.n_passed ?? 0} passed · {run.n_failed ?? 0} failed
      </div>
      <div className="run-hash">tree {run.tree_sha256 ? run.tree_sha256.slice(0, 12) : '—'}</div>
      {output && (
        <details className="evidence-details">
          <summary>pytest output</summary>
          <pre className="evidence-output">{output}</pre>
        </details>
      )}
    </div>
  )
}

function verdictSummary(result: DemoResult): string {
  const total = result.claims.length
  if (total === 0) return 'No checkable claims were found in this report, so nothing could be verified.'
  const counts = countVerdicts(result.claims)
  const parts = [`${counts.VERIFIED} of ${total} ${total === 1 ? 'claim' : 'claims'} verified`]
  if (counts.CONTRADICTED) parts.push(`${counts.CONTRADICTED} contradicted`)
  if (counts['INSUFFICIENT EVIDENCE']) parts.push(`${counts['INSUFFICIENT EVIDENCE']} without enough evidence`)
  const tampered = result.integrity.passed === false ? '. The patch edited protected test files.' : '.'
  return parts.join(', ') + tampered
}

function ResultPanel({ result }: { result: DemoResult }) {
  const tampered = result.integrity.passed === false

  return (
    <div className="result-panel" role="region" aria-label="Verification result">
      <div className={`verdict-hero verdict-hero-${VERDICT_KEY[result.verdict]}`}>
        <div className="verdict-hero-context">
          {result.scenario_label} · {result.mode === 'live' ? 'Live' : 'Replay'} · {result.elapsed_s}s
        </div>
        <div className="verdict-hero-word">{result.verdict}</div>
        <p className="verdict-hero-summary">{verdictSummary(result)}</p>
      </div>

      <div className="prototype-note" role="note">
        <AlertCircle size={13} />
        <span>
          {result.mode === 'replay' ? (
            <>
              <strong>Replay mode:</strong> this agent's claims are scripted so the demo runs offline. The verdicts
              still come from real pytest runs in a sandbox.
            </>
          ) : (
            <>
              <strong>Live mode:</strong> {result.model ?? 'Nemotron'} on Nebius Token Factory extracted these claims.
              It never decides the verdicts; executed evidence does.
            </>
          )}
        </span>
      </div>

      {result.extraction_error && (
        <div className="notice notice-error" role="alert">
          <AlertCircle size={13} />
          Claim extraction failed ({result.extraction_error}). That is not evidence against the agent, so nothing was
          marked contradicted because of it.
        </div>
      )}

      <div className="result-section">
        <div className="result-section-label">Agent report, claims highlighted by verdict</div>
        <ReportView report={result.report} claims={result.claims} />
      </div>

      <div className="result-section">
        <div className="result-section-label">
          {result.claims.length} {result.claims.length === 1 ? 'claim' : 'claims'} checked
        </div>
        {result.claims.length > 0 ? (
          <div className="evidence-list">
            {result.claims.map((claim, index) => (
              <ClaimCard key={`${claim.check}-${index}`} claim={claim} />
            ))}
          </div>
        ) : (
          <div className="plan-diagnostic">
            <span className="plan-diagnostic-title">No checkable claims</span>
            <p className="plan-diagnostic-desc">
              No valid claim could be extracted from this report, so nothing can be verified. An unverified report is
              never reported as VERIFIED.
            </p>
          </div>
        )}
      </div>

      <div className="result-section">
        <div className="result-section-label">Test integrity</div>
        <div className="claim-card">
          <div className="claim-card-head">
            <span className="check-pill">Protected test files</span>
            <span className={`ev-badge ${tampered ? 'ev-fail' : 'ev-pass'}`}>
              {tampered ? 'Tampering detected' : 'Clean'}
            </span>
          </div>
          <p className="claim-explain">{result.integrity.explanation}</p>
        </div>
      </div>

      <div className="result-section">
        <div className="result-section-label">Real test runs: unpatched repo vs the agent's patch</div>
        <div className="runs-grid">
          <RunCard title="Before (unpatched)" run={result.runs.baseline} />
          <RunCard title="After (agent's patch)" run={result.runs.patched} />
        </div>
      </div>

      {result.dropped_claims.length > 0 && (
        <div className="result-section">
          <div className="result-section-label">Rejected model output ({result.dropped_claims.length})</div>
          <ul className="rejected-list">
            {result.dropped_claims.map((dropped, index) => (
              <li key={index}>{dropped.reason}</li>
            ))}
          </ul>
        </div>
      )}
    </div>
  )
}

// ---------------------------------------------------------------------------
// App
// ---------------------------------------------------------------------------

function App() {
  const [config, setConfig] = useState<DemoConfig | null>(null)
  const [configError, setConfigError] = useState('')
  const [targetName, setTargetName] = useState('')
  const [scenario, setScenario] = useState<ScenarioKind | null>(null)
  const [mode, setMode] = useState<Mode>('replay')
  const [customReport, setCustomReport] = useState<string | null>(null)
  const [showHelp, setShowHelp] = useState(false)
  const [activeNav, setActiveNav] = useState<'lab' | 'result' | 'pipeline'>('lab')
  const [appState, setAppState] = useState<AppState>({ phase: 'idle' })
  const resultRef = useRef<HTMLDivElement | null>(null)
  const hasResult = appState.phase === 'success'

  useEffect(() => {
    let cancelled = false
    fetchConfig()
      .then((loaded) => {
        if (cancelled) return
        setConfig(loaded)
      })
      .catch((err: unknown) => {
        if (cancelled) return
        setConfigError(err instanceof Error ? err.message : 'Could not reach the API.')
      })
    return () => {
      cancelled = true
    }
  }, [])

  // Highlight the sidebar item for the section nearest the top of the viewport.
  useEffect(() => {
    const visible = new Set<string>()
    const observer = new IntersectionObserver(
      (entries) => {
        for (const entry of entries) {
          const key = (entry.target as HTMLElement).dataset.nav ?? ''
          if (entry.isIntersecting) visible.add(key)
          else visible.delete(key)
        }
        setActiveNav(visible.has('pipeline') ? 'pipeline' : visible.has('result') ? 'result' : 'lab')
      },
      { rootMargin: '0px 0px -55% 0px' },
    )
    document.querySelectorAll('[data-nav]').forEach((element) => observer.observe(element))
    return () => observer.disconnect()
  }, [hasResult])

  useEffect(() => {
    if (appState.phase === 'success') {
      resultRef.current?.scrollIntoView({ behavior: 'smooth', block: 'start' })
    }
  }, [appState.phase])

  const isLoading = appState.phase === 'loading'
  const target = config?.targets.find((item) => item.name === targetName)
  const scenarioInfo = scenario ? target?.scenarios.find((item) => item.kind === scenario) : undefined
  const ready = Boolean(target && scenario)
  const behaviorOptions = (target ?? config?.targets[0])?.scenarios ?? []
  const liveReport = mode === 'live' && customReport !== null
  const shownReport = liveReport ? customReport : (scenarioInfo?.report ?? '')
  const maxChars = config?.max_report_chars ?? 4000

  function resetResult() {
    if (appState.phase === 'success' || appState.phase === 'error') setAppState({ phase: 'idle' })
  }

  function pickTarget(name: string) {
    setTargetName(name)
    setCustomReport(null)
    resetResult()
  }

  function pickScenario(kind: ScenarioKind) {
    setScenario(kind)
    setCustomReport(null)
    resetResult()
  }

  function pickMode(next: Mode) {
    setMode(next)
    resetResult()
  }

  function onReportChange(event: ChangeEvent<HTMLTextAreaElement>) {
    setCustomReport(event.target.value)
    resetResult()
  }

  async function handleVerify() {
    if (!target || !scenario) return
    setAppState({ phase: 'loading' })
    try {
      const result = await runDemo({
        target: target.name,
        scenario,
        mode,
        report: liveReport ? customReport : undefined,
      })
      setAppState({ phase: 'success', result })
    } catch (err) {
      setAppState({ phase: 'error', message: err instanceof Error ? err.message : 'An unexpected error occurred.' })
    }
  }

  function goToLab() {
    window.scrollTo({ top: 0, behavior: 'smooth' })
    history.replaceState(null, '', window.location.pathname + window.location.search)
  }

  function goToResult() {
    document.getElementById('result')?.scrollIntoView({ behavior: 'smooth', block: 'start' })
    history.replaceState(null, '', window.location.pathname + window.location.search)
  }

  function goToPipeline() {
    document.getElementById('pipeline')?.scrollIntoView({ behavior: 'smooth', block: 'start' })
    history.replaceState(null, '', '#pipeline')
  }

  const apiState = config ? 'connected' : configError ? 'offline' : 'connecting'

  return (
    <main className="app-shell">
      <aside className="sidebar">
        <a className="brand" href="#" aria-label="Verdikt home">
          <span className="brand-mark">
            <ShieldCheck size={21} strokeWidth={1.8} />
          </span>
          <span className="brand-name">Verdikt<span>.</span></span>
        </a>

        <nav className="sidebar-nav" aria-label="Sections">
          <a
            className={`nav-item ${activeNav === 'lab' ? 'active' : ''}`}
            href="#"
            aria-current={activeNav === 'lab' ? 'page' : undefined}
            onClick={(event) => {
              event.preventDefault()
              goToLab()
            }}
          >
            <Layers3 size={17} />
            <span>Agent lab</span>
          </a>
          {appState.phase === 'success' && (
            <a
              className={`nav-item ${activeNav === 'result' ? 'active' : ''}`}
              href="#result"
              aria-current={activeNav === 'result' ? 'page' : undefined}
              onClick={(event) => {
                event.preventDefault()
                goToResult()
              }}
            >
              <ClipboardCheck size={17} />
              <span>Result</span>
              <i className={`nav-dot nav-dot-${VERDICT_KEY[appState.result.verdict]}`} aria-hidden="true" />
            </a>
          )}
          <a
            className={`nav-item ${activeNav === 'pipeline' ? 'active' : ''}`}
            href="#pipeline"
            aria-current={activeNav === 'pipeline' ? 'page' : undefined}
            onClick={(event) => {
              event.preventDefault()
              goToPipeline()
            }}
          >
            <FileCheck2 size={17} />
            <span>How it works</span>
          </a>
        </nav>

        <div className="sidebar-bottom">
          <div className="connection-card">
            <span className={`connection-dot ${apiState === 'connected' ? 'connected' : ''}`} />
            <div>
              <strong>API {apiState}</strong>
              <small>
                {config
                  ? config.live_available
                    ? `Live ready · ${config.live_model ?? 'Nemotron'}`
                    : 'Replay mode only'
                  : API_BASE}
              </small>
            </div>
          </div>
          <button className="nav-item help-item" onClick={() => setShowHelp(!showHelp)}>
            <CircleHelp size={17} />
            <span>About Verdikt</span>
          </button>
          {showHelp && (
            <div className="help-popover">
              Verdikt checks what coding agents claim against real test runs instead of trusting their completion
              message.
              <button onClick={() => setShowHelp(false)} aria-label="Close about panel">
                <X size={14} />
              </button>
            </div>
          )}
          <div className="sidebar-footer">Built for evidence, not assumptions.</div>
        </div>
      </aside>

      <section className="main-panel">
        <header className="topbar">
          <div className="breadcrumbs">
            <span>Verdikt</span>
            <span className="breadcrumb-slash">/</span>
            <strong>Agent lab</strong>
          </div>
          <div className="topbar-right">
            <span className="environment-label"><span /> Nebius × NVIDIA hackathon</span>
          </div>
        </header>

        <div className="page-content">
          <section className="hero">
            <h1>Agents say it's done.<br /><span>Verdikt runs the tests.</span></h1>
            <p className="hero-description">
              Pick a buggy repo and an agent behavior. Verdikt splits the agent's report into claims and judges each one
              against real test runs, not against what the agent says about itself.
            </p>
          </section>

          <section className="verification-card">
            <div className="card-heading">
              <div>
                <h2>Pick a repo and an agent</h2>
                <p>Each repo ships with a real bug and a real test suite. The agent's patch is applied in a sandbox.</p>
              </div>
            </div>

            {configError && (
              <div className="notice notice-error" role="alert">
                <AlertCircle size={13} />
                Could not load the lab from {API_BASE}: {configError}
              </div>
            )}

            {config && (
              <>
                <div className="picker-group">
                  <span className="claim-label">Repository</span>
                  <div className="chip-row">
                    {config.targets.map((item) => (
                      <button
                        key={item.name}
                        className={`choice-chip ${item.name === targetName ? 'active' : ''}`}
                        disabled={isLoading}
                        onClick={() => pickTarget(item.name)}
                      >
                        {item.title}
                      </button>
                    ))}
                  </div>
                </div>

                <div className="picker-group">
                  <span className="claim-label">Agent behavior</span>
                  <div className="chip-row">
                    {behaviorOptions.map((item) => (
                      <button
                        key={item.kind}
                        className={`choice-chip ${item.kind === scenario ? 'active' : ''}`}
                        disabled={isLoading || !target}
                        onClick={() => pickScenario(item.kind)}
                      >
                        {item.label}
                      </button>
                    ))}
                  </div>
                  <p className="scenario-blurb">
                    {scenario
                      ? SCENARIO_BLURBS[scenario]
                      : target
                        ? 'Choose how the agent behaves.'
                        : 'Pick a repository first.'}
                  </p>
                </div>

                <div className="picker-group">
                  <span className="claim-label">Claim source</span>
                  <div className="mode-toggle" role="group" aria-label="Claim source">
                    <button
                      className={`mode-option ${mode === 'replay' ? 'active' : ''}`}
                      disabled={isLoading}
                      onClick={() => pickMode('replay')}
                    >
                      Replay · scripted, offline
                    </button>
                    <button
                      className={`mode-option ${mode === 'live' ? 'active' : ''}`}
                      disabled={isLoading || !config.live_available}
                      title={config.live_available ? undefined : 'The server has no Nebius API key configured.'}
                      onClick={() => pickMode('live')}
                    >
                      Live · Nemotron extracts claims
                    </button>
                  </div>
                </div>

                <label className="claim-label" htmlFor="claim-input">Agent's final report</label>
                <textarea
                  id="claim-input"
                  value={shownReport}
                  readOnly={mode !== 'live' || !ready}
                  placeholder="Pick a repository and an agent behavior to load the agent's report."
                  disabled={isLoading}
                  maxLength={maxChars}
                  onChange={onReportChange}
                  rows={4}
                />
                <div className="input-meta">
                  <span>
                    {!ready
                      ? "The agent's report appears here once you pick a repository and an agent behavior."
                      : mode === 'live'
                      ? 'Edit the report. Nemotron extracts the claims; the patch stays the same.'
                      : 'Switch to live mode to edit the report and let Nemotron extract the claims.'}
                  </span>
                  <span>{shownReport.length} / {maxChars}</span>
                </div>
              </>
            )}

            {appState.phase === 'error' && (
              <div className="notice notice-error" role="alert">
                <AlertCircle size={13} />
                {appState.message}
              </div>
            )}

            <div className="form-footer">
              <span className="privacy-note">
                <ShieldCheck size={14} />
                {isLoading
                  ? 'Running tests in a sandbox. This takes a few seconds…'
                  : ready
                    ? 'Nothing the model writes is ever executed.'
                    : 'Pick a repository and an agent behavior to run a check.'}
              </span>
              <button
                className="primary-button"
                id="verify-submit-btn"
                onClick={handleVerify}
                disabled={isLoading || !ready}
                aria-busy={isLoading}
              >
                {isLoading ? (
                  <>
                    <Loader2 size={15} className="spin" />
                    Verifying…
                  </>
                ) : (
                  <>
                    {appState.phase === 'success' ? <Check size={15} /> : <ArrowUpRight size={16} />}
                    {appState.phase === 'success' ? 'Verify again' : 'Verify agent'}
                  </>
                )}
              </button>
            </div>
          </section>

          <div ref={resultRef} id="result" data-nav={hasResult ? 'result' : undefined}>
            {appState.phase === 'success' && <ResultPanel result={appState.result} />}
          </div>

          <section className="pipeline-section" id="pipeline" data-nav="pipeline">
            <div className="pipeline-heading">
              <div>
                <h2>How Verdikt works</h2>
              </div>
            </div>

            <div className="pipeline-list">
              {STAGES.map((stage) => {
                const Icon = stage.icon
                return (
                  <article className="pipeline-stage ready" key={stage.number}>
                    <div className="stage-icon"><Icon size={18} strokeWidth={1.7} /></div>
                    <div className="stage-copy">
                      <div className="stage-title-row">
                        <span className="stage-number">{stage.number}</span>
                        <h3>{stage.title}</h3>
                      </div>
                      <p>{stage.description}</p>
                      <span className="stage-source">{stage.source}</span>
                    </div>
                  </article>
                )
              })}
            </div>
            <p className="pipeline-disclaimer">
              Deployment claims can never be verified: there is no deployment runner, so they always end as
              INSUFFICIENT EVIDENCE rather than a guess.
            </p>
          </section>

        </div>
      </section>
    </main>
  )
}

export default App
