# Installation

This guide converts a clean Raspberry Pi OS Lite 64-bit Trixie installation
into a PPSPi appliance. For downloadable image use, see the README.

## Prerequisites

- Raspberry Pi 4 Model B;
- Uputronics GPS/RTC Expansion Board V6.0+ with RV-3028-C7 RTC;
- active antenna connected before power-on;
- wired Ethernet;
- Raspberry Pi OS Lite 64-bit Trixie;
- an initial user with `sudo` access;
- Internet access while packages are installed.

Identify older HAT revisions before installation. Do not assume their RTC is
compatible with the current profile; see [hardware](hardware.md).

## Prepare Raspberry Pi OS

Use Raspberry Pi Imager to install Raspberry Pi OS Lite (64-bit). Imager must
create the initial user because PPSPi contains no default password. Optionally
enable SSH with a public key in Imager. Boot the Pi, log in, and install updates:

```console
sudo apt update
sudo apt full-upgrade
sudo reboot
```

## Install PPSPi

```console
git clone https://github.com/Bazsy/PPSPi.git
cd PPSPi
sudo ./scripts/install.sh
sudo reboot
```

The installer:

1. validates every profile value without evaluating it as shell code;
2. rejects unsupported Raspberry Pi models;
3. installs only the required Debian packages;
4. installs PPSPi tools, udev rules, and systemd units;
5. updates the active Raspberry Pi boot configuration;
6. removes only serial-console kernel arguments that conflict with GPS;
7. writes GPSD and Chrony configuration;
8. enables timing and health timers;
9. disables `fake-hwclock` when a real RTC is configured.

Run the installer again after an interrupted setup. Repeated runs produce the
same managed content and do not duplicate boot lines.

## Configuration overrides

Select the initial profile explicitly:

```console
sudo PPSTIME_PROFILE=uputronics-gps-rtc-hat ./scripts/install.sh
```

Apply a custom file after defaults and the profile:

```console
sudo ./scripts/install.sh --config /path/to/site.env
```

A custom file uses one `KEY=VALUE` per line. Unknown keys, duplicates, shell
syntax, control characters, unsafe device paths, non-LAN CIDRs, and invalid
values are rejected. The shipped default already permits all RFC 1918 IPv4
space and IPv6 ULA. This example intentionally narrows access for a segmented
site:

```ini
NTP_ALLOW=192.168.50.0/24
NTP_FALLBACK_POOL=se.pool.ntp.org
DEFAULT_HOSTNAME=ppspi
```

The installer also accepts recognized exported variables as final overrides.
Use this sparingly so an installation remains reproducible.

## Files changed

PPSPi owns these locations:

- `/etc/ppstime/ppstime.env` — active validated configuration;
- `/etc/chrony/conf.d/ppstime.conf` — generated timing and server fragment;
- `/etc/default/gpsd` — GPSD devices and startup options;
- `/etc/udev/rules.d/80-ppstime.rules` — PPS permissions and systemd tag;
- `/usr/lib/ppstime/` — implementation and internal commands;
- `/usr/local/sbin/ppstime-*` — public command links;
- `/etc/systemd/system/ppstime-*` — RTC and health units;
- Chrony and GPSD drop-in directories.

The installer detects `/boot/firmware/config.txt` and `cmdline.txt` first, then
their legacy `/boot` locations. It adds one marked block to `config.txt` and
removes serial console tokens from the one-line `cmdline.txt`.

Before changing either boot file, it creates a sibling backup such as:

```text
config.txt.ppstime-20260718T120000Z.bak
cmdline.txt.ppstime-20260718T120000Z.bak
```

No new backup is created when content is already correct.

## First reboot and verification

After reboot:

```console
ppstime-status
sudo ppstime-test
systemctl status chrony gpsd
chronyc sources -v
```

Expected devices are `/dev/serial0`, `/dev/pps0`, and `/dev/rtc0`. An outdoor
antenna may need several minutes for a cold fix. `ppstime-test` intentionally
returns non-zero while essential timing components are unavailable.

Optionally narrow NTP access to the actual LAN when the broader private-range
default is not desired:

```console
sudo ppstime-config set NTP_ALLOW 192.168.50.0/24
sudo ppstime-config apply
```

`apply` validates all values, regenerates files, asks Chrony to parse its full
configuration, and only then restarts Chrony and GPSD.

## Dry-run and alternate roots

Inspect installer actions without writing:

```console
sudo ./scripts/install.sh --dry-run
```

Image builders and tests can target a mounted root filesystem:

```console
sudo ./scripts/install.sh --root /mnt/rootfs --skip-packages
```

Package installation for alternate roots belongs to the image builder. The
official pi-gen stage installs packages before invoking this mode.

## Recovery

If a boot setting prevents startup, mount the boot partition on another system
and restore the newest pre-PPSPi `config.txt` and `cmdline.txt` backups. Keep
their original names when restoring.

For a running system, inspect the generated block and active config before
changing anything. A complete manual removal should:

1. disable PPSPi timers and RTC restore;
2. remove PPSPi systemd units and drop-ins;
3. remove `/etc/chrony/conf.d/ppstime.conf` and restore GPSD defaults;
4. remove only the marked PPSPi boot block or restore backups;
5. reload systemd and udev rules;
6. reboot.

Do not blindly restore old boot files after unrelated firmware or OS changes.
