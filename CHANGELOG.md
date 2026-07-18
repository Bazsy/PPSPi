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

### Security

- no embedded account password, SSH key, or wireless credential;
- private-network-only NTP configuration validation;
- locked pi-gen build account and SSH-off image default;
- explicit release publication gate and pinned GitHub Actions.

## 0.1.0 - Unreleased

Planned first milestone. It must not be dated or published until the Raspberry
Pi 4 and Uputronics hardware acceptance report is complete.
