import { useEffect, useState } from 'react'
import { useSearchParams } from 'react-router-dom'
import { api, download } from '../api'
import Button from '../components/Button'

const SEV: Record<string, { cls: string; label: string; rank: number }> = {
  critical: { cls: 'text-crit', label: 'Critical', rank: 0 },
  high: { cls: 'text-high', label: 'High', rank: 1 },
  medium: { cls: 'text-med', label: 'Medium', rank: 2 },
  low: { cls: 'text-low', label: 'Low', rank: 3 },
  info: { cls: 'text-info', label: 'Info', rank: 4 },
}
const TEMPLATES = ['Executive Summary', 'Full Technical', 'OWASP Web App', 'ILCS Internal']

function sevOf(f: any) {
  return SEV[(f.severity || 'info').toLowerCase()] || SEV.info
}

export default function FindingsReview() {
  const [params] = useSearchParams()
  const [jobId, setJobId] = useState(params.get('job') || '')
  const [findings, setFindings] = useState<any[] | null>(null)
  const [selected, setSelected] = useState(0)
  const [template, setTemplate] = useState('Full Technical')
  const [err, setErr] = useState('')
  const [loading, setLoading] = useState(false)
  const [generating, setGenerating] = useState(false)

  async function load() {
    if (!jobId) return
    setErr('')
    setLoading(true)
    try {
      const f = await api.pget(`/api/findings/${jobId}`)
      f.sort((a: any, b: any) => sevOf(a).rank - sevOf(b).rank)
      setFindings(f)
      setSelected(0)
    } catch (e: any) {
      setErr(e.message + ' (private plane requires Tailscale)')
      setFindings(null)
    } finally {
      setLoading(false)
    }
  }

  async function genReport() {
    setGenerating(true)
    try {
      const meta = await api.ppost('/api/reports/generate', { job_id: jobId, template })
      await download(api.privateBase, `/api/reports/${meta.file}/download`, meta.file)
    } catch (e: any) {
      setErr(e.message)
    } finally {
      setGenerating(false)
    }
  }

  // Arriving from a Dashboard job link (?job=<id>): load it immediately.
  useEffect(() => {
    if (params.get('job')) load()
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [])

  const current = findings && findings.length > 0 ? findings[selected] : null

  return (
    <div className="-m-sm md:-m-lg">
      <div className="flex flex-wrap items-center justify-between gap-sm border-b border-rule bg-paper-2 px-sm py-2xs md:px-lg">
        <div className="flex flex-wrap items-center gap-xs">
          <span className="font-display text-lg text-ink">Findings Review</span>
          <input
            className="input h-8 w-40"
            placeholder="Job ID"
            value={jobId}
            onChange={(e) => setJobId(e.target.value)}
          />
          <Button variant="ghost" busy={loading} busyLabel="Loading…" onClick={load}>
            Load
          </Button>
        </div>
        {findings && findings.length > 0 && (
          <div className="flex flex-wrap items-center gap-xs">
            <select className="input h-8" value={template} onChange={(e) => setTemplate(e.target.value)}>
              {TEMPLATES.map((t) => (
                <option key={t}>{t}</option>
              ))}
            </select>
            <Button busy={generating} busyLabel="Generating…" onClick={genReport}>
              Generate report
            </Button>
          </div>
        )}
      </div>
      {err && <div className="px-sm py-2xs text-sm text-crit md:px-lg">{err}</div>}

      {findings && findings.length === 0 && (
        <div className="px-sm py-sm text-sm text-ink-faint md:px-lg">No findings for this job.</div>
      )}

      {findings && findings.length > 0 && (
        <div className="grid md:grid-cols-[minmax(0,1fr)_minmax(0,1.3fr)]">
          <div className="overflow-x-auto border-b md:border-b-0 md:border-r md:border-rule">
            <table className="data-table">
              <thead>
                <tr>
                  <th className="pl-sm md:pl-lg">Sev</th>
                  <th>Finding</th>
                  <th className="pr-sm md:pr-lg">Host</th>
                </tr>
              </thead>
              <tbody>
                {findings.map((f, i) => {
                  const s = sevOf(f)
                  return (
                    <tr
                      key={i}
                      aria-selected={i === selected}
                      tabIndex={0}
                      onClick={() => setSelected(i)}
                      onKeyDown={(e) => e.key === 'Enter' && setSelected(i)}
                      className="aria-selected:bg-paper-3 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-focus focus-visible:ring-inset"
                    >
                      <td className={`pl-sm font-semibold md:pl-lg ${s.cls}`}>{s.label}</td>
                      <td className="max-w-[14rem] truncate text-ink">{f.name}</td>
                      <td className="mono pr-sm text-xs text-ink-muted md:pr-lg">{f.host}</td>
                    </tr>
                  )
                })}
              </tbody>
            </table>
          </div>

          {current && (
            <div className="space-y-xs px-sm py-sm text-sm md:px-lg">
              <div className={`font-semibold ${sevOf(current).cls}`}>{current.name}</div>
              <div className="text-ink-muted">
                <span className="text-ink-faint">Host:</span> {current.host} &nbsp;
                <span className="text-ink-faint">URL:</span> {current.url}
              </div>
              {current.owasp && (
                <div className="text-ink-muted">
                  <span className="text-ink-faint">OWASP:</span> {current.owasp}
                </div>
              )}
              {(current.cve || current.cwe) && (
                <div className="mono text-ink-muted">
                  <span className="font-body text-ink-faint">CVE:</span> {current.cve || '-'}{' '}
                  <span className="font-body text-ink-faint">CVSS:</span> {current.cvss ?? '-'}{' '}
                  <span className="font-body text-ink-faint">CWE:</span> {current.cwe || '-'}
                </div>
              )}
              {current.impact && (
                <div className="text-ink-muted">
                  <span className="text-ink-faint">Impact:</span> {current.impact}
                </div>
              )}
              {current.remediation && (
                <div className="text-ink-muted">
                  <span className="text-ink-faint">Remediation:</span> {current.remediation}
                </div>
              )}
              {current.evidence && (
                <pre className="mono overflow-x-auto rounded-input bg-paper p-xs text-xs text-ink-muted">
                  {current.evidence}
                </pre>
              )}
              <div className="mono text-xs text-ink-faint">tool: {current.tool}</div>
            </div>
          )}
        </div>
      )}
    </div>
  )
}
