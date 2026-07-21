# PPSPi v0.1.0 draft release notes

> Draft only. Operational Raspberry Pi 4/Uputronics checks have passed or have
> an explicit scope waiver. Do not publish until the open-sky observation,
> hardware report, and release-readiness checklist are approved.

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
- pinned pi-gen Trixie arm64 image tooling and explicit GitHub release gates;
- Raspberry Pi Imager 2.x `cloudinit-rpi` manifests for release and local image
  customisation.
- RV-3028 level-switching backup mode for power-loss retention;
- bounded stale-PPS aging with automatic network fallback and PPS recovery;
- strict built-image inspection, local NTP health checks, and unprivileged
  RTC/PPS status through validated sysfs data.

## Security defaults

The image contains no default password, project SSH key, or wireless credential.
SSH is disabled. Initial account creation and optional password or public-key
configuration use Raspberry Pi Imager through the supplied manifest. Password
SSH is accepted only with a strong, unique password on a trusted private LAN and
must not be publicly exposed. NTP access is limited to validated private CIDRs.

## Default LAN access

Chrony serves all standard private LAN ranges by default: `10.0.0.0/8`,
`172.16.0.0/12`, `192.168.0.0/16`, and IPv6 ULA `fc00::/7`. This covers common
subnets such as `192.168.1.0/24` while continuing to reject user-configured
public, loopback, link-local, CGNAT, multicast, and test ranges. Exact loopback
host routes are rendered only for the appliance's local NTP health query.

Operators can optionally narrow the allow-list after first boot:

```console
sudo ppstime-config set NTP_ALLOW 192.168.1.0/24
sudo ppstime-config apply
```

## Known limitations

- Release acceptance status: **IN PROGRESS**; the fresh 24-hour open-sky
  observation remains pending.
- Only Raspberry Pi 4 Model B is in scope.
- Older Uputronics HAT revisions are not automatically supported.
- GPS serial offset remains uncalibrated and the GPS source is intentionally
  non-selectable.
- A continuously reliable external antenna view is required. Indoor placement
  behind modern glazing or obstructed by forest/buildings may produce
  geometry-dependent fix and PPS loss.
- Civilian GNSS and unauthenticated public NTP are not cryptographic proof of
  UTC and remain susceptible to interference, spoofing, and path delay.
- Printed Chrony offsets are not an independently traceable accuracy claim.
- This milestone does not claim production readiness.

## Verification

- protected test workflow:
  [run 29762876794](https://github.com/Bazsy/PPSPi/actions/runs/29762876794);
- protected lint workflow:
  [run 29762876590](https://github.com/Bazsy/PPSPi/actions/runs/29762876590);
- manual image workflow:
  [run 29762932486](https://github.com/Bazsy/PPSPi/actions/runs/29762932486);
- [in-progress hardware report](hardware-test-report-v0.1.0.md);
- candidate compressed image SHA-256:
  `9d57c17deeaa6ebac4d7d1cd649c290eebe2391b9b4c90d539f359253596cd15`;
- candidate source commit:
  `f6cde4d72305ec1e31ffd76f9f247f0853615ff7`;
- pinned pi-gen commit:
  `ca8aeed0ae300c2a89f55ce9617d5f96a27e99e5`.

The final notes must replace candidate/pending language with the tagged release
commit, public asset checksum, approved report, and post-release verification.
