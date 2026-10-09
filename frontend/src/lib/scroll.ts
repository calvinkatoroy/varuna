export type NavType = 'POP' | 'PUSH' | 'REPLACE'

/** True while a Back/Forward scroll restore is in flight: a deep-link row must not re-centre over it. */
export const restoring = { on: false }

/** Where the page should sit after a PATH change: back/forward returns to that entry's saved spot, anything else starts at the top. */
export const scrollTarget = (type: NavType, saved: number | undefined): number => (type === 'POP' ? saved ?? 0 : 0)
