# Host health monitoring

PPSPi monitors the Raspberry Pi host separately from GPS/PPS timing. A disk,
temperature, power, or update warning does not relabel healthy timing as
unsynchronized, and a GNSS outage does not hide a storage problem.

This feature is available in the current `0.2.0-dev` branch and is not included
in the published v0.1.0 image.

## Inspect host state

Show a current one-shot host assessment:

```console
ppstime-host-health
ppstime-host-health --json
```

Show confirmed timing and host states together:

```console
ppstime-health
ppstime-health --json
ppstime-health --prometheus
```

The existing two-minute health timer samples both collectors. Timing and host
state each require two matching observations before a confirmed transition.
Both use the same volatile `/run/ppstime/health-state.json`, but maintain
independent current state, duration, pending count, reasons, and last transition.

## Host states

| State | Meaning |
| --- | --- |
| `HEALTHY` | No configured host warning or critical condition was found. |
| `WARNING` | Attention is needed, but the appliance may continue operating. |
| `CRITICAL` | A current condition risks reliability or data integrity. |
| `UNKNOWN` | Two observations have not yet established host state. |

Examples of warnings include 5–15% disk/inode availability, temperature at or
above 75 °C, historical firmware throttling flags, failed/stale update checks,
and a pending required reboot. Examples of critical conditions include 5% or
less disk/inode availability, read-only root/boot filesystems, 85 °C or higher,
current under-voltage/throttling, a nonzero ext4 root error counter, or an update
success age of at least seven days.

An unavailable temperature or throttling source is a warning because those
signals are expected on the supported Raspberry Pi image. An unavailable ext4
error counter remains non-degrading because the root filesystem may not expose
that optional counter; source-availability metrics still report the gap. A
missing OS update marker remains `UNKNOWN` without degrading host state until
the unattended maintenance feature writes its first result. Prometheus exposes
fixed-cardinality source availability and one-hot update status for these cases.

## Collected sources

The standalone collector reads only bounded local state:

- `statvfs()` for root and boot free bytes, free percentage, inode percentage,
  and read-only flags. Available percentage uses blocks available to
  unprivileged processes divided by total blocks, so it may differ slightly from
  `df` when ext4 reserved blocks exist;
- `/sys/class/thermal/thermal_zone*/` for CPU temperature;
- `vcgencmd get_throttled` from Raspberry Pi OS `raspi-utils` for current and
  historical under-voltage, frequency-cap, throttling, and soft-temperature
  bits;
- `/proc/self/mountinfo` to require a real boot mount instead of treating an
  unmounted `/boot/firmware` directory as healthy;
- `/proc/self/mountinfo`, `/sys/dev/block`, and
  `/sys/fs/ext4/<root-device>/errors_count` for the persistent ext4 root error
  counter when available;
- `/var/lib/ppstime/os-update-state.json`, a closed non-secret marker reserved
  for PPSPi's OS maintenance job.

It does not scan arbitrary journals, files, processes, home directories, network
configuration, or credentials. It never deletes files, repairs/remounts a
filesystem, runs updates, restarts services, or reboots.

## Threshold configuration

Thresholds are validated keys in `/etc/ppstime/ppstime.env`, so they are also
included in `ppstime-backup` export/restore:

```ini
HOST_DISK_CRITICAL_PERCENT=5.0
HOST_DISK_WARNING_PERCENT=15.0
HOST_INODE_CRITICAL_PERCENT=5.0
HOST_INODE_WARNING_PERCENT=15.0
HOST_TEMPERATURE_CRITICAL_C=85.0
HOST_TEMPERATURE_WARNING_C=75.0
HOST_UPDATE_CRITICAL_HOURS=168.0
HOST_UPDATE_WARNING_HOURS=48.0
```

The schema is closed. Unknown/missing/non-finite values are rejected. Critical
percentages must be below warning percentages; temperature and update critical
values must be above warnings. Keep thresholds conservative and validate changes
before deployment. Use `ppstime-config set` for each value. Host-only threshold
changes take effect on the next sample and do not require restarting timing
services:

```console
sudo ppstime-config set HOST_TEMPERATURE_WARNING_C 75.0
ppstime-host-health --json
systemctl start ppstime-healthcheck.service
journalctl -u ppstime-healthcheck.service -n 20 --no-pager
```

A malformed threshold file makes standalone collection fail and causes the
passive health wrapper to journal a warning while retaining the previous
confirmed host state.

## Throttling flags

The JSON output preserves the firmware bit field and friendly active names.
Current flags produce `CRITICAL`; historical-only flags produce `WARNING` so a
past under-voltage event remains visible after voltage recovers.

Common causes include:

- inadequate or damaged power supply/cable;
- overloaded USB peripherals;
- insufficient cooling or blocked airflow;
- enclosure or ambient temperature problems.

Do not clear or ignore historical flags until the physical cause is understood.
A reboot may clear history without fixing power or cooling.

## Update freshness marker

The reserved marker has this exact schema:

```json
{
  "last_check_utc": "2026-07-22T12:00:00Z",
  "last_success_utc": "2026-07-22T12:00:00Z",
  "reboot_required": false,
  "result": "SUCCESS",
  "schema_version": 1
}
```

Only `SUCCESS` and `FAILED` results are accepted. Issue #67 will write this file
atomically after maintenance checks. Until then, a missing marker reports update
status `UNKNOWN` without a host warning. An invalid existing marker is a warning.

## Transition hooks

The existing `/etc/ppstime/health-transition.d` hooks receive host transitions
with:

```text
PPSTIME_HEALTH_DOMAIN=host
```

Timing transitions use `PPSTIME_HEALTH_DOMAIN=timing`. All existing ownership,
mode, timeout, minimal-environment, and notification-only rules still apply. A
confirmed healthy initial state remains silent; degraded startup and subsequent
host transitions invoke hooks.

## Prometheus metrics

`ppstime-health --prometheus` adds fixed-cardinality host metrics for:

- confirmed host state and duration;
- pending confirmations;
- root/boot available bytes and percentages;
- root/boot inode availability;
- CPU temperature;
- firmware throttling flags;
- root ext4 error count;
- last successful update-check age and required-reboot state.

No path, device, source address, process, or reason is used as an unbounded label.
See [health monitoring and soak testing](monitoring.md) for node-exporter
textfile integration.

## Diagnostics and troubleshooting

`ppstime-diagnostics` includes `host-health.json` as valid JSON. Review the
archive before sharing it; the host snapshot is designed to be non-secret, but
other diagnostic members may contain environment-specific operational details.

Host monitoring is detection, not remediation. For a critical result, preserve
state and diagnostics before changing the appliance. Storage errors or a
read-only filesystem may require replacing the SD card and restoring from a
[configuration backup](backup-restore.md).
