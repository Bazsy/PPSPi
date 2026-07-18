# PPSPi v0.1.0 draft release notes

> Draft only. Do not publish until the Raspberry Pi 4/Uputronics acceptance
> report passes every required check.

PPSPi v0.1.0 introduces the source-controlled installer and diagnostics
milestone for a GPS/PPS Stratum-1 server based on Raspberry Pi OS Lite 64-bit
Bookworm.

## Highlights

- current Uputronics GPS/RTC profile with source-verified GPIO 18 PPS and
  RV-3028-C7 RTC configuration;
- strict, idempotent installer for a clean Raspberry Pi OS Lite system;
- GPSD serial time and direct kernel PPS integration with Chrony;
- private-LAN NTP serving with network startup/fallback sources;
- guarded RTC restore and low-frequency synchronized save;
- `ppstime-status`, `ppstime-test`, `ppstime-config`, and sanitised diagnostics;
- fixture-driven CI and Raspberry Pi model policy tests;
- pinned pi-gen Bookworm arm64 image tooling and explicit GitHub release gates.

## Security defaults

The image contains no default password, project SSH key, or wireless credential.
SSH is disabled. Initial account creation and optional key injection use
Raspberry Pi Imager. NTP access is limited to validated private CIDRs.

## Required operator action

Narrow the default NTP allow-list after first boot:

```console
sudo ppstime-config set NTP_ALLOW 192.168.1.0/24
sudo ppstime-config apply
```

## Known limitations

- Hardware acceptance status: **NOT RUN**.
- Only Raspberry Pi 4 Model B is in scope.
- Older Uputronics HAT revisions are not automatically supported.
- GPS serial offset remains uncalibrated and the GPS source is intentionally
  non-selectable.
- This milestone does not claim production readiness.

## Verification

The final notes must include:

- test workflow URL;
- manual image build workflow URL;
- hardware report URL;
- image SHA-256;
- exact pi-gen and PPSPi commit IDs.
