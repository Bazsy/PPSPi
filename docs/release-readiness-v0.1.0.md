# PPSPi v0.1.0 release readiness

Status: **COMPLETE**

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
- release pull request set `VERSION` to `0.1.0`.

Runtime/configuration remained frozen through the final observation. The release
pull request changed version and release documentation only; publication remained
a separate explicit maintainer action.

## Public release identity

- GitHub Release: [v0.1.0](https://github.com/Bazsy/PPSPi/releases/tag/v0.1.0),
  published 2026-07-22;
- tagged release commit: `fcc3acf3ab6d26c94ba3a9e952abb9957d58b0fc`;
- release workflow:
  [run 29907047200](https://github.com/Bazsy/PPSPi/actions/runs/29907047200);
- compressed public image SHA-256:
  `75aad478df0a234f7d3c502b66cddbcf5e6e77430b0bfd2542acfdac696deb45`;
- extracted public image SHA-256:
  `4d049234e774fbc55f10000119beaddcec200e7a5f14cf5ffd2576ae4bf98e5f`.

## Validation completed

- 66 unit and fixture tests passed on Python 3.10, 3.11, and 3.13;
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
- the final 24.003-hour open-sky observation passed strict analysis with 97.42%
  sample coverage, 100% PPS selection/assert advancement/3D GNSS captures, zero
  restarts/failed units/throttling events, and a passing final deep test.
- the tagged rebuild passed static tests, read-only mounted-image validation,
  exact four-asset validation, and explicit upload;
- unauthenticated public downloads passed checksum, XZ, build metadata,
  manifest, extracted-image, and credential-absence verification;
- Raspberry Pi Imager 2.0.10 loaded the public manifest and exposed all
  `cloudinit-rpi` customisation pages;
- the flashed public image completed cloud-init, selected active PPS at Stratum
  1, reported a 3D fix with 15 satellites used, and passed every deep check.

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

## Completion gates

- [x] Fresh 24-hour open-sky timing observation completed and passed strict
  analysis.
- [x] Visible HAT revision and best-effort RTC package top-code are recorded
  without serials; the difficult RTC reading is explicitly marked unverified.
- [x] RAM, bootloader, storage, power-supply, and antenna/cable report fields are
  completed.
- [x] Maintainer signed off the documented check-15 deployment-scope waiver.
- [x] `VERSION` is changed from `0.1.0-dev` to `0.1.0` in a release pull
  request.
- [x] Changelog `0.1.0` section receives the release date.
- [x] Final release notes replace all pending language.
- [x] Explicit GitHub Release `v0.1.0` is published against the reviewed commit.
- [x] Release workflow attaches and verifies all four public assets.
- [x] Public artifact checksum, metadata, Imager manifest, credential absence,
  and shortened smoke boot are verified.

## Deferred after v0.1.0

- stable v1.0.0 support and maintenance commitments: issue #20;
- generic UART/PPS hardware profiles: issue #18;
- evidence-based pre-V6.0 Uputronics profiles: issue #22;
- additional Raspberry Pi models require separate physical profiles and test
  plans.
