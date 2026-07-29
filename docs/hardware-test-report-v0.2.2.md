# PPSPi hardware test report: v0.2.2

Status: **INHERITED TIMING BASELINE; PATCH-SPECIFIC HARDWARE CHECK PENDING**

v0.2.2 supersedes v0.2.1, whose image build failed before signing or asset
upload. The correction changes only how the installer invokes systemctl for the
default dashboard units. It does not alter GPSD, PPS, Chrony, RTC, boot overlays,
hardware profiles, or the supported physical target.

## Release identity

| Field | Value |
| --- | --- |
| Version | `0.2.2` |
| Source commit | Pending merge of the stable release PR |
| Image filename | `ppspi-0.2.2-raspios-trixie-arm64.img.xz` |
| Image hashes | Pending release workflow |
| Imager manifest | `ppspi-0.2.2-raspios-trixie-arm64.rpi-imager-manifest` |
| Application archive | `ppspi-0.2.2-application.tar.gz` |
| pi-gen commit | `ca8aeed0ae300c2a89f55ce9617d5f96a27e99e5` |

## Physical target and inherited evidence

The target remains Raspberry Pi 4 Model B Rev 1.5 with Uputronics GPS/RTC
Expansion Board Rev 6.4, RV-3028-C7 RTC, active external antenna, and trusted
private LAN.

The [v0.2.0 hardware report](hardware-test-report-v0.2.0.md) records physical
first boot, customization, operator/network/SSH policy, GPS at 115200 baud, 3D
fix, PPS, RTC, synchronized Stratum 1, deep tests, host health, reboot
persistence, loopback dashboard, bounded storage, and diagnostics privacy. Its
public assets and production signature were subsequently verified in
[issue #95](https://github.com/Bazsy/PPSPi/issues/95).

## Feature disposition

| Feature | Result | Notes |
| --- | --- | --- |
| GPS/PPS/RTC and Stratum 1 | INHERITED PASS | Unchanged from v0.2.0 |
| Dashboard sanitized API/UI | INHERITED/AUTOMATED PASS | Existing physical and complete regression coverage |
| Default dashboard enable/bind | AUTOMATED PASS | Installer, image, config, server, and unit tests |
| pi-gen dashboard enablement | CORRECTED | Separate enable/start operations; public build pending |
| Exact v0.2.0 migration | AUTOMATED PASS | Regeneration and transaction coverage |
| Production v0.2.0-to-v0.2.2 apply | PENDING | Requires published signed assets |
| Direct-LAN allow/deny boundary | PENDING | Requires appliance measurement |
| Production rollback/reapply | PENDING | Requires published signed assets |
| Exact public-image smoke | PENDING | Requires completed release workflow |
| Genuine reboot-required OS update | DEFERRED | Separate issue #95 scope |

## Post-publication procedure

After independent seven-asset verification, capture preservation sentinels; run
exact-version check/apply; verify timing, service/timer state, private Ethernet
and Wi-Fi access, an out-of-CIDR denial, bounded sampling, and no logging or
external requests; exercise rollback and exact restoration; then reapply if
desired. Record sanitized evidence in issue #95.

## Decision

Inherited hardware evidence and protected automated coverage are sufficient to
publish the corrected assets needed for the physical update test. Patch-specific
appliance checks remain **PENDING**, not PASS. PPSPi must not be the sole
production time source.
