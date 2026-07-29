import { useEffect, useState } from 'react'
import { api } from '@/api'

// Live agent status in the cockpit hero. Replaces the old dead "Install Agent" button (which
// made no sense post-unlock): once you are in the dashboard, the agent is already installed.
export function AgentStatus() {
  const [a, setA] = useState<{ registered: boolean; online: boolean } | null>(null)
  useEffect(() => { api.get('/api/agent').then(setA).catch(() => {}) }, [])
  const online = a?.online
  return (
    <span className="inline-flex items-center gap-2 rounded-pill bg-white/10 px-4 py-2.5 text-[13px] font-medium text-[#F2F5EF] backdrop-blur-md">
      <span className={`h-[7px] w-[7px] rounded-full ${online ? 'bg-low shadow-[0_0_0_3px_rgba(66,196,162,.28)]' : 'bg-ink-faint'}`} />
      Agent {online ? 'online' : a?.registered ? 'offline' : 'not installed'}
    </span>
  )
}
