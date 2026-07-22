# PPSPi hardware test report: v0.1.0

Status: **APPROVED**

All applicable operational checks passed on the target appliance. Check 15 has
an explicitly approved deployment-scope waiver rather than a measured pass. The
fresh 24-hour open-sky observation passed strict analysis with no detected
operational anomaly.

## Artifact identity

| Field | Value |
| --- | --- |
| Candidate version | `0.1.0-dev` |
| Approved release version | `0.1.0` |
| Source commit | `f6cde4d72305ec1e31ffd76f9f247f0853615ff7` |
| Merge commit containing the candidate | `0f59bc3bf0daf9ee4e9ec1eff6f21afc1d6b8aea` |
| Image filename | `ppspi-0.1.0-dev-raspios-trixie-arm64.img.xz` |
| Compressed image SHA-256 | `9d57c17deeaa6ebac4d7d1cd649c290eebe2391b9b4c90d539f359253596cd15` |
| Extracted image SHA-256 | `5962d592ef138e8f5b769db95b6598cf945603e1b6c792d758a282bcae19eb04` |
| Imager manifest filename | `ppspi-0.1.0-dev-raspios-trixie-arm64.rpi-imager-manifest` |
| Raspberry Pi Imager version | `2.0.10` |
| pi-gen commit | `ca8aeed0ae300c2a89f55ce9617d5f96a27e99e5` |
| Build date UTC | `2026-07-20T17:16:27Z` |
| Manual image workflow | [Run 29762932486](https://github.com/Bazsy/PPSPi/actions/runs/29762932486) |
| Protected test workflow | [Run 29762876794](https://github.com/Bazsy/PPSPi/actions/runs/29762876794) |
| Protected lint workflow | [Run 29762876590](https://github.com/Bazsy/PPSPi/actions/runs/29762876590) |
| Observation archive | `ppstime-open-sky-20260721T084824Z.tar.gz` |
| Observation archive SHA-256 | `70635ca37b7034cf2bbf89077e54e3a0f5bd023d581bf54663b6768e01ae82dc` |

The GitHub artifact digest recorded for workflow artifact ID `8470418703` is
`sha256:084e74335bf3a4b969a96ba7e66f28ccbe486f4450a5e6ec1cd9d71570dc2fde`.
That digest covers the artifact ZIP and is not the raw image SHA-256.

## Hardware and environment

| Field | Value |
| --- | --- |
| Raspberry Pi model/revision | Raspberry Pi 4 Model B Rev 1.5 |
| RAM | Nominal 1 GB model; 906 MiB reported by `/proc/meminfo` |
| Bootloader | Raspberry Pi bootloader dated 2026-05-17 19:13:18 UTC (`1779045198`); VL805 firmware `000138c0` |
| HAT product/revision marking | Uputronics GPS/RTC Expansion Board, visibly marked `Rev 6.4` |
| RTC marking/address | RV-3028-C7 profile, physically detected at I2C `0x52`; package top-code was difficult to read and appeared to be `M306E4` / `302B` (unverified) |
| GNSS receiver/firmware | u-blox, SW ROM CORE 3.01 / SPG 3.01, protocol 18.00 |
| Antenna and cable | 2J `2J4D01MPCF-300LL100-C20GST`, 1561–1606 MHz active antenna with magnetic/ribbon mounting, 3 m LL100 cable, and male SMA; temporary open-sky metal-roof development placement with drip loop |
| Storage | SanDisk Ultra Go 32 GB microSD; Linux reported 29.7 GiB on `mmcblk0` |
| Power supply | Official Raspberry Pi 4 USB-C power supply, rated 5 V / 3 A |
| Network topology | Trusted private LAN, wired Ethernet, no public TCP 22 or UDP 123 forwarding |
| Ambient temperature range | 52.582–57.939 °C during the open-sky observation |
| Test period | 2026-07-20 through 2026-07-22; final observation 2026-07-21 08:48:24 UTC through 2026-07-22 08:48:35 UTC |

Precise coordinates, MAC addresses, private addresses, credentials, public NTP
source addresses, storage serials, and host fingerprints are intentionally not
included.

## Acceptance results

| # | Check | Result | Evidence / notes |
| ---: | --- | --- | --- |
| 1 | Fresh image boots | PASS | Untouched final candidate booted Raspberry Pi OS Trixie arm64. |
| 2 | Imager hostname, user, locale, and private-LAN SSH | PASS | Imager 2.0.10 loaded the local `cloudinit-rpi` manifest; customization completed with cloud-init `done` and no errors. Strong password SSH was used on the trusted private LAN; TCP 22 was not publicly exposed. |
| 3 | Ethernet address | PASS | Wired DHCP and SSH worked without Wi-Fi; carrier removal/restoration was tested separately. |
| 4 | `/dev/serial0` | PASS | Alias resolved to the header UART and delivered receiver data at 115200 baud. |
| 5 | GPSD data | PASS | GPSD 3.25 recognized u-blox protocol data and reported configured/reported 115200 baud. |
| 6 | `/dev/pps0` | PASS | Kernel source `pps@12.-1`, GPIO 18 interrupts, device ownership/mode, and direct Chrony access verified. |
| 7 | PPS pulses | PASS | Multiple runs captured at least ten consecutive one-second assert sequence increments. |
| 8 | RTC device | PASS | RV-3028 driver, I2C `0x52`, `/dev/rtc0`, and valid reads verified. |
| 9 | RTC cold boot | PASS | More than 30 minutes unpowered; backup level mode persisted and RTC restored plausible time before network/GNSS synchronization. |
| 10 | Outdoor GPS fix | PASS | Open-sky placement produced stable 3D fixes with 15–17 satellites used, HDOP 0.65–0.74, and PDOP 1.19–1.42. |
| 11 | Chrony GPS and PPS | PASS | GPS coarse source and direct PPS both reached octal `377`; GPS remained `noselect`. |
| 12 | PPS selected | PASS | Direct PPS selected as `#*` without unconditional `prefer`. |
| 13 | Stratum 1 | PASS | Normal leap status and appliance Stratum 1 recorded repeatedly. |
| 14 | Allowed client query | PASS | Linux/local checks and ten consecutive Windows `w32tm /stripchart` responses succeeded after Ethernet recovery. |
| 15 | Denied client query | WAIVED | Deployment intentionally allows all RFC 1918 and IPv6 ULA ranges, has no public forwarding, and has no second routed out-of-scope LAN solely for this test. Strict configuration validation rejects public/default-route CIDRs. This is not a measured PASS. |
| 16 | Antenna-loss fallback | PASS | On the untouched generated image, stale PPS was demoted and network time selected within 171 seconds; services remained active with zero restarts. |
| 17 | GPS restoration | PASS | Reconnecting the antenna restored 3D, GPS/PPS reach `377`, `#* PPS`, and Stratum 1 without restarts. |
| 18 | Network-loss behavior | PASS | Ethernet was absent for approximately 2.5 minutes while PPS remained selected at Stratum 1; services had zero restarts and the LAN client recovered after carrier return. |
| 19 | Reboot persistence | PASS | Non-default configuration, generated files, services, RTC behavior, and timing chain persisted across reboot. |
| 20 | Sanitized diagnostics | PASS | Mode-0600 archive had expected scoped members; filename/content review found no credential material, unsafe paths, or coordinates in the tested no-fix bundle. |

Detailed chronological evidence and sanitized maintainer decisions are recorded
in [hardware acceptance issue #17](https://github.com/Bazsy/PPSPi/issues/17).

## Timing observation

| Metric | Value / method |
| --- | --- |
| Observation duration | 24.003 hours; 1,403 minute samples; 97.42% sample coverage; strict analyzer PASS |
| Independent reference | No traceable independent timing reference; Chrony statistics are operational evidence only |
| PPS availability | `#* PPS` in 100% of 1,403 source samples; 100% of 1,402 kernel assert intervals advanced; zero reach-zero samples; maximum `LastRx` 1 second |
| Mean system offset | +0.369 µs |
| RMS system offset | 8.841 µs |
| Maximum absolute offset | 122.676 µs |
| Mean PPS offset | -1.300 µs |
| PPS standard deviation | 20.895 µs population standard deviation; maximum absolute sample 256.165 µs |
| Root dispersion range | 35.523 µs–1.019832 ms; mean 301.612 µs |
| Frequency/skew range | Frequency -32.213–69.078 ppm (mean 18.978 ppm); skew 0.017–127.912 ppm (mean 2.599 ppm) |
| Temperature range | 52.582–57.939 °C; mean 55.433 °C |
| GNSS quality | 100% of 281 captures were 3D; 12–19 satellites used (mean 15.72); HDOP 0.61–1.26; PDOP 1.02–2.07 |
| Operational continuity | Chrony/GPSD active in all 1,403 samples with zero restarts; zero failed units; zero throttling events; final deep test PASS |

No accuracy claim will be derived from Chrony's printed resolution alone.

## Failures and anomalies

The acceptance campaign intentionally retained failures instead of hiding them:

- first-boot/cloud-init, RTC runtime, RTC backup-mode, and unprivileged status
  defects were found, fixed, rebuilt, and retested;
- GPSD 3.25 required `/run/chrony.clk.serial0.sock` for coarse serial time;
- the deep NTP probe required correct `ss` parsing and explicit loopback access;
- stale PPS required bounded Chrony source aging and removal of unconditional
  preference;
- the first observation was invalidated after about eleven hours by marginal
  indoor-window/forest GNSS reception. Issue
  [#51](https://github.com/Bazsy/PPSPi/issues/51) confirmed this was an RF
  placement incident: the same hardware became stable with an external open-sky
  antenna and no software change.

No unexplained service restart, failed unit, source transition, PPS interruption,
GNSS fix loss, throttling event, or time step was detected in the final
observation.

## Security review

- [x] No default password, embedded credential, or project SSH key was found.
- [x] SSH remained disabled in the pristine image and was enabled only through
  Imager customization.
- [x] The test used a strong, unique password on a trusted private LAN; TCP 22
  was not publicly exposed.
- [x] The chosen account and first-boot customization completed successfully.
- [x] Allowed NTP access was measured; check 15 has an explicit, documented
  scope waiver and is not represented as a measured pass.
- [x] Diagnostics were inspected for scope, unsafe paths, and sensitive content.
- [x] The public report excludes private site and device identifiers.
- [x] Repository rulesets, immutable Action pins, secret scanning/push
  protection, private vulnerability reporting, vulnerability alerts,
  Dependabot security fixes, and the release environment were reviewed.

## Decision

Release gate: **APPROVED FOR v0.1.0 PUBLICATION**

The maintainer explicitly accepts check 15 as **WAIVED** for the declared
deployment. Every routed private range is intentionally allowed, public/default
CIDRs are rejected by configuration validation, and no public forwarding or
separate routed out-of-scope client exists. No denied-client measurement is
represented as a pass.

This approval covers the runtime-equivalent v0.1.0 candidate on the documented
Raspberry Pi 4 / Uputronics Rev 6.4 hardware. The tagged release rebuild must
still pass automated image/asset validation, public checksum and metadata
verification, Imager loading, credential review, and the documented shortened
post-release smoke boot.

Tester and approver: repository maintainer. Approved 2026-07-22 based on all
applicable hardware checks, the explicit check-15 scope waiver, and the 24-hour
open-sky observation, which completed without a detected anomaly.
