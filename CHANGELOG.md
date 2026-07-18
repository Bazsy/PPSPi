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
- pinned pi-gen Bookworm arm64 image build;
- separate lint, test, manual image, and explicitly published release workflows;
- user, developer, hardware, troubleshooting, and release documentation.

### Changed

- expanded the default NTP client allow-list to all RFC 1918 IPv4 ranges and
  RFC 4193 IPv6 ULA while keeping other address classes rejected.
- corrected the Uputronics V6.0+ profile to its manufacturer-documented 115200
  baud default, fixed GPSD to that configured speed, and exposed baud in status
  output; older Uputronics boards remain documented as 9600-baud hardware.

### Fixed

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
