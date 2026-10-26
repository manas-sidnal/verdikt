
import { useState } from 'react'
import {
  Activity,
  ArrowUpRight,
  Check,
  ChevronDown,
  CircleHelp,
  FileCheck2,
  FlaskConical,
  GitBranch,
  Layers3,
  Plus,
  ShieldCheck,
  Sparkles,
  Terminal,
  X,
} from 'lucide-react'
import './App.css'

type StageStatus = 'ready' | 'pending'

const stages: {
  number: string
  title: string
  description: string
  source: string
  status: StageStatus
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

function App() {
  const [claim, setClaim] = useState('')
  const [notice, setNotice] = useState('')
  const [showHelp, setShowHelp] = useState(false)

  function handleSubmit() {
    if (!claim.trim()) {
      setNotice('Enter a claim to prepare a verification run.')
      return
    }

    setNotice(
      'Preview only — verification is not connected to the frontend yet. Your claim has not been submitted to the backend.',
    )
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
            <span className="connection-dot" />
            <div>
              <strong>Local prototype</strong>
              <small>Backend integration pending</small>
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
              onChange={(event) => {
                setClaim(event.target.value)
                setNotice('')
              }}
              placeholder="e.g. The login bug is fixed and the deployment is successful."
              rows={4}
            />

            <div className="input-meta">
              <span>Be specific. Claims should be testable.</span>
              <span>{claim.length} characters</span>
            </div>

            <div className="example-row">
              <span className="example-label">TRY AN EXAMPLE</span>
              <button
                className="example-chip"
                onClick={() => {
                  setClaim('The login bug is fixed and the deployment is successful.')
                  setNotice('')
                }}
              >
                Login fix + deployment <ArrowUpRight size={13} />
              </button>
            </div>

            {notice && <div className="notice" role="status">{notice}</div>}

            <div className="form-footer">
              <span className="privacy-note"><ShieldCheck size={14} /> No verification runs until you start one.</span>
              <button className="primary-button" onClick={handleSubmit}>
                Prepare verification <ArrowUpRight size={16} />
              </button>
            </div>
          </section>

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
