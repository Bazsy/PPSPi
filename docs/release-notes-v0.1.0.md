# PPSPi v0.1.0 release notes

PPSPi v0.1.0 introduces the source-controlled installer, image, and diagnostics
milestone for a GPS/PPS Stratum-1 server based on Raspberry Pi OS Lite 64-bit
Trixie.

> [!NOTE]
> The four image assets are rebuilt and attached after the GitHub Release is
> published. If they are not yet visible, the release workflow is still running;
> wait for it to complete before downloading or flashing.

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
  customisation;
- RV-3028 level-switching backup mode for power-loss retention;
- bounded stale-PPS aging with automatic network fallback and PPS recovery;
- strict built-image and exact release-asset validation;
- local NTP health checks and unprivileged RTC/PPS status through validated
  sysfs data;
- reproducible 24-hour observation analysis with human, JSON, and strict modes.

## Hardware acceptance

The approved hardware target is:

- Raspberry Pi 4 Model B Rev 1.5;
- Uputronics GPS/RTC Expansion Board visibly marked `Rev 6.4`;
- RV-3028-C7 RTC at I2C address `0x52`;
- external active GNSS antenna with a broad open-sky view;
- wired private LAN.

All applicable checks passed. The denied-client test is explicitly **WAIVED**,
not passed, for the declared deployment: all routed private ranges are
intentionally allowed, public/default CIDRs are rejected by validation, no
public forwarding exists, and no separate routed out-of-scope client was
available solely for this test.

The final open-sky observation ran for 24.003 hours with 1,403 minute samples
and 97.42% coverage. Strict analysis reported:

- PPS selected in 100% of source/tracking samples;
- 100% kernel PPS assert-sequence advancement and zero reach-zero samples;
- 100% 3D GNSS captures, with 12–19 satellites used;
- system offset mean +0.369 µs, RMS 8.841 µs, and maximum absolute 122.676 µs;
- PPS offset mean -1.300 µs and population standard deviation 20.895 µs;
- root dispersion 35.523 µs–1.019832 ms;
- zero service restarts, inactive samples, failed units, or throttling events;
- passing final deep validation and no detected anomaly.

These are operational Chrony statistics, not an independently traceable
accuracy measurement.

## Security defaults

The image contains no default password, project SSH key, or wireless credential.
SSH is disabled. Initial account creation and optional password or public-key
configuration use Raspberry Pi Imager through the supplied manifest. Password
SSH is accepted only with a strong, unique password on a trusted private LAN and
must not be publicly exposed. NTP access is limited to validated private CIDRs.

The release workflow uses the repository-scoped `GITHUB_TOKEN`, immutable action
and container pins, a dedicated environment, rebuilt-image inspection, and an
exact four-asset validation gate before upload.

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
- [approved hardware report](hardware-test-report-v0.1.0.md);
- tested candidate compressed image SHA-256:
  `9d57c17deeaa6ebac4d7d1cd649c290eebe2391b9b4c90d539f359253596cd15`;
- tested runtime source commit:
  `f6cde4d72305ec1e31ffd76f9f247f0853615ff7`;
- pinned pi-gen commit:
  `ca8aeed0ae300c2a89f55ce9617d5f96a27e99e5`.

The published image is rebuilt from the reviewed `v0.1.0` tag and therefore is
not expected to have the same compressed checksum as the temporary candidate.
Use the `.sha256` asset attached to the GitHub Release, then complete the public
asset and shortened smoke checks in the
[release process](release-process.md).
