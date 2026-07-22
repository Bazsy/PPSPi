# Health monitoring and soak testing

PPSPi monitors timing health without changing Chrony, GPSD, kernel PPS, or RTC
state. Monitoring never restarts services or selects a time source. Chrony
remains solely responsible for source selection and stale-source aging.

## Confirmed health states

`ppstime-healthcheck.timer` samples `ppstime-status --json`. Two consecutive
observations must agree before the confirmed state changes:

| State | Meaning |
| --- | --- |
| `HEALTHY_PPS` | Chrony is synchronized at Stratum 1 with active PPS selected. |
| `NETWORK_FALLBACK` | Chrony is synchronized, but PPS is not the healthy selected source. |
| `UNSYNCHRONIZED` | Chrony has no acceptable synchronized source. |
| `HARDWARE_ERROR` | Required GPS serial, GPSD, PPS device, or RTC state is unavailable. |
| `UNKNOWN` | The monitor has not yet received enough observations after boot. |

The timer starts after five minutes, runs every two minutes, and adds up to 15
seconds of jitter. A transition therefore normally requires roughly two to four
minutes after sampling starts. This hysteresis avoids alerting on a single
short-lived read failure or normal convergence.

The current state is stored atomically in `/run/ppstime/health-state.json` with
mode `0644`. Durations use the kernel boot clock, so normal wall-clock
corrections cannot make them jump backward. The file contains only enumerated
state, UTC timestamps, reasons, a small status summary, pending confirmation
state, and the most recent transition. It
contains no offsets, client/source addresses, credentials, or configuration.
Non-PPS/GPS selected sources are recorded only as `OTHER`. `/run` is
memory-backed and resets on reboot, which avoids periodic microSD writes. Use
the journal for transition history across the current boot.

## Inspect health

Show confirmed and pending state:

```console
ppstime-health
ppstime-health --json
```

Inspect monitor scheduling and transitions:

```console
systemctl list-timers ppstime-healthcheck.timer
journalctl -u ppstime-healthcheck.service --output=short-iso
```

The systemd wrapper deliberately returns success even if status collection,
state validation, or a hook fails. Warnings remain visible in the journal, but a
monitoring problem cannot create a systemd restart loop or alter timing.

## Prometheus textfile output

`ppstime-health --prometheus` emits a fixed-cardinality Prometheus text format:

```console
ppstime-health --prometheus
```

It includes one-hot confirmed-state gauges, current-state duration, last-check
timestamp, and pending-confirmation count. PPSPi does not install or expose a
metrics server. When an existing node exporter textfile collector is used, write
the output atomically from a separate operator-managed timer:

```console
sudo install -d -m 0755 /var/lib/node_exporter/textfile_collector
ppstime-health --prometheus | sudo tee \
  /var/lib/node_exporter/textfile_collector/ppstime.prom.tmp > /dev/null
sudo mv /var/lib/node_exporter/textfile_collector/ppstime.prom.tmp \
  /var/lib/node_exporter/textfile_collector/ppstime.prom
```

Do not expose a metrics endpoint beyond the trusted management network without
separate authentication and firewall policy.

## Optional transition hooks

Executable files in `/etc/ppstime/health-transition.d` run in lexical order only
when a state transition is confirmed. A healthy initial state is silent. A
confirmed degraded initial state and all later transitions invoke hooks.

The directory and each hook must:

- be owned by the health service's effective user (`root` in the appliance);
- not be group- or world-writable;
- be a regular, non-symlink file;
- have its owner execute bit set.

Each hook has a ten-second timeout, all hooks share a 15-second total budget,
and a timeout kills the hook's process group. Hooks receive only this minimal
environment:

| Variable | Value |
| --- | --- |
| `PPSTIME_HEALTH_FROM` | Previous confirmed state. |
| `PPSTIME_HEALTH_TO` | New confirmed state. |
| `PPSTIME_HEALTH_AT` | UTC transition timestamp. |
| `PPSTIME_HEALTH_PREVIOUS_DURATION_SECONDS` | Time spent in the previous state, or empty at startup. |
| `PPSTIME_HEALTH_REASONS` | Comma-separated non-secret reason identifiers. |

Hook output is discarded. Only its filename and failure type are journaled.
Keep notification credentials outside the repository and outside diagnostics;
store them in a root-readable file used by the operator's hook. Hooks inherit
the health service's systemd sandbox, empty capability set, minimal `PATH`, and
`NoNewPrivileges` policy.

Hooks are trusted operator code: the sandbox limits filesystem writes and
capabilities but does not make arbitrary root-owned scripts harmless. A hook is
notification plumbing, not remediation. It must not restart Chrony or GPSD,
rewrite PPSPi configuration, change the clock, or select sources.

Malformed state is preserved instead of silently discarded. The health-check
journal reports the validation error and leaves the last file untouched. After
inspection, reboot to recreate volatile state or remove
`/run/ppstime/health-state.json`; never replace it with hand-written state.

## Seven-to-fourteen-day release soak

Run a normal-use soak on the public release image before making timing-chain
changes. Keep the hardware, antenna, power supply, network topology, and PPSPi
configuration stable unless investigating a recorded fault.

At the start, record non-sensitive identity and baseline state:

```console
cat /etc/ppstime/build-info.json
ppstime-status
ppstime-health --json
systemctl show chrony gpsd -p ActiveState -p NRestarts
systemctl --failed --no-legend
```

During the soak, review health transitions daily rather than repeatedly changing
the appliance:

```console
ppstime-health
journalctl -u ppstime-healthcheck.service --since=-24hours --output=short-iso
```

At the end, collect final evidence:

```console
ppstime-status
sudo ppstime-test
ppstime-health --json
systemctl show chrony gpsd -p ActiveState -p NRestarts
systemctl --failed --no-legend
journalctl -u ppstime-healthcheck.service --since=-14days --output=short-iso
sudo ppstime-diagnostics --output-dir /tmp
```

Review the diagnostics archive locally before sharing it. Record environmental
context for every transition. Expected `NETWORK_FALLBACK` during a known antenna
interruption is different from unexplained `HARDWARE_ERROR` or
`UNSYNCHRONIZED` operation.

A successful soak has no unexplained hardware or synchronization transitions,
no failed units or service restart growth, a passing final deep test, and healthy
PPS selection after any explained recovery. Reboot resets the `/run` state, so
record the reboot and use the journal plus service restart counters when
interpreting duration.

Chrony offsets and monitor state are operational evidence only. They do not
establish independently traceable timing accuracy.
