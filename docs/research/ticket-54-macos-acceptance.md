# Ticket #54: macOS installation acceptance

Validation date: 2026-10-28. Source: `75e84869931d5dfec494f9c5eb59c98a551aa2d6`
(v0.1.2-alpha.1 release-source merge). This records native Mac evidence for
[issue #54](https://github.com/Today20092/Davinci-Resolve-TimeTracker/issues/54).
Broader activity, workload and ownership acceptance belongs to #58.

## Environment

| Component | Observed value |
| --- | --- |
| macOS | 27.0.1, build 26A434 |
| Architecture | arm64 / Apple Silicon |
| Resolve application | 21.1.1, bundle build 21.1.10010; running edition confirmation pending |
| Git | 2.54.0 (Apple Git-157) |
| Node.js | Interactive shell: 22.23.1; observed installer Electron-download child: Homebrew 26.10.0 |
| pnpm used for installation | 11.21.0, matching `frontend/package.json` |
| uv | 0.12.19 (Homebrew, aarch64-apple-darwin) |
| Python | CPython 3.13.14 |

## Isolation and procedure

- Used an independent fresh clone, detached at the revision above, under
  `~/Library/Application Support/ResolveTimeTracker/mac-acceptance/source`.
  The working source checkout was not upgraded or rebuilt.
- Before installation, copied the existing Resolve `Scripts/Utility` directory
  to a private temporary backup. There was no pre-existing
  `~/Library/Application Support/ResolveTimeTracker` data directory before the
  fresh clone was created. Live tests must still use a disposable project and
  separate database.
- The shell supplied pnpm 11.25.0, so created isolated Corepack shims in a
  temporary directory and verified `pnpm --version` returned 11.21.0 from
  `frontend/`. This did not replace the global package manager.
- Ran the repository's `sh install.sh` with those shims first on `PATH`.
  No npm install workaround, manual frontend prebuild, or generated npm
  lockfile was used.
- Resolve and its dashboard were closed during installation.

## Results

| Check | Result |
| --- | --- |
| Fresh `sh install.sh` | PASS: exit 0; frontend built, Electron executable downloaded, Python environment created, default menu entries installed |
| Existing installer regression suite | PASS: `uv run --python 3.13 -m pytest -q tests/test_bootstrap_install.py`, 19 tests |
| Frontend checks in fresh clone | PASS: lint, typecheck, 29 tests (0 skipped), production build |
| Missing pnpm prerequisite | PASS: restricted `PATH` produced `Install failed: Node.js with pnpm is required to build the desktop app.` before build/menu mutation |
| Resolve SDK default files | PASS: default macOS `DaVinciResolveScript.py` and application `fusionscript.so` exist |
| Installed dashboard | Pending live validation |
| Resolve menu attach / repeat launch | Pending live validation |

The missing-prerequisite check ran the fresh installer's Python entry point with
`PATH=/usr/bin:/bin` and an explicit existing source directory. It returned exit
status 1 without starting dependency installation. File existence alone does not
prove scripting access; that requires the live Resolve tests.

The full frontend check commands were `pnpm run lint`, `pnpm run typecheck`,
`pnpm test`, and `pnpm run build`, with the pinned-version Corepack shims first on
`PATH`. The build emitted the existing warning that a minified JavaScript chunk
exceeds 500 kB (705.51 kB, gzip 213.02 kB); it completed successfully. The source
working tree remained clean after installation and checks, with no generated npm
lockfile. Electron's first version check downloaded its macOS arm64 binary
automatically as part of the installer; no manual prebuild was needed.

No OS privacy/security permissions were changed, and no runtime token, private
project name, or media path is included here. Native Linux/X11 is outside this
Mac installation result.
