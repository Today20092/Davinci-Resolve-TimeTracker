# Roadmap

GitHub Issues own the remaining work. The [0.1.2-alpha.1 release notes](releases/0.1.2-alpha.1.md) distinguish completed fixes from known limits.

## Completed for the source preview

- Isolated Resolve SDK reads keep status, Pause/Resume and Stop responsive during blocked reads.
- Late observations are discarded; stale totals and pause recovery use the Session's own persisted freshness boundary. Uncertain gaps are excluded from billing.
- One SDK reader is reused, dead readers can recover, and Windows parent-crash ownership prevents orphaned readers.
- Benchmarks now identify aggregate process costs and distinguish synthetic observations from SDK calls. Concurrent cached reads and heartbeat limits have regression coverage.
- Isolated Windows install/reinstall/rollback and source-runtime shutdown checks passed. The native-window experiment recorded its idle successes and playback failures; it is not a production UI replacement.

Existing explicit launch, no login watcher, local SQLite history, CSV/PDF reports and the on-demand Electron dashboard remain the product foundation.

## Remaining work

| Priority | Ticket | Next outcome |
| --- | --- | --- |
| First | [#52: Windows tracking correctness and release validation](https://github.com/Today20092/Davinci-Resolve-TimeTracker/issues/52) | Restore reliable playback observations; address dashboard resource costs; validate actual installed upgrades, representative editing/long renders and recovery. |
| Environment needed | [#54: fresh macOS installation](https://github.com/Today20092/Davinci-Resolve-TimeTracker/issues/54) | Verify the pinned-pnpm install and installed dashboard/menu launch on a real Mac. |
| Environment needed | [#58: macOS/X11 runtime validation](https://github.com/Today20092/Davinci-Resolve-TimeTracker/issues/58) | Verify activity, ownership, shutdown and resource behavior on the actual platforms; reuse #54's installer evidence. |
| Research | [#57: native Resolve utility](https://github.com/Today20092/Davinci-Resolve-TimeTracker/issues/57) | Prove responsive launch, scheduling and Stop during playback/render before integrating tracking. Retain on-demand reporting meanwhile. |
| Deferred | [#13: Resolve Free compatibility](https://github.com/Today20092/Davinci-Resolve-TimeTracker/issues/13) | Investigate an actual Free environment; record unsupported APIs or edition restrictions without promising compatibility. |
| Deferred | [#20: Windows packaged distribution](https://github.com/Today20092/Davinci-Resolve-TimeTracker/issues/20) | Revisit after real editing validation and the hosting decision; source previews do not deliver a standalone installer. |

## Windows Packaged Release

[ADR 0002](adr/0002-windows-packaged-distribution.md) owns the distribution design. Before a production-ready installer, prove clean-machine install, launch, upgrade, rollback, uninstall and data preservation, then add code signing and published checksums. Packaging tools remain unselected. No login watcher or automatic startup is planned.

Session editing improvements and expanded diagnostics remain future ideas; they are not commitments in this release.
