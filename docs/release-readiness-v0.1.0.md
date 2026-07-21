# PPSPi v0.1.0 release readiness

Status: **IN PROGRESS**

This checklist summarizes release controls without replacing the detailed
[hardware report](hardware-test-report-v0.1.0.md) or
[release process](release-process.md).

## Candidate identity

- runtime candidate source: `f6cde4d72305ec1e31ffd76f9f247f0853615ff7`;
- candidate merge commit: `0f59bc3bf0daf9ee4e9ec1eff6f21afc1d6b8aea`;
- Raspberry Pi OS: Trixie arm64;
- pinned pi-gen: `ca8aeed0ae300c2a89f55ce9617d5f96a27e99e5`;
- compressed candidate SHA-256:
  `9d57c17deeaa6ebac4d7d1cd649c290eebe2391b9b4c90d539f359253596cd15`;
- version file remains `0.1.0-dev`; no release tag exists.

Runtime/configuration is frozen during the final observation. Documentation
work on this branch does not approve or publish a release.

## Validation completed

- 62 unit and fixture tests passed on Python 3.10, 3.11, and 3.13;
- supported/rejected Raspberry Pi model matrix passed;
- Ruff, ShellCheck, shfmt, yamllint, actionlint, and markdownlint passed;
- manual Trixie arm64 image build and read-only validation passed;
- local Raspberry Pi Imager manifest generation and independent image hash
  validation passed;
- all operational hardware checks are PASS except check 15, which has an
  explicit scope waiver rather than a measured pass;
- antenna-loss fallback, GPS/PPS recovery, Ethernet loss, client recovery, RTC
  cold restore, and sanitized diagnostics were physically exercised;
- marginal indoor RF placement was diagnosed and corrected without a software
  change.

## Repository and security controls

Reviewed 2026-07-21:

- active default-branch ruleset requires pull requests, resolved conversations,
  strict **Static checks**, and strict **Required test gate**;
- branch deletion and non-fast-forward updates are blocked by the ruleset;
- Actions default token permission is read-only and cannot approve pull
  requests;
- release workflow alone has explicit `contents: write` and is gated by the
  `release` environment;
- pull requests, merges, and tag pushes cannot publish a release;
- all external Actions and the QEMU image are pinned by immutable digest;
- GitHub secret scanning and push protection are enabled;
- private vulnerability reporting is enabled;
- vulnerability alerts and Dependabot security updates are enabled;
- default CodeQL setup for Python was enabled;
- no open Dependabot or secret-scanning alert was reported at review time;
- tracked filename/content checks found no credential material;
- repository object integrity passed `git fsck`;
- merged branches are deleted automatically.

## Open gates

- [ ] Fresh 24-hour open-sky timing observation started at
  2026-07-21 08:48:24 UTC, completes, and is analyzed.
- [x] Visible HAT revision and best-effort RTC package top-code are recorded
  without serials; the difficult RTC reading is explicitly marked unverified.
- [x] RAM, bootloader, storage, power-supply, and antenna/cable report fields are
  completed.
- [ ] Maintainer signs off the documented check-15 deployment-scope waiver.
- [ ] `VERSION` is changed from `0.1.0-dev` to `0.1.0` in a release pull
  request.
- [ ] Changelog `0.1.0` section receives the release date.
- [ ] Final release notes replace all pending language.
- [ ] Explicit GitHub Release `v0.1.0` is published against the reviewed commit.
- [ ] Release workflow attaches and verifies all four public assets.
- [ ] Public artifact checksum, metadata, Imager manifest, credential absence,
  and shortened smoke boot are verified.

## Deferred after v0.1.0

- stable v1.0.0 support and maintenance commitments: issue #20;
- generic UART/PPS hardware profiles: issue #18;
- evidence-based pre-V6.0 Uputronics profiles: issue #22;
- additional Raspberry Pi models require separate physical profiles and test
  plans.
