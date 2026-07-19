# PPSPi v0.1.0 draft release notes

> Draft only. Do not publish until the Raspberry Pi 4/Uputronics acceptance
> report passes every required check.

PPSPi v0.1.0 introduces the source-controlled installer and diagnostics
milestone for a GPS/PPS Stratum-1 server based on Raspberry Pi OS Lite 64-bit
Trixie.

## Highlights

- Uputronics V6.0+ GPS/RTC profile with manufacturer-verified 115200 baud,
  GPIO 18 PPS, and RV-3028-C7 RTC configuration;
- strict, idempotent installer for a clean Raspberry Pi OS Lite system;
- GPSD serial time and direct kernel PPS integration with Chrony;
- private-LAN NTP serving with network startup/fallback sources;
- guarded RTC restore and low-frequency synchronized save;
- `ppstime-status`, `ppstime-test`, `ppstime-config`, and sanitised diagnostics;
- fixture-driven CI and Raspberry Pi model policy tests;
- pinned pi-gen Trixie arm64 image tooling and explicit GitHub release gates.

## Security defaults

The image contains no default password, project SSH key, or wireless credential.
SSH is disabled. Initial account creation and optional key injection use
Raspberry Pi Imager. NTP access is limited to validated private CIDRs.

## Default LAN access

Chrony serves all standard private LAN ranges by default: `10.0.0.0/8`,
`172.16.0.0/12`, `192.168.0.0/16`, and IPv6 ULA `fc00::/7`. This covers common
subnets such as `192.168.1.0/24` while continuing to reject public, loopback,
link-local, CGNAT, multicast, and test ranges.

Operators can optionally narrow the allow-list after first boot:

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
