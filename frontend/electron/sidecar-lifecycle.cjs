function restartSidecar({
  apiIsRunning,
  isQuitting,
  onComplete,
  startSidecar,
}) {
  return async () => {
    onComplete()
    if (!isQuitting() && !(await apiIsRunning())) startSidecar()
  }
}

module.exports = { restartSidecar }
