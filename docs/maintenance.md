# Unattended OS maintenance

PPSPi can install signed Raspberry Pi OS/Debian package updates in one weekly
maintenance window. It uses the distribution-native `unattended-upgrades` tool,
never reboots unconditionally, and does not update PPSPi application code.

This feature is available in `0.2.0-dev`, not the published v0.1.0 image.

## Default policy

The default configuration is:

```ini
OS_UPDATES_ENABLED=true
OS_UPDATE_SCOPE=security
OS_MAINTENANCE_DAY=Sun
OS_MAINTENANCE_TIME=04:00
OS_MAINTENANCE_TIMEZONE=UTC
OS_MAINTENANCE_RANDOM_DELAY_MINUTES=30
OS_REBOOT_ENABLED=true
```

PPSPi disables the competing `apt-daily.timer` and
`apt-daily-upgrade.timer`, then enables `ppstime-maintenance.timer`. The default
APT policy permits Debian security updates only. It disables
`unattended-upgrades` built-in reboot behavior so PPSPi can perform package,
clock, and RTC preflight itself.

The timer uses `Persistent=true`: if the Pi is powered off during the weekly
window, systemd runs the missed job shortly after the next boot or timer
re-enable rather than waiting a full week.

`OS_UPDATE_SCOPE=all` additionally permits configured Debian, Debian updates,
Raspbian, and Raspberry Pi Foundation origins. This broader policy is opt-in and
can introduce more change than security-only updates.

## Weekly maintenance flow

At the configured weekly window, with a bounded randomized delay:

1. acquire a non-blocking PPSPi maintenance lock;
2. run `apt-get update`;
3. run `unattended-upgrade --verbose` using the PPSPi origin policy;
4. require `dpkg --audit` to report no incomplete package state;
5. atomically write `/var/lib/ppstime/os-update-state.json`;
6. stop when `/run/reboot-required` is absent;
7. when a reboot is required and enabled, require synchronized Chrony, require a
  real RTC save (a skipped save is failure), and audit packages again;
8. write a persistent reboot marker containing reason and current kernel boot ID;
9. request `systemctl reboot`.

A package failure writes a `FAILED` update result while preserving the previous
successful timestamp. The service fails visibly in systemd and never continues
to reboot. Network/power interruption cannot create a PPSPi reboot loop.

## Reboot acknowledgment

Ten minutes after boot, `ppstime-maintenance-post-boot.timer` starts the
acknowledgment service only when a reboot marker exists. It compares the current
boot ID with the requesting boot ID:

- the same boot ID means the requested reboot did not complete; the marker is
  retained and the service fails;
- a changed boot ID runs deep PPSPi and timing/host health checks, records
  bounded evidence in `/var/lib/ppstime/maintenance-post-boot.json`, acknowledges
  exactly one completed reboot, removes the marker, and updates required-reboot state;
- no marker means no action.

PPSPi never schedules another reboot merely because the persistent marker
exists. A later weekly update run can request a new reboot only when the OS still
provides `/run/reboot-required`.

## Inspect and operate

Show the configured schedule:

```console
systemctl list-timers ppstime-maintenance.timer
```

Show non-secret update/reboot state:

```console
ppstime-maintenance status
ppstime-host-health
```

Run the maintenance job now:

```console
sudo systemctl start ppstime-maintenance.service
journalctl -u ppstime-maintenance.service -n 100 --no-pager
```

A manual start can install packages and reboot when required. Do not run it when
an interruption would be unsafe.

Pause automatic runs without changing policy:

```console
sudo systemctl disable --now ppstime-maintenance.timer
```

Re-enable the configured schedule:

```console
sudo systemctl enable --now ppstime-maintenance.timer
```

Disable through persistent PPSPi configuration:

```console
sudo ppstime-config set OS_UPDATES_ENABLED false
sudo ppstime-config apply
```

This keeps the distribution `apt-daily*` timers disabled as well, so setting
`OS_UPDATES_ENABLED=false` means no automatic OS updates until PPSPi maintenance
or another operator-managed update scheduler is enabled.

## Change the maintenance window

Set one or more validated values, then apply:

```console
sudo ppstime-config set OS_MAINTENANCE_DAY Sun
sudo ppstime-config set OS_MAINTENANCE_TIME 04:00
sudo ppstime-config set OS_MAINTENANCE_TIMEZONE Europe/Stockholm
sudo ppstime-config set OS_MAINTENANCE_RANDOM_DELAY_MINUTES 30
sudo ppstime-config apply
```

The day must be `Mon` through `Sun`, time uses 24-hour `HH:MM`, timezone is `UTC`
or an IANA name, and randomized delay is 0–360 minutes. These keys are included
in `ppstime-backup` archives. `apply` regenerates both APT policy and the systemd
timer.

To prevent automatic reboot while still installing updates:

```console
sudo ppstime-config set OS_REBOOT_ENABLED false
sudo ppstime-config apply
```

Host health then reports a pending reboot until an operator reboots safely.

## State and diagnostics

`/var/lib/ppstime` is root-owned mode `0755`; its non-secret JSON state files are
mode `0644` so `ppstime-maintenance status` and host health work unprivileged.
The update marker has a closed non-secret schema containing only:

- last check UTC;
- last successful check UTC;
- `SUCCESS` or `FAILED`;
- whether the OS requires reboot;
- schema version.

Host health reports failed/stale checks and pending reboot without scraping broad
package logs. `ppstime-diagnostics` includes the state marker, reboot marker, the
maintenance units, and only the PPSPi maintenance journal units. Review every
archive before sharing.

## Recovery and boundaries

Create a [configuration backup](backup-restore.md) before enabling unattended
maintenance on an existing appliance. This feature updates signed OS packages;
it does not update PPSPi application files or cross PPSPi versions. Verified
application update and rollback remain issue #68.

If package management is interrupted, do not repeatedly trigger the timer. Review
`dpkg --audit`, APT/unattended-upgrades logs, the PPSPi maintenance journal, disk
space, and power stability. Repair package state manually before another run.
PPSPi never invokes automatic filesystem repair, package-force options, source
changes, or rollback of Debian packages.
