# PPSPi v0.2.0 release readiness

Status: **APPROVED FOR PUBLICATION WITH EXPLICIT DEFERRED ACCEPTANCE**

The maintainer chose to publish v0.2.0 before moving the appliance to its final
location. Available hardware scope passed; remaining production-only checks are
tracked in [issue #95](https://github.com/Bazsy/PPSPi/issues/95) under the v0.3
milestone and are not represented as v0.2.0 passes.

## Release identity

| Field | Value |
| --- | --- |
| Version | `0.2.0` |
| Release commit | Pending merge of this release PR |
| Release workflow | Pending publication |
| Public image SHA-256 | Pending workflow |
| Public extracted SHA-256 | Pending workflow |
| Raspberry Pi OS | Trixie arm64 |
| pi-gen commit | `ca8aeed0ae300c2a89f55ce9617d5f96a27e99e5` |
| Imager format | `cloudinit-rpi` |

## Completed validation

- 175 unit/integration tests passed on the release-preparation source;
- protected Python 3.10, 3.11, and 3.13 jobs, Raspberry Pi model matrix,
  required gate, static checks, and CodeQL passed;
- complete Ruff, ShellCheck, shfmt, Bash syntax, yamllint, actionlint,
  markdownlint, and whitespace gates passed;
- combined development image workflow
  [30154360761](https://github.com/Bazsy/PPSPi/actions/runs/30154360761)
  passed build, mounted-image validation, local Imager manifest generation,
  artifact upload, checksum, XZ, and build-identity checks;
- first boot, cloud-init customization, operator/network/SSH policy, GPS/PPS/RTC,
  Stratum 1, deep validation, host health, reboot persistence, dashboard disabled
  default, loopback dashboard, bounded storage, and diagnostics privacy passed;
- PRs #89 through #93 remediate all defects found during hardware acceptance;
- v0.2 milestone implementation issues are closed;
- release environment contains `MINISIGN_SECRET_KEY`; no private key is tracked.

## Explicitly deferred to v0.3 issue #95

- genuine signed OS update that creates `/run/reboot-required`, including RTC
  save, one reboot, boot-ID acknowledgment, post-boot evidence, marker removal,
  and no loop;
- production application check/apply/preservation/rollback using v0.2.0's newly
  published signed assets;
- direct-LAN dashboard allowed/out-of-CIDR client measurement;
- public seven-asset verification and shortened public-image smoke after the
  workflow finishes.

The maintainer accepts these as post-v0.2.0 follow-up scope. They remain untested
or pending, not waived into PASS.

## Publication controls

- [x] `VERSION` is exactly `0.2.0`.
- [x] Changelog and stable release notes are dated and reviewed.
- [x] Deferred acceptance is centralized in v0.3 issue #95.
- [x] Release publication remains the only trigger for image/signature upload.
- [x] Release workflow validates tag/version, rebuilds, mounts and validates the
  image, creates the production-signed application bundle, validates the exact
  seven-asset contract, and uploads without clobbering.
- [ ] Publish GitHub Release `v0.2.0` against the reviewed merge commit.
- [ ] Confirm the release workflow succeeds and all seven assets appear.
- [ ] Record public hashes and follow-up evidence in issue #95.

## Decision

Publication is approved by explicit maintainer direction on 2026-07-25. PPSPi
remains early-stage software and must not be the sole production time source.
