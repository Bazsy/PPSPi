# PPSPi v0.2.0-rc.1 release readiness

Status: **PREPARING — DO NOT PUBLISH YET**

This checklist governs the prerelease used to create genuine production-signed
application-update assets. It does not approve stable v0.2.0.

## Candidate identity

| Field | Value |
| --- | --- |
| Version | `0.2.0-rc.1` |
| Candidate commit | Pending merge of the release-preparation PR |
| Manual image workflow | Pending |
| Image artifact ID | Pending |
| Compressed SHA-256 | Pending |
| Extracted SHA-256 | Pending |
| Raspberry Pi OS | Trixie arm64 |
| pi-gen commit | `ca8aeed0ae300c2a89f55ce9617d5f96a27e99e5` |
| Imager format | `cloudinit-rpi` |

## Completed foundations

- 175 unit/integration tests pass before the version-preparation change;
- protected Python/model matrix, static checks, CodeQL, shell, YAML, workflow,
  Markdown, and whitespace checks pass;
- combined development image run
  [30154360761](https://github.com/Bazsy/PPSPi/actions/runs/30154360761)
  passed construction, mounted-image validation, manifest generation, artifact
  integrity, and the available hardware smoke scope;
- first boot, operator settings, wired network, SSH policy, timing hardware,
  deep checks, host health, reboot persistence, loopback dashboard, and
  regenerated diagnostics privacy passed;
- PRs #89 through #93 remediate every defect found during that campaign;
- release environment `release` exists and contains `MINISIGN_SECRET_KEY`;
- the production public key is committed; no private signing material is tracked.

## Required before RC1 publication

- [ ] Merge the version/release-documentation PR with all protected checks green.
- [ ] Dispatch **Build test image** with version `0.2.0-rc.1` from that commit.
- [ ] Verify mounted-image validation includes the persistent Netplan
  `root:root 0600` mode and dpkg statoverride entry.
- [ ] Download the workflow artifact and verify artifact digest, image checksum,
  XZ integrity, build metadata, and local Imager manifest.
- [ ] Flash the exact RC1 candidate to a separate test SD.
- [ ] Perform a shortened smoke: cloud-init, operator/network/SSH settings,
  updater origin, no incomplete transaction, Netplan mode/override, GPS/PPS/RTC,
  PPS selected at Stratum 1, deep test, host health, dashboard disabled default,
  and zero failed units.
- [ ] Complete the RC1 hardware report with exact commit/workflow/hashes.
- [ ] Review the prerelease notes and all known limitations.
- [ ] Explicitly publish GitHub prerelease `v0.2.0-rc.1` against the reviewed
  commit; do not create a stable release.

## Required after RC1 publication

- [ ] Confirm the protected workflow attaches exactly seven assets.
- [ ] Verify the public image checksum, XZ stream, build metadata, manifest, and
  credential absence.
- [ ] Verify the application manifest minisign signature with the production
  public key and validate the complete signed inventory.
- [ ] Perform a shortened public-image smoke boot.
- [ ] On the retained pre-RC test image, capture account/SSH/network/cloud-init,
  timing-config, and unrelated-file sentinels; apply RC1 through the production
  updater; verify preservation; then perform local rollback and verify exact
  restoration.
- [ ] Record #68 production apply/rollback evidence.

## Stable v0.2.0 blockers

- Issue #67 requires one real signed OS update that genuinely creates
  `/run/reboot-required`, followed by RTC/package preflight, one reboot, changed
  boot ID, delayed acknowledgment, healthy post-boot evidence, marker removal,
  and no reboot loop. The marker must not be manufactured.
- Direct-LAN dashboard behavior is not part of the accepted loopback deployment
  and must not be claimed unless an allowed client and routed out-of-CIDR client
  are measured or the release scope explicitly documents an approved waiver.
- Stable release notes/readiness must replace prerelease language and identify
  the exact stable candidate/public rebuild.

## Decision

RC1 publication gate: **NOT READY** until every pre-publication checkbox above is
complete. Stable v0.2.0 gate: **BLOCKED** by issue #67 regardless of RC1 status.
