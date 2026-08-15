function redact(value, userHome) {
  if (!value) return "none"
  return userHome
    ? String(value).replaceAll(userHome, "[user-home]")
    : String(value)
}

function yesNoUnavailable(value) {
  return value === true ? "yes" : value === false ? "no" : "unavailable"
}

function buildSupportReport({
  generatedAt,
  appVersion,
  electronVersion,
  platform,
  apiBase,
  electronMemoryMb,
  launchMode,
  sidecar,
  userHome,
}) {
  const diagnostics = sidecar.diagnostics || {}
  return [
    "Resolve Time Tracker support report",
    `Generated: ${generatedAt}`,
    `Tracker: ${appVersion}`,
    `Electron: ${electronVersion}`,
    `System: ${platform}`,
    `Electron memory: ${electronMemoryMb ?? "unavailable"} MB`,
    `Electron process: ${process.pid}`,
    `Launch mode: ${launchMode}`,
    `Local API: ${apiBase}`,
    `Sidecar reachable: ${sidecar.reachable ? "yes" : "no"}`,
    `Sidecar error: ${redact(sidecar.error, userHome)}`,
    `Python: ${diagnostics.python_version || "unavailable"}`,
    `Python process: ${diagnostics.process_id || "unavailable"}`,
    `Python executable: ${diagnostics.executable || "unavailable"}`,
    `Sidecar platform: ${diagnostics.platform || "unavailable"}`,
    `Resolve bridge: ${diagnostics.resolve_bridge || "unavailable"}`,
    `External scripting: ${
      diagnostics.resolve_bridge === "connected" ? "confirmed" : "not confirmed"
    }`,
    `Resolve project detected: ${yesNoUnavailable(diagnostics.resolve_project_detected)}`,
    `Scripting module available: ${yesNoUnavailable(diagnostics.scripting_module_available)}`,
    `Scripting module loaded: ${yesNoUnavailable(diagnostics.scripting_module_loaded)}`,
    `Resolve: ${
      [diagnostics.resolve_product, diagnostics.resolve_version]
        .filter(Boolean)
        .join(" ") || "unavailable"
    }`,
    `Resolve bridge error: ${redact(diagnostics.last_runtime_error, userHome)}`,
    "",
    "Recent sidecar errors:",
    redact(sidecar.stderr, userHome),
    "",
    "Privacy: this report does not include Resolve project names or tracking history.",
  ].join("\n")
}

module.exports = { buildSupportReport }
