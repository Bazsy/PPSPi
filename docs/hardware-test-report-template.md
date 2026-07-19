# PPSPi hardware test report: `<version>`

Status: **NOT RUN**

## Artifact identity

| Field | Value |
| --- | --- |
| Version | |
| Git commit | |
| Image filename | |
| SHA-256 | |
| Imager manifest filename | |
| Raspberry Pi Imager version | |
| pi-gen commit | |
| Build date UTC | |

## Hardware and environment

| Field | Value |
| --- | --- |
| Raspberry Pi model/revision | |
| RAM | |
| Bootloader | |
| HAT product/revision marking | |
| RTC marking/address | |
| GNSS receiver/firmware | |
| Antenna and cable | |
| Storage | |
| Power supply | |
| Network topology (sanitised) | |
| Ambient temperature range | |
| Test start/end UTC | |

## Acceptance results

| # | Check | Result | Evidence / notes |
| ---: | --- | --- | --- |
| 1 | Fresh image boots | NOT RUN | |
| 2 | Imager hostname, user, locale, and key-only SSH | NOT RUN | |
| 3 | Ethernet address | NOT RUN | |
| 4 | `/dev/serial0` | NOT RUN | |
| 5 | GPSD data | NOT RUN | |
| 6 | `/dev/pps0` | NOT RUN | |
| 7 | PPS pulses | NOT RUN | |
| 8 | RTC device | NOT RUN | |
| 9 | RTC cold boot | NOT RUN | |
| 10 | Outdoor GPS fix | NOT RUN | |
| 11 | Chrony GPS and PPS | NOT RUN | |
| 12 | PPS selected | NOT RUN | |
| 13 | Stratum 1 | NOT RUN | |
| 14 | Allowed client query | NOT RUN | |
| 15 | Denied client query | NOT RUN | |
| 16 | Antenna-loss fallback | NOT RUN | |
| 17 | GPS restoration | NOT RUN | |
| 18 | Network-loss behavior | NOT RUN | |
| 19 | Reboot persistence | NOT RUN | |
| 20 | Sanitized diagnostics | NOT RUN | |

Use only `PASS`, `FAIL`, or `BLOCKED` in the final report.

## Timing observation

| Metric | Value / method |
| --- | --- |
| Observation duration | |
| Independent reference | |
| PPS availability | |
| Mean system offset | |
| RMS system offset | |
| Maximum absolute offset | |
| Mean PPS offset | |
| PPS standard deviation | |
| Root dispersion range | |
| Frequency/skew range | |
| Temperature range | |

## Failures and anomalies

List every failure, unexpected restart, source switch, time step, data gap, and
deviation from the documented procedure. Link issues for unresolved items.

## Security review

- [ ] No default password or embedded key was found.
- [ ] SSH remained disabled unless explicitly enabled in Imager.
- [ ] The chosen hostname, account, locale, timezone, and SSH policy were applied.
- [ ] NTP allowed and denied network tests behaved correctly.
- [ ] Diagnostics were inspected and sanitised.
- [ ] Public report contains no private site or device information.

## Decision

Release gate: **NOT APPROVED**

Tester(s), review date, and approval rationale:
