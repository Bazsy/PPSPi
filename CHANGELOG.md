# Changelog

All notable changes are documented here. PPSPi follows
[Semantic Versioning](https://semver.org/).

## Unreleased

### Added

- strict environment-style Uputronics hardware profile;
- idempotent Raspberry Pi OS Lite installer;
- GPSD, direct kernel PPS, Chrony, and RV-3028 RTC integration;
- human-readable and JSON status output;
- deep installation tests and sanitised diagnostic bundles;
- fixture-based tests for healthy and degraded timing states;
- pinned pi-gen Trixie arm64 image build;
- separate lint, test, manual image, and explicitly published release workflows;
- user, developer, hardware, troubleshooting, and release documentation.

### Changed

- expanded the default NTP client allow-list to all RFC 1918 IPv4 ranges and
  RFC 4193 IPv6 ULA while keeping other address classes rejected.
- corrected the Uputronics V6.0+ profile to its manufacturer-documented 115200
  baud default, fixed GPSD to that configured speed, and exposed baud in status
  output; older Uputronics boards remain documented as 9600-baud hardware.
- migrated the image base from Debian 12 Bookworm to current Debian 13 Trixie,
  pinned the official Raspberry Pi `pi-gen` arm64 revision, and enabled native
  Raspberry Pi cloud-init support for subsequent Imager integration.
- added read-only image inspection before artifact upload to verify Trixie,
  native Raspberry Pi cloud-init support, PPSPi runtime/configuration, a locked
  temporary account, and disabled SSH.
- switched the GitHub runner's host emulation package to `qemu-user-binfmt`,
  which provides the `qemu-aarch64` binary required by Trixie pi-gen.
- register a static arm64 fix-binary interpreter with the pinned Docker QEMU
  setup action so pi-gen's privileged container can execute arm64 binaries in
  both manual test-image and published-release builds.
- generate Raspberry Pi Imager 2.x manifests with `cloudinit-rpi`, Pi 4-only
  device metadata, versioned release URLs, and compressed/extracted SHA-256 and
  size values.
- document the supported release/local manifest paths and a secure manual
  cloud-init boot-partition fallback; **Use custom** remains intentionally
  unsuitable for Trixie customisation in Imager 2.x.
- accept strong, unique password-authenticated SSH as the approachable baseline
  on a trusted private LAN, while retaining public keys as optional hardening
  and warning that PPSPi does not firewall SSH according to `NTP_ALLOW`.

### Fixed

- enable RV-3028 level-switching backup mode for the Uputronics V6.0+ profile,
  allowing its twin supercapacitors to maintain RTC time while Pi power is
  removed; mode `0` remains available for profiles without backup power.
- let unprivileged `ppstime-status` fall back to validated, world-readable RTC
  sysfs date/time when the root-only RTC device rejects `hwclock`, while keeping
  RTC setting and restore operations privileged.
- treat the RV-3028's expected first-power-on `EINVAL` read as an uninitialized
  RTC restore skip instead of leaving a failed systemd unit; other RTC errors
  remain failures.
- make the strictly non-secret active profile readable by documented
  unprivileged status commands and preserve that mode after configuration edits.
- conditionally remove the pinned Raspberry Pi cloud-init package's stale
  `netplan_nm_patch` module entry when the package does not ship that module,
  preventing a successful customized first boot from reporting degraded status.
- install Trixie's `util-linux-extra` package so RTC restore/save has
  `hwclock`, and load `i2c-dev` persistently so `/dev/i2c-1` is available for
  documented hardware validation and diagnostics.
- pass the generated pi-gen configuration through `build-docker.sh -c`; the
  previous positional argument left the configuration path empty and failed at
  `realpath` before Docker image construction began.
- install pi-gen's required QEMU user emulation and binfmt support explicitly on
  the ephemeral GitHub-hosted image-build runner.
- suppress the intermediate Stage 2 `-lite` image and select the final pi-gen
  output by its exact PPSPi image name instead of rejecting all multi-image
  deploy directories.

### Security

- no embedded account password, SSH key, or wireless credential;
- private-network-only NTP configuration validation;
- locked pi-gen build account and SSH-off image default;
- explicit release publication gate and pinned GitHub Actions.

## 0.1.0 - Unreleased

Planned first milestone. It must not be dated or published until the Raspberry
Pi 4 and Uputronics hardware acceptance report is complete.
