# PPSPi v0.2.1 release readiness

Status: **PUBLISHED WITHOUT ASSETS; SUPERSEDED BY v0.2.2**

The release workflow failed during image installation before signing or upload
because `systemctl enable --now` is invalid in pi-gen's systemd-less chroot. No
release asset was attached. The published tag remains immutable; v0.2.2 carries
the reviewed fix and is the first deployable dashboard-default patch.

This patch publishes the production-signed application bundle required to test
the real v0.2.0-to-v0.2.1 update on the running appliance. The maintainer has
requested the release. Pending production-only checks remain explicit in
[issue #95](https://github.com/Bazsy/PPSPi/issues/95) and are not treated as
pre-publication passes.

## Release identity

| Field | Value |
| --- | --- |
| Version | `0.2.1` |
| Release commit | Pending merge of this release PR |
| Release workflow | Pending publication |
| Public image SHA-256 | Pending workflow |
| Public extracted SHA-256 | Pending workflow |
| Raspberry Pi OS | Trixie arm64 |
| pi-gen commit | `ca8aeed0ae300c2a89f55ce9617d5f96a27e99e5` |
| Imager format | `cloudinit-rpi` |
| Compatibility series | `0.2` |

## Completed validation

- PR #97 merged the runtime/default/migration change with all protected Python
  3.10, 3.11, 3.13, Raspberry Pi model, required-gate, static, and CodeQL checks
  green;
- 177 unit/integration tests pass locally, including exact v0.2.0 default
  migration through the candidate configuration-regeneration path and
  customized-setting preservation;
- Ruff, ShellCheck, shfmt, yamllint, checksum-verified actionlint v1.7.7,
  markdownlint, and whitespace gates pass;
- wildcard bind validation accepts only IPv4 `0.0.0.0`; public, IPv6 wildcard,
  link-local, CGNAT, multicast, and documentation addresses remain rejected;
- socket-peer admission remains limited to validated loopback/private CIDRs and
  forwarded identity headers remain ignored;
- application updates already snapshot generated configuration and dashboard
  unit state, so failed apply/recovery/rollback covers the migrated tuple;
- v0.2.0 physically passed the unchanged GPS/PPS/RTC, Stratum 1, deep test, host
  health, reboot-persistence, loopback dashboard, and diagnostics privacy scope;
- v0.2.0's seven public assets, hashes, Imager metadata, application inventory,
  and production minisign signatures were independently verified in issue #95.

## Explicit post-publication acceptance

- independently verify all seven v0.2.1 public assets, compressed/extracted image
  hashes, build identity, Imager manifest, application inventory, and production
  signature;
- on the running v0.2.0 appliance, capture account/SSH/network/cloud-init/timing/
  unrelated-file sentinels and updater/configuration/unit state;
- run production `check` and `apply` for exact version 0.2.1;
- verify default migration, automatic service/sampler startup, Ethernet and Wi-Fi
  private access, one routed out-of-CIDR rejection, no access logging/external
  requests, bounded history, timing health, and sentinel preservation;
- exercise one-step local rollback and verify exact restoration, then reapply
  v0.2.1 if it is retained;
- perform a shortened public-image smoke when practical;
- retain the genuine reboot-required OS maintenance test separately in issue #95.

## Publication controls

- [x] `VERSION` is exactly `0.2.1`.
- [x] Changelog and patch release notes are dated and reviewed.
- [x] Deferred acceptance remains centralized in issue #95.
- [x] Release publication is the only image/signature upload trigger.
- [x] Release workflow validates tag/version, tests, rebuilds and mounts the
  image, signs the application bundle, validates exactly seven assets, removes
  the temporary signing key, and uploads without clobbering.
- [ ] Merge this release PR with all protected checks green.
- [ ] Publish GitHub Release `v0.2.1` against the exact merge commit.
- [ ] Confirm the workflow and independently verify all seven public assets.
- [ ] Record hashes and continue live-appliance acceptance in issue #95.

## Decision

Publication is approved by maintainer direction on 2026-07-29 to enable the
real signed in-place update test. PPSPi remains early-stage software and must not
be the sole production time source.
