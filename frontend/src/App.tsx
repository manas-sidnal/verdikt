import { useState } from 'react'
import {
  Activity,
  AlertCircle,
  ArrowUpRight,
  Check,
  ChevronDown,
  CircleHelp,
  FileCheck2,
  FlaskConical,
  GitBranch,
  Layers3,
  Loader2,
  Plus,
  ShieldCheck,
  Sparkles,
  Terminal,
  X,
} from 'lucide-react'
import './App.css'

// ---------------------------------------------------------------------------
// API
// ---------------------------------------------------------------------------

const API_BASE = (import.meta.env.VITE_API_BASE_URL as string | undefined) ?? 'http://127.0.0.1:8000'

interface PlanCheck {
  id: string
  description: string
}

interface Plan {
  claim: string
  checks: PlanCheck[]
}

interface Evidence {
  check_id: string
  passed: boolean
  exit_code: number
  tests_ran: boolean
  stdout: string
  stderr: string
  evidence_source: string
}

type Verdict = 'VERIFIED' | 'CONTRADICTED' | 'INSUFFICIENT EVIDENCE'

interface VerificationResult {
  claim: string
  plan: Plan
  evidence: Evidence
  verdict: Verdict
}

async function runVerification(claim: string): Promise<VerificationResult> {
  const response = await fetch(`${API_BASE}/verify`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ claim }),
  })

  if (!response.ok) {
    if (response.status === 422) {
      throw new Error('Claim is too short, too long, or otherwise invalid.')
    }
    throw new Error(`Verification failed (HTTP ${response.status}). Check the API server logs.`)
  }

  return response.json() as Promise<VerificationResult>
}

// ---------------------------------------------------------------------------
// Verdict badge helpers
// ---------------------------------------------------------------------------

type AppState =
  | { phase: 'idle' }
  | { phase: 'loading' }
  | { phase: 'success'; result: VerificationResult }
  | { phase: 'error'; message: string }

const stages: {
  number: string
  title: string
  description: string
  source: string
  status: 'ready' | 'pending'
  icon: typeof ShieldCheck
}[] = [
  {
    number: '01',
    title: 'Plan verification',
    description: 'Determine what evidence would prove or disprove the claim.',
    source: 'Nemotron · Nebius',
    status: 'ready',
    icon: GitBranch,
  },
  {
    number: '02',
    title: 'Collect evidence',
    description: 'Gather independent results from available checks.',
    source: 'Local test runner',
    status: 'ready',
    icon: FlaskConical,
  },
  {
    number: '03',
    title: 'Evaluate claim',
    description: 'Compare the claim against the collected evidence.',
    source: 'Verdict engine',
    status: 'ready',
    icon: FileCheck2,
  },
  {
    number: '04',
    title: 'Verify deployment',
    description: 'Check an independent deployment source when configured.',
    source: 'Not connected',
    status: 'pending',
    icon: Activity,
  },
]

// ---------------------------------------------------------------------------
// Verdict display component
// ---------------------------------------------------------------------------

function VerdictBadge({ verdict }: { verdict: Verdict }) {
  const map: Record<Verdict, { label: string; className: string }> = {
    VERIFIED: { label: 'VERIFIED', className: 'verdict-badge verdict-verified' },
    CONTRADICTED: { label: 'CONTRADICTED', className: 'verdict-badge verdict-contradicted' },
    'INSUFFICIENT EVIDENCE': { label: 'INSUFFICIENT EVIDENCE', className: 'verdict-badge verdict-insufficient' },
  }
  const { label, className } = map[verdict]
  return <span className={className}>{label}</span>
}

function ResultPanel({ result }: { result: VerificationResult }) {
  return (
    <div className="result-panel" role="region" aria-label="Verification result">
      <div className="result-header">
        <div className="result-header-left">
          <div className="section-kicker">VERIFICATION RESULT</div>
          <h2>Evidence-based verdict</h2>
        </div>
        <VerdictBadge verdict={result.verdict} />
      </div>

      {/* Prototype scope note */}
      <div className="prototype-note" role="note">
        <AlertCircle size={13} />
        <span>
          <strong>Prototype scope:</strong> The current evidence check tests local login
          behaviour only. It does not independently verify a real deployment.
          Deployment evidence is always absent, so the verdict will be{' '}
          <em>INSUFFICIENT EVIDENCE</em> unless the login tests fail.
        </span>
      </div>

      {/* Claim */}
      <div className="result-section">
        <div className="result-section-label">CLAIM SUBMITTED</div>
        <p className="result-claim">{result.claim}</p>
      </div>

      {/* Plan */}
      <div className="result-section">
        <div className="result-section-label">VERIFICATION PLAN · {result.plan.checks.length} checks</div>
        <ul className="plan-checks">
          {result.plan.checks.map((check) => (
            <li key={check.id} className="plan-check">
              <span className="check-id">{check.id}</span>
              <span className="check-desc">{check.description}</span>
            </li>
          ))}
        </ul>
      </div>

      {/* Evidence */}
      <div className="result-section">
        <div className="result-section-label">EVIDENCE · {result.evidence.evidence_source}</div>
        <div className="evidence-grid">
          <div className="evidence-row">
            <span className="evidence-key">Check</span>
            <span className="evidence-val">{result.evidence.check_id}</span>
          </div>
          <div className="evidence-row">
            <span className="evidence-key">Tests ran</span>
            <span className="evidence-val">{result.evidence.tests_ran ? 'Yes' : 'No'}</span>
          </div>
          <div className="evidence-row">
            <span className="evidence-key">Passed</span>
            <span className={`evidence-val ${result.evidence.passed ? 'ev-pass' : 'ev-fail'}`}>
              {result.evidence.passed ? 'Yes' : 'No'}
            </span>
          </div>
          <div className="evidence-row">
            <span className="evidence-key">Exit code</span>
            <span className="evidence-val evidence-mono">{result.evidence.exit_code}</span>
          </div>
        </div>
        {result.evidence.stdout && (
          <pre className="evidence-output">{result.evidence.stdout.trim()}</pre>
        )}
      </div>
    </div>
  )
}

// ---------------------------------------------------------------------------
// App
// ---------------------------------------------------------------------------

function App() {
  const [claim, setClaim] = useState('')
  const [notice, setNotice] = useState('')
  const [showHelp, setShowHelp] = useState(false)
  const [appState, setAppState] = useState<AppState>({ phase: 'idle' })

  const isLoading = appState.phase === 'loading'

  async function handleSubmit() {
    if (!claim.trim()) {
      setNotice('Enter a claim to start verification.')
      return
    }
    setNotice('')
    setAppState({ phase: 'loading' })
    try {
      const result = await runVerification(claim.trim())
      setAppState({ phase: 'success', result })
    } catch (err) {
      const message = err instanceof Error ? err.message : 'An unexpected error occurred.'
      setAppState({ phase: 'error', message })
    }
  }

  return (
    <main className="app-shell">
      <aside className="sidebar">
        <a className="brand" href="#" aria-label="Verdikt home">
          <span className="brand-mark">
            <ShieldCheck size={21} strokeWidth={1.8} />
          </span>
          <span className="brand-name">Verdikt<span>.</span></span>
        </a>

        <button
          className="workspace-switcher"
          onClick={() => setNotice('Workspace switching is not implemented yet.')}
        >
          <span className="workspace-avatar">V</span>
          <span className="workspace-copy">
            <strong>Personal workspace</strong>
            <small>Prototype environment</small>
          </span>
          <ChevronDown size={15} />
        </button>

        <div className="nav-label">WORKSPACE</div>
        <nav className="sidebar-nav">
          <button className="nav-item active" onClick={() => setNotice('You are on the verification overview.')}>
            <Layers3 size={17} />
            <span>Overview</span>
          </button>
          <button className="nav-item" onClick={() => setNotice('Verification history is coming later.')}>
            <FileCheck2 size={17} />
            <span>Verification runs</span>
            <span className="nav-soon">Soon</span>
          </button>
          <button className="nav-item" onClick={() => setNotice('Evidence explorer is coming later.')}>
            <Terminal size={17} />
            <span>Evidence explorer</span>
            <span className="nav-soon">Soon</span>
          </button>
        </nav>

        <div className="sidebar-bottom">
          <div className="connection-card">
            <span className="connection-dot connected" />
            <div>
              <strong>Local prototype</strong>
              <small>Backend connected · {API_BASE}</small>
            </div>
          </div>
          <button className="nav-item help-item" onClick={() => setShowHelp(!showHelp)}>
            <CircleHelp size={17} />
            <span>About Verdikt</span>
          </button>
          {showHelp && (
            <div className="help-popover">
              Verdikt checks AI agent claims against evidence instead of trusting a completion message alone.
              <button onClick={() => setShowHelp(false)} aria-label="Close about panel">
                <X size={14} />
              </button>
            </div>
          )}
          <div className="sidebar-footer">BUILT FOR EVIDENCE, NOT ASSUMPTIONS.</div>
        </div>
      </aside>

      <section className="main-panel">
        <header className="topbar">
          <div className="breadcrumbs">
            <span>Workspace</span>
            <span className="breadcrumb-slash">/</span>
            <strong>Overview</strong>
          </div>
          <div className="topbar-right">
            <span className="environment-label"><span /> DEVELOPMENT</span>
            <div className="avatar">M</div>
          </div>
        </header>

        <div className="page-content">
          <section className="hero">
            <div className="eyebrow"><Sparkles size={13} /> INDEPENDENT AI VERIFICATION</div>
            <h1>Don't just trust the claim.<br /><span>Verify the evidence.</span></h1>
            <p className="hero-description">
              AI agents can say a task is complete. Verdikt checks whether the evidence agrees.
            </p>
          </section>

          <section className="verification-card">
            <div className="card-heading">
              <div>
                <div className="section-kicker">NEW VERIFICATION</div>
                <h2>What does the agent claim?</h2>
                <p>Describe a result that should be independently verified.</p>
              </div>
              <div className="card-icon"><ShieldCheck size={21} /></div>
            </div>

            <label className="claim-label" htmlFor="claim-input">CLAIM TO VERIFY</label>
            <textarea
              id="claim-input"
              value={claim}
              disabled={isLoading}
              onChange={(event) => {
                setClaim(event.target.value)
                setNotice('')
                if (appState.phase !== 'idle' && appState.phase !== 'loading') {
                  setAppState({ phase: 'idle' })
                }
              }}
              placeholder="e.g. The login bug is fixed and the deployment is successful."
              rows={4}
            />

            <div className="input-meta">
              <span>Be specific. Claims should be testable.</span>
              <span>{claim.length} / 2000 characters</span>
            </div>

            <div className="example-row">
              <span className="example-label">TRY AN EXAMPLE</span>
              <button
                className="example-chip"
                disabled={isLoading}
                onClick={() => {
                  setClaim('The login bug is fixed and the deployment is successful.')
                  setNotice('')
                  setAppState({ phase: 'idle' })
                }}
              >
                Login fix + deployment <ArrowUpRight size={13} />
              </button>
            </div>

            {notice && <div className="notice" role="status">{notice}</div>}

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
                  ? 'Running verification — please wait…'
                  : appState.phase === 'success'
                  ? 'Verification complete. Edit the claim to run again.'
                  : 'No verification runs until you start one.'}
              </span>
              <button
                className="primary-button"
                id="verify-submit-btn"
                onClick={handleSubmit}
                disabled={isLoading}
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
                    {appState.phase === 'success' ? 'Verify again' : 'Start verification'}
                  </>
                )}
              </button>
            </div>
          </section>

          {appState.phase === 'success' && (
            <ResultPanel result={appState.result} />
          )}

          <section className="pipeline-section">
            <div className="pipeline-heading">
              <div>
                <div className="section-kicker">HOW VERDIKT WORKS</div>
                <h2>Verification pipeline</h2>
              </div>
              <span className="pipeline-count">4 STAGES</span>
            </div>

            <div className="pipeline-list">
              {stages.map((stage) => {
                const Icon = stage.icon
                return (
                  <article className={`pipeline-stage ${stage.status}`} key={stage.number}>
                    <div className="stage-icon"><Icon size={18} strokeWidth={1.7} /></div>
                    <div className="stage-copy">
                      <div className="stage-title-row">
                        <span className="stage-number">{stage.number}</span>
                        <h3>{stage.title}</h3>
                      </div>
                      <p>{stage.description}</p>
                      <span className="stage-source">{stage.source}</span>
                    </div>
                    <div className={`stage-status ${stage.status}`}>
                      {stage.status === 'ready' ? <><Check size={12} /> COMPONENT</> : <>NOT CONNECTED</>}
                    </div>
                  </article>
                )
              })}
            </div>
            <p className="pipeline-disclaimer">
              Component availability does not mean every stage is integrated into an end-to-end verification run.
            </p>
          </section>

          <footer className="page-footer">
            <span>VERDIKT <span className="footer-separator">/</span> EARLY PROTOTYPE</span>
            <button onClick={() => setNotice('The end-to-end verification flow is still being built.')}>
              <Plus size={13} /> What's next?
            </button>
          </footer>
        </div>
      </section>
    </main>
  )
}

export default App
