const presentations = {
  active: ["#22c55e", "Tracking active"],
  idle: ["#eab308", "Idle — not recording time"],
  paused: ["#eab308", "Tracking paused"],
  resolve_closed: ["#9ca3af", "Resolve closed"],
  stale: ["#ef4444", "Tracker heartbeat stale"],
  error: ["#ef4444", "Tracker disconnected"],
}

function trayPresentation(status) {
  const [color, label] =
    presentations[status?.tracking_status] ?? presentations.error
  const details = [
    status?.project !== "none" && status?.project,
    status?.active_elapsed,
  ]
    .filter(Boolean)
    .join(" — ")
  return { color, label, tooltip: details ? `${label} — ${details}` : label }
}

module.exports = { trayPresentation }
