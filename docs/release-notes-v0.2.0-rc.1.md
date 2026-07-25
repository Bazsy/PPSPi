# PPSPi v0.2.0-rc.1 release notes

PPSPi v0.2.0-rc.1 is a prerelease for validating unattended operation,
production-signed application updates, recovery, and the optional read-only
local dashboard on the supported Raspberry Pi 4 and Uputronics Rev 6.4 target.

> [!WARNING]
> This is not the stable v0.2.0 release. The real reboot-required OS maintenance
> path in issue #67 remains blocked until a genuine signed OS update requires a
> reboot. Use RC1 on a test SD with the known-good SD retained.

## Highlights

- passive timing and host-health states with two-observation hysteresis,
  transitions, JSON, human, and Prometheus output;
- mode-0600 configuration backup, inspection, dry-run restore, hardware
  validation, pre-restore backup, and rollback;
- distribution-native signed security maintenance in one bounded weekly window,
  with package audit, RTC preflight, required-only reboot, and boot-ID
  acknowledgment;
- exact-version, production-minisign-signed application bundles with bounded
  parsing, durable transaction snapshots, interrupted-update recovery, exact
  managed inventories, and one-step local rollback;
- optional, default-disabled Python standard-library dashboard with sanitized
  bounded SQLite history, fixed local assets, strict private bind/CIDR policy,
  read-only HTTP access, labeled graph scales, and hardened systemd services;
- host capacity, inode, filesystem, temperature, throttling, ext4-error, update,
  and required-reboot monitoring;
- portable configuration disaster recovery and expanded diagnostics.

## Security and privacy

- application updates trust the production public key committed in the image;
  the private key is restricted to the protected GitHub release environment;
- updater downloads, redirects, manifests, archives, payload paths, sizes,
  modes, hashes, unit changes, and rollback snapshots fail closed;
- dashboard routes are exact GET/HEAD-only paths, with peer-CIDR enforcement,
  request/response bounds, security headers, no access logging, no external
  assets, and no administrative endpoint;
- diagnostics exclude raw GPS position, Chrony source/client listings, dashboard
  sample rows, credentials, account data, and unrelated logs; bounded captured
  output redacts selected-source identities and valid IPv4/IPv6 literals;
- the upstream Raspberry Pi Netplan renderer file receives a package-owner-
  verified, persistent `root:root 0600` dpkg statoverride.

## Hardware evidence

The combined development image passed first boot, Imager customization,
operator/SSH/network preservation, GPS at 115200 baud, 3D fix, active PPS,
RV-3028 RTC, synchronized PPS selection at Stratum 1, deep tests, host health,
reboot persistence, loopback dashboard behavior, bounded storage, and regenerated
diagnostics privacy inspection.

Hardware feedback produced four merged runtime fixes before RC1:

- PR #89: host filesystem state is read from PID 1's mount namespace rather than
  the health service's deliberate `ProtectSystem=strict` sandbox;
- PR #90: the documented maintenance status command is exposed on the operator
  path;
- PR #91: dashboard graphs have numeric/named scales, units, binary axes, and
  visible legends;
- PR #92: indirect Chrony source addresses are redacted from status/journal
  diagnostics.

PR #93 adds the persistent Netplan permission correction found during first
boot. The exact RC1 image build and shortened smoke are tracked in
[RC1 readiness](release-readiness-v0.2.0-rc.1.md) and the
[RC1 hardware report](hardware-test-report-v0.2.0-rc.1.md).

## Why publish a prerelease

The release workflow is the only path that can access the protected production
minisign key. Publishing RC1 as a prerelease creates a genuine signed same-series
application bundle so issue #68 can exercise production verification, apply,
recovery boundaries, preservation sentinels, and rollback without weakening the
trust root.

## Known limitations and blocked gates

- issue #67's real update plus required-reboot path is **BLOCKED**, not passed;
- issue #68's production apply/rollback remains pending until RC1 signed assets
  are attached;
- direct-LAN dashboard allow/deny behavior was not physically measured; the
  accepted deployment is loopback through SSH;
- only Raspberry Pi 4 Model B with the documented Uputronics V6.0+ profile is in
  scope;
- timing statistics are operational evidence, not an independently traceable
  accuracy claim;
- RC1 must not be used as the sole production time source.

## Expected assets

After explicit prerelease publication, the protected workflow rebuilds and
attaches exactly seven assets:

- compressed Trixie arm64 image;
- image SHA-256;
- `build-info.json`;
- Raspberry Pi Imager manifest;
- application archive;
- canonical application manifest;
- minisign signature for the manifest.

Verify all assets and the post-publication workflow before using RC1.
