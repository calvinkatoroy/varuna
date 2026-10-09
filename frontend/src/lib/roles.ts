// Roles as the backend defines them (controlplane/common/models.py). One place for the human labels,
// so a role never shows up as a raw id like "lead_cyber" anywhere in the app.
export type Role = 'client' | 'sysadmin' | 'pentester' | 'lead_pentester' | 'lead_cyber' | 'governance' | 'manager'

export const ROLE_LABEL: Record<Role, string> = {
  client: 'Client',
  sysadmin: 'System Administrator',
  pentester: 'Pentester',
  lead_pentester: 'Lead Pentester',
  lead_cyber: 'Lead Cybersecurity',
  governance: 'Governance',
  manager: 'Manager',
}

// Staff roles a system administrator can grant or switch between (clients belong to an organization instead).
export const STAFF_ROLES: Role[] = ['sysadmin', 'pentester', 'lead_pentester', 'lead_cyber', 'governance', 'manager']

export const roleLabel = (r?: string | null) => (r ? ROLE_LABEL[r as Role] ?? r : '')
export const isClient = (r?: string | null) => r === 'client'
