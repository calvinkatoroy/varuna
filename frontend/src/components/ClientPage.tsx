import { ShellActions, ShellTitle } from './ShellSlots'

// What the old ClientShell took as props, now handed to the persistent shell: title and buttons go to the
// header slots, the content sits in the usual panel.
export function ClientPage({ title, sub, action, children }: { title: string; sub?: string; action?: React.ReactNode; children: React.ReactNode }) {
  return (
    <>
      <ShellTitle title={title} sub={sub} />
      {action && <ShellActions>{action}</ShellActions>}
      <div className="rounded-bento-lg bg-panel p-3.5">{children}</div>
    </>
  )
}
