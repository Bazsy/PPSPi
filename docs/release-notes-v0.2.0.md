# PPSPi v0.2.0 release notes

PPSPi v0.2.0 adds unattended operations, verified application updates,
configuration recovery, independent host health, and an optional read-only local
dashboard to the supported Raspberry Pi 4 and Uputronics Rev 6.4 appliance.

> [!IMPORTANT]
> Available hardware smoke passed, but three production-only acceptance items are
> explicitly deferred to [issue #95](https://github.com/Bazsy/PPSPi/issues/95):
> a genuine reboot-requiring OS update, production application apply/rollback
> using the newly published signed assets, and direct-LAN dashboard allow/deny
> measurement. These are not represented as having passed in v0.2.0.

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
  the private key is restricted to the GitHub release environment;
- updater downloads, redirects, manifests, archives, payload paths, sizes,
  modes, hashes, unit changes, and rollback snapshots fail closed;
- dashboard routes are exact GET/HEAD-only paths, with peer-CIDR enforcement,
  request/response bounds, security headers, no access logging, no external
  assets, and no administrative endpoint;
- diagnostics exclude raw GPS position, Chrony source/client listings, dashboard
  sample rows, credentials, account data, and unrelated logs; bounded captured
  output redacts selected-source identities and valid IPv4/IPv6 literals;
- Raspberry Pi OS's NetworkManager Netplan renderer receives a package-owner-
  verified, persistent `root:root 0600` dpkg statoverride.

## Hardware evidence

The combined development candidate passed first boot, Imager customization,
operator/SSH/network preservation, GPS at 115200 baud, 3D fix, active PPS,
RV-3028 RTC, synchronized PPS selection at Stratum 1, deep tests, host health,
reboot persistence, loopback dashboard behavior, bounded storage, and regenerated
diagnostics privacy inspection.

Hardware feedback produced merged fixes before v0.2.0:

- PR #89: host filesystem state uses PID 1's mount namespace rather than the
  health service's deliberate `ProtectSystem=strict` sandbox;
- PR #90: the documented maintenance status command is on the operator path;
- PR #91: dashboard graphs have numeric/named scales, units, binary axes, and
  visible legends;
- PR #92: indirect Chrony source addresses are redacted from diagnostics;
- PR #93: Netplan renderer permissions persist across package replacement.

See the [v0.2.0 hardware report](hardware-test-report-v0.2.0.md) and
[release readiness](release-readiness-v0.2.0.md).

## Deferred acceptance

Tracked in [issue #95](https://github.com/Bazsy/PPSPi/issues/95):

- exercise OS maintenance only when a genuine signed update creates
  `/run/reboot-required`; never manufacture the marker;
- use the production-signed v0.2.x application assets to test check/apply,
  preservation sentinels, recovery boundaries, and local rollback;
- retain loopback-through-SSH as the accepted dashboard deployment until one
  allowed and one routed out-of-CIDR direct-LAN client are measured;
- verify all seven public assets and perform a shortened public-image smoke after
  the release workflow finishes.

## Supported target and limitations

- Raspberry Pi 4 Model B with the documented Uputronics V6.0+ GPS/RTC profile;
- external active GNSS antenna with broad sky view;
- trusted private wired LAN;
- timing statistics are operational evidence, not an independently traceable
  accuracy claim;
- PPSPi remains early-stage software and must not be the sole production time
  source.

## Release assets

The protected release workflow rebuilds and attaches exactly seven assets:

- compressed Trixie arm64 image;
- image SHA-256;
- `build-info.json`;
- Raspberry Pi Imager manifest;
- application archive;
- canonical application manifest;
- minisign signature for the manifest.

Verify the completed release workflow and every attachment before deployment.
