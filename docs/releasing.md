# Release Policy

## Version Sources and Current Status

The application version is `[project].version` in [pyproject.toml](../pyproject.toml), currently `0.1.1`. Keep `src/resolve_time_tracker/__init__.py` and the root package entry in `uv.lock` synchronized with it when preparing a release. Tags use `v<version>`.

[frontend/package.json](../frontend/package.json) is a private development package; its current `0.0.1` is not a second application release. When packaging is implemented, align installer and displayed application versions with the authoritative application version and update any affected lockfiles.

The project remains experimental, with a Pre-Alpha classifier. Historical unsuffixed `0.x` versions do not establish stable readiness. No next version or stable release date is selected by this policy. Packaging remains deferred as recorded in the [roadmap](roadmap.md#windows-packaged-release).

## Compatibility Contract

Compatibility covers saved Projects, Sessions, settings and Heartbeat recovery; tracked launch and Resolve menu workflows; documented command options and environment settings; and exported CSV/PDF information. Keep the loopback API and dashboard compatible within the same release; internal Python modules and cross-version private API access are not a public SDK contract.

Newer versions preserve existing user history and settings through safe migrations. Back up data before a schema change, test upgrades, and provide recovery instructions. Older applications are not promised to open databases changed by newer versions; restore a compatible backup for downgrade when necessary. Tracking-rule fixes may change future computed totals; explain consequential changes and preserve recorded history.

Support claims follow [Platform Support](platform-support.md) and each release's recorded evidence. State the tested Resolve version and operating system. Automated tests on Windows and Ubuntu do not establish live Resolve support on macOS or Linux.

## Choosing a Version

Use [Semantic Versioning 2.0.0](https://semver.org/) with the application contract above. Choose the largest increment required by the release batch; released contents and tags are immutable.

| Change | Before 1.0 | From 1.0 onward |
| --- | --- | --- |
| Compatible fix or small UI refinement | Patch, such as 0.1.1 to 0.1.2 | Patch |
| Compatible new functionality | Minor, resetting patch | Minor, resetting patch |
| Breaks the compatibility contract | Minor, resetting patch; describe migration/recovery | Major, resetting minor and patch; describe migration/recovery |

The pre-1.0 convention is a project rule, not a SemVer compatibility guarantee. Documentation-only changes can accompany the next release without a version bump. UI additions follow the feature rule; a visual change that breaks a supported workflow follows the breaking-change rule.

Readiness is selected separately from the increment:

- **Alpha** (`-alpha.N`): core behavior is incomplete or experimental.
- **Beta** (`-beta.N`): the intended workflow is ready for broader testing.
- **Release candidate** (`-rc.N`): a proposed stable release awaiting final verification.
- **Stable** (no suffix): recommended and maintained for the documented purpose, with limitations stated.

Select `1.0.0` when the owner accepts maintaining this contract and the intended workflow is ready for recommended use. Stages are optional. A stable source release does not imply every platform or a packaged installer is qualified. Use the version syntax required by each package ecosystem when encoding prereleases, while retaining the same release identity.

## Release Preparation

1. Select the reviewed source through the [Git workflow](branch-workflow.md). Record its commit and an unused version; synchronize the version sources above and any packaging inputs actually present.
2. Prepare notes covering changes, readiness, migrations, backups/recovery, tested platforms and Resolve versions, and known limitations. Keep current README, help, and download wording consistent while preserving historical records.
3. Run the [development checks](development.md#run-checks). Record actual results against the selected source. Separately validate live tracking accuracy, privacy, startup/shutdown, and data preservation for the environments advertised. For a packaged release, meet [ADR 0002's lifecycle constraints](adr/0002-windows-packaged-distribution.md#release-constraints), including signing and SHA-256 checksums before calling the installer production-ready. Retain the tested artifacts and evidence.
4. Inspect [CI](../.github/workflows/ci.yml) and [release automation](../.github/workflows/release.yml) before tagging. A `v*` tag starts both workflows independently; draft creation is not gated on CI passing. The release workflow creates generated draft notes only, with no installer build or explicit prerelease flag. Verify checks, artifacts, notes, and GitHub prerelease status against the chosen readiness before publication.
5. Tag, push, and publish only within the user's authorization. After publication, verify the public version and intended downloads. Record what was published and any unperformed checks; preparation alone is not publication.
