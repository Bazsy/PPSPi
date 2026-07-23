# Diagnostics

PPSPi has four management commands. They read the validated active configuration
from `/etc/ppstime/ppstime.env` and do not require a logged-in desktop session.

## `ppstime-status`

The default output is a concise operational summary:

```console
ppstime-status
```

Important fields are GPS fix, PPS activity, RTC state, Chrony synchronization,
selected source, Stratum, and client count. `PPS` selected at Stratum 1 is the
target after the receiver has a valid fix and Chrony has settled.

When run unprivileged, `ppstime-status` first attempts the normal `hwclock`
read. If `/dev/rtc0` is root-only, it falls back to the matching world-readable
Linux sysfs RTC name/date/time. This fallback is read-only; setting the RTC and
restoring the system clock remain privileged operations.

PPS activity is also checked without device write access by observing the
world-readable Linux PPS assert sequence in sysfs across one pulse period. The
deeper root-only test continues to use `ppstest` for detailed pulse evidence.

Machine-readable output has a versioned stable structure:

```console
ppstime-status --json
```

```json
{
  "chrony": {
    "root_dispersion_seconds": "0.000018000",
    "selected_source": "PPS",
    "state": "SYNCHRONIZED",
    "stratum": 1,
    "system_offset_seconds": "0.000002300"
  },
  "gps": {
    "configured_baud": 115200,
    "device": "/dev/serial0",
    "fix": "3D",
    "reported_baud": 115200,
    "satellites_used": 4,
    "serial": "OK",
    "service": "ACTIVE"
  },
  "ntp_clients": 4,
  "pps": {
    "device": "/dev/pps0",
    "exists": true,
    "pulses": "ACTIVE"
  },
  "profile": "uputronics-gps-rtc-hat",
  "rtc": {
    "device": "/dev/rtc0",
    "status": "OK",
    "time": "2026-07-18 12:00:00.123456+00:00"
  },
  "schema_version": 1
}
```

Numeric timing measurements are strings to preserve Chrony's printed precision
and sign. Unavailable values are JSON `null`.

## `ppstime-test`

Run deeper deployment checks as root:

```console
sudo ppstime-test
sudo ppstime-test --json
```

Checks cover:

- package commands;
- boot overlays;
- serial and PPS devices;
- GPSD service and message flow;
- GPS fix as a non-essential warning;
- PPS pulses;
- RTC read access;
- Chrony synchronization, configuration syntax, and selected source;
- UDP port 123;
- a local NTP query;
- PPSPi-related systemd health.

An essential failure produces exit status 1. Configuration or invocation errors
produce status 2. A missing current GPS fix is a warning by itself, but failures
that break the core timing chain remain non-zero.

## `ppstime-config`

Show the complete active file:

```console
sudo ppstime-config show
sudo ppstime-config show --json
```

Set one value without immediately restarting services:

```console
sudo ppstime-config set NTP_ALLOW 192.168.1.0/24
```

Apply all pending values:

```console
sudo ppstime-config apply
```

Apply regenerates files, runs a full Chrony parse, and only then restarts Chrony
and GPSD. The hardware profile name cannot be changed in place; reinstall with
`scripts/install.sh --profile` so profile defaults remain coherent.

## `ppstime-diagnostics`

```console
sudo ppstime-diagnostics --output-dir /tmp
```

The result is a mode-0600 archive named
`ppstime-diagnostics-<UTC timestamp>.tar.gz`. It contains:

- sanitised active configuration;
- only relevant boot lines;
- package and kernel versions;
- Raspberry Pi model;
- matching `/dev` listings;
- Chrony, GPSD, RTC, and PPSPi unit status;
- up to 500 related journal entries from the last 24 hours;
- Chrony tracking, sources, source statistics, and clients;
- bounded `gpspipe`, `ppstest`, and `hwclock` samples.

It does not intentionally collect `/etc/shadow`, home directories, SSH files,
wireless profiles, environment variables, arbitrary journal units, or full
network configuration. Keys containing password, secret, token, private, Wi-Fi,
SSID, or key terminology are redacted if future profiles add them.

Always inspect an archive before sharing it. Device paths, host timing behavior,
client addresses in `chronyc clients`, and related logs may still be sensitive
in your environment.

## Passive health monitor

`ppstime-healthcheck.timer` starts after five minutes and samples status every
two minutes with a small randomized delay. Two matching observations are needed
to confirm `HEALTHY_PPS`, `NETWORK_FALLBACK`, `UNSYNCHRONIZED`, or
`HARDWARE_ERROR`. The non-secret current state is stored under `/run/ppstime`
and included in diagnostics as `health-state.json`.

It does not restart services and returns success even when collection or a
notification hook fails, preventing ordinary antenna outages or monitoring
faults from becoming systemd restart loops. Inspect current state with:

```console
ppstime-health
ppstime-health --json
ppstime-health --prometheus
```

Inspect it with:

```console
systemctl list-timers ppstime-healthcheck.timer
journalctl -u ppstime-healthcheck.service
```

See [health monitoring and operational checks](monitoring.md) for state
semantics, guarded local hooks, Prometheus textfile integration, and optional
runtime evidence collection.
