import { api } from '@/api'
import { prefetch } from './swr'

export type Feed = { key: string; load: () => Promise<any>; warm: () => void }

// key = plane + path: the same path answers differently for a client (pub) and for staff (prv).
function feed(plane: 'pub' | 'prv', path: string): Feed {
  const key = `${plane}:${path}`
  const loud = () => (plane === 'pub' ? api.get(path) : api.pget(path))
  const quiet = () => (plane === 'pub' ? api.qget(path) : api.qpget(path))
  return { key, load: loud, warm: () => prefetch(key, quiet) }
}

export const FEEDS = {
  cockpit: feed('pub', '/api/cockpit'),
  tasks: feed('pub', '/api/tasks'),
  reports: feed('pub', '/api/reports'),
  clientTargets: feed('pub', '/api/findings/targets'),
  board: feed('prv', '/api/board'),
  teamTargets: feed('prv', '/api/findings/targets'),
}
