import type { TaskStatus } from '@/api'

// Client-side words for the task states the API returns (controlplane/common/workflow.py _CLIENT).
export const CLIENT_LABEL: Record<TaskStatus, string> = {
  waiting: 'Waiting for a pentester', accepted: 'Accepted', scheduled: 'Scheduled', scanning: 'Scanning',
  paused: 'Paused', in_review: 'In review', delivered: 'Delivered', declined: 'Declined', expired: 'Expired',
}
export const CLIENT_TONE: Record<TaskStatus, string> = {
  waiting: 'med', accepted: 'accent', scheduled: 'accent', scanning: 'info', paused: 'med',
  in_review: 'accent', delivered: 'low', declined: 'crit', expired: 'crit',
}
export const CLIENT_HINT: Record<TaskStatus, string> = {
  waiting: 'A pentester will pick this up and plan the scan inside your time limit.',
  accepted: 'A pentester has taken this task and will start or schedule the scan.',
  scheduled: 'The scan is planned and starts on its own at the time shown.',
  scanning: 'The scan is running. Findings arrive when every tool has finished.',
  paused: 'The scan is paused. The security team will continue or reschedule it.',
  in_review: 'The scan is done. The report is being reviewed before it is sent to you.',
  delivered: 'Signed off and delivered. The protected report is on the Reports page.',
  declined: 'The security team could not take this task. See the reason below; you can send a new one.',
  expired: 'Your time limit ended before the scan could finish. Send a new task with a new time limit.',
}
export const CLIENT_ORDER: TaskStatus[] = ['waiting', 'accepted', 'scheduled', 'scanning', 'paused', 'in_review', 'delivered', 'declined', 'expired']
export const isClosed = (s: TaskStatus) => s === 'declined' || s === 'expired'
export const isClaimed = (s: TaskStatus) => s !== 'waiting' && !isClosed(s)
