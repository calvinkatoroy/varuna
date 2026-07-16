import { useState } from 'react'
import { api, download } from '../api'

const SEV: Record<string, { cls: string; label: string }> = {
  critical: { cls: 'text-crit', label: 'Critical' },
  high: { cls: 'text-high', label: 'High' },
  medium: { cls: 'text-med', label: 'Medium' },
  low: { cls: 'text-low', label: 'Low' },
  info: { cls: 'text-info', label: 'Info' },
}
const TEMPLATES = ['Executive Summary', 'Full Technical', 'OWASP Web App', 'ILCS Internal']

export default function FindingsReview() {
  const [jobId, setJobId] = useState('')
  const [findings, setFindings] = useState<any[] | null>(null)
  const [template, setTemplate] = useState('Full Technical')
  const [err, setErr] = useState('')

  async function load() {
    if (!jobId) return
    setErr('')
    try {
      setFindings(await api.pget(`/api/findings/${jobId}`))
    } catch (e: any) {
      setErr(e.message + ' (private plane requires Tailscale)')
      setFindings(null)
    }
  }

  async function genReport() {
    try {
      const meta = await api.ppost('/api/reports/generate', { job_id: jobId, template })
      await download(api.privateBase, `/api/reports/${meta.file}/download`, meta.file)
    } catch (e: any) {
      setErr(e.message)
    }
  }

  return (
    <div className="max-w-3xl space-y-4">
      <h1 className="text-2xl font-bold text-white">Findings Review</h1>
      <div className="flex gap-2">
        <input className="input" placeholder="Job ID" value={jobId} onChange={(e) => setJobId(e.target.value)} />
        <button className="btn" onClick={load}>
          Load
        </button>
      </div>
      {err && <div className="text-sm text-crit">{err}</div>}

      {findings && (
        <>
          <div className="flex items-center gap-2">
            <select className="input flex-1" value={template} onChange={(e) => setTemplate(e.target.value)}>
              {TEMPLATES.map((t) => (
                <option key={t}>{t}</option>
              ))}
            </select>
            <button className="btn" onClick={genReport}>
              Generate report
            </button>
          </div>
          {findings.length === 0 && <div className="text-gray-400">No findings for this job.</div>}
          {findings.map((f, i) => {
            const s = SEV[(f.severity || 'info').toLowerCase()] || SEV.info
            return (
              <details key={i} className="card" open={['critical', 'high'].includes((f.severity || '').toLowerCase())}>
                <summary className="cursor-pointer">
                  <span className={`font-semibold ${s.cls}`}>{s.label}</span>{' '}
                  <span className="text-white">{f.name}</span>
                </summary>
                <div className="mt-3 space-y-1 text-sm text-gray-300">
                  <div>
                    <span className="text-gray-500">Host:</span> {f.host} &nbsp;
                    <span className="text-gray-500">URL:</span> {f.url}
                  </div>
                  {f.owasp && <div><span className="text-gray-500">OWASP:</span> {f.owasp}</div>}
                  {(f.cve || f.cwe) && (
                    <div>
                      <span className="text-gray-500">CVE:</span> {f.cve || '-'}{' '}
                      <span className="text-gray-500">CVSS:</span> {f.cvss ?? '-'}{' '}
                      <span className="text-gray-500">CWE:</span> {f.cwe || '-'}
                    </div>
                  )}
                  {f.impact && <div><span className="text-gray-500">Impact:</span> {f.impact}</div>}
                  {f.remediation && <div><span className="text-gray-500">Remediation:</span> {f.remediation}</div>}
                  {f.evidence && (
                    <pre className="overflow-x-auto rounded bg-bg p-3 text-xs text-gray-200">{f.evidence}</pre>
                  )}
                  <div className="text-xs text-gray-600">tool: {f.tool}</div>
                </div>
              </details>
            )
          })}
        </>
      )}
    </div>
  )
}
