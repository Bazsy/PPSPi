# PPSPi v0.2.2 release readiness

Status: **APPROVED CORRECTED PATCH FOR PUBLICATION**

v0.2.2 supersedes assetless v0.2.1. The v0.2.1 release workflow failed before
signing or upload when its newly default-enabled dashboard path used
`systemctl enable --now` inside pi-gen's systemd-less chroot. The corrected
installer enables units and starts them in separate operations, preserving both
first-boot image behavior and immediate activation on a running appliance.

## Release identity

| Field | Value |
| --- | --- |
| Version | `0.2.2` |
| Release commit | Pending merge of this release PR |
| Corrected predecessor | `v0.2.1` (no assets) |
| Failed predecessor workflow | [30431968395](https://github.com/Bazsy/PPSPi/actions/runs/30431968395) |
| Release workflow | Pending publication |
| Public image hashes | Pending workflow |
| Raspberry Pi OS | Trixie arm64 |
| pi-gen commit | `ca8aeed0ae300c2a89f55ce9617d5f96a27e99e5` |
| Compatibility series | `0.2` |

## Root cause and correction

- pi-gen invokes the installer in a chroot where the target path appears as `/`
  but systemd is not PID 1;
- `systemctl enable` correctly creates first-boot wants links there;
- `systemctl start` is safely ignored by systemctl's chroot detection;
- combined `systemctl enable --now` is rejected before that normal start-path
  handling and terminated the build;
- v0.2.2 uses explicit enable and start commands and adds an image-build
  regression assertion forbidding the combined dashboard operation.

## Validation

- the focused image/installer suite passes after the correction;
- complete local unit/integration and static gates must pass on the release
  branch;
- protected Python 3.10/3.11/3.13, model matrix, required gate, static checks,
  and CodeQL must pass before merge;
- v0.2.0 remains the physical timing baseline because GPSD, PPS, Chrony, RTC,
  boot overlays, and hardware profiles are unchanged;
- dashboard defaults, exact v0.2.0 migration, custom-setting preservation,
  transactional rollback, CIDR enforcement, and mounted-image expectations are
  covered by automated tests.

## Post-publication acceptance

- independently verify exactly seven v0.2.2 assets, all public digests, image XZ
  integrity and extracted identity, build metadata, Imager manifest, application
  inventory, and production signature;
- run exact signed v0.2.0-to-v0.2.2 check/apply on the appliance with preservation
  sentinels;
- verify automatic service/timer state, Ethernet/Wi-Fi private access, a routed
  out-of-CIDR denial, bounded history, no access logging/external requests, and
  unchanged timing health;
- exercise local rollback/restoration and reapply if v0.2.2 is retained;
- perform shortened public-image smoke when practical;
- retain the separate genuine reboot-required OS test in issue #95.

## Publication controls

- [x] v0.2.1 remains immutable and is visibly marked assetless/superseded.
- [x] `VERSION` is exactly `0.2.2`.
- [x] Changelog and corrected patch documents are dated.
- [x] Release publication remains the only signing/upload trigger.
- [ ] Complete local and protected validation.
- [ ] Merge against an up-to-date `main` and capture the exact merge commit.
- [ ] Publish stable `v0.2.2` against that commit.
- [ ] Confirm workflow success and independently verify all seven assets.
- [ ] Continue appliance evidence in issue #95.

## Decision

Publication is approved as a corrected patch. PPSPi remains early-stage software
and must not be the sole production time source.
