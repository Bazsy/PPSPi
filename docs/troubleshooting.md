# Troubleshooting

Start with:

```console
ppstime-status
sudo ppstime-test
sudo ppstime-diagnostics --output-dir /tmp
```

Work from hardware and kernel devices upward to GPSD and Chrony. Restarting
services cannot fix a missing overlay, wrong board revision, or poor sky view.

## No `/dev/serial0`

Check that `enable_uart=1` appears inside the PPSPi block in the active
`config.txt`, then reboot. Confirm the correct boot location:

```console
grep -n -E 'PPSPi|enable_uart' /boot/firmware/config.txt /boot/config.txt 2>/dev/null
```

Inspect aliases and UART messages:

```console
ls -l /dev/serial0
dmesg | grep -i -E 'ttyAMA|ttyS|uart'
```

If the model is not Pi 4 Model B, stop; the initial profile intentionally
rejects it.

## Serial console conflict

The GPS UART cannot simultaneously be a login or kernel console. `cmdline.txt`
must be one line and must not contain `console=serial0,...`, `console=ttyAMA...`,
or `console=ttyS...`. Keep `console=tty1` if present.

Re-run the installer to remove only conflicting serial console tokens. Do not
manually split `cmdline.txt` across lines.

## Serial device exists but no GPS data

Check service state and raw output:

```console
systemctl status gpsd
journalctl -u gpsd --since=-10minutes
gpspipe -r -n 20
```

Confirm `/etc/default/gpsd` lists `/dev/serial0 /dev/pps0`, uses `-n`, and that
no other process has the serial device open. Verify HAT seating, antenna power,
and `-s 115200` for a V6.0+ board. The Uputronics datasheet says older boards
defaulted to 9600; do not change the current profile unless the physical board
revision has been identified. Binary u-blox output may not look like readable
NMEA; `gpsmon` or `cgps -s` is a better protocol-aware check. Confirm GPSD's
detected speed with its `DEVICE` JSON report or `gpsctl`.

## GPS has no satellite fix indoors

Move the active antenna outdoors with a wide sky view. Check antenna connector
seating and wait through a cold acquisition. Buildings, metallized windows,
nearby transmitters, cable loss, and GNSS interference can prevent a fix.

No fix during image creation is expected. A deployed time server needs a valid
receiver fix before PPS can be trusted and locked.

## No `/dev/pps0`

Check the active boot block:

```console
grep -E 'pps-gpio|PPSPi' /boot/firmware/config.txt /boot/config.txt 2>/dev/null
lsmod | grep pps
dmesg | grep -i pps
```

The current HAT profile requires `dtoverlay=pps-gpio,gpiopin=18`. Reboot after
any boot change. If the device still does not appear, identify the physical HAT
revision before changing GPIO values.

## Suspected incorrect PPS GPIO

Do not probe random GPIOs in the profile. Confirm the board revision, schematic
or manufacturer documentation, and physical pin. Use a logic analyser or
oscilloscope referenced to ground to verify a one-hertz edge on physical pin 12
before changing configuration.

An unidentified older Uputronics board is a new hardware-profile task, not a
reason to silently change the current profile.

## PPS permission denied

Inspect ownership and the udev rule:

```console
ls -l /dev/pps0
udevadm info /dev/pps0
getent group dialout
```

PPSPi installs mode `0660`, group `dialout`. Chrony opens the refclock while it
still has the required startup privileges. Interactive users need membership in
`dialout` for direct `ppstest`; log out and back in after adding membership.

## PPS device exists but has no pulses

```console
sudo ppstest /dev/pps0
cgps -s
```

Many receivers emit or qualify PPS only after a valid fix. Check antenna and
sky view first. Then confirm edge polarity and HAT revision. Repeated timeout
with a 3D fix points to GPIO mapping, polarity, seating, or hardware failure.

## Chrony sees GPS but not PPS

Verify `/dev/pps0` and `ppstest` before Chrony. Then inspect:

```console
chronyd -p -f /etc/chrony/chrony.conf
chronyc sources -v
journalctl -u chrony --since=-10minutes
```

The generated line must use the configured PPS device and `lock GPS`. A missing
PPS device at Chrony startup may resolve after systemd retries GPSD, but Chrony
itself may need one restart after correcting the kernel device problem.

## PPS is visible but rejected

Chrony source symbols explain rejection. Common causes are:

- no valid/recent `GPS` sample to label PPS;
- clock initially more than half a second from the correct second;
- wrong edge polarity;
- GPS time disagreement during cold start or leap-information acquisition;
- network sources disagreeing with GNSS;
- insufficient samples after startup.

Use `chronyc sources -v`, `chronyc sourcestats -v`, and the Chrony journal. Do
not make GPS selectable or add a guessed one-second offset to hide the problem.

## RTC not detected

```console
i2cdetect -y 1
ls -l /dev/rtc*
dmesg | grep -i -E 'rtc|rv3028'
systemctl status ppstime-rtc-restore.service
```

The current board should appear at `0x52` and use
`dtoverlay=i2c-rtc,rv3028,backup-switchover-mode=3`. `UU` in `i2cdetect` can mean
the kernel driver owns the address. A different address or chip marking may
indicate an older HAT revision; identify it instead of trying arbitrary
overlays.

If the RTC loses time whenever Pi power is removed, inspect the RV-3028 backup
switch mode:

```console
sudo hwclock --param-get bsm --rtc /dev/rtc0
```

The Uputronics V6.0+ overlay profile requires raw mode `3` (level switching).
The `hwclock` ioctl uses a different kernel enum and reports that same mode as
`0x2`. A reported value of `0x0` means backup power is disabled even when the
board's supercapacitors are charged.

If the restore journal reports that `hwclock` is missing, install
`util-linux-extra`. If `/dev/rtc0` exists but `/dev/i2c-1` does not, load
`i2c-dev`. Current PPSPi installs do both automatically; these commands are for
diagnosing or repairing an older candidate image:

```console
sudo apt-get install util-linux-extra
sudo modprobe i2c-dev
```

On the first boot after the RTC has lost backup power, the kernel may report
`hctosys: unable to read the hardware clock` and `hwclock` may return
`Invalid argument`. Current PPSPi treats this specific state as an uninitialized
RTC and skips restore without failing the unit. Once Chrony is synchronized, the
guarded save timer initializes the RTC. Other read errors remain failures.

If `ppstime-status` reports permission denied for `/etc/ppstime/ppstime.env`,
the candidate predates the unprivileged status fix. The active profile contains
only validated hardware and service settings, not credentials. Repair its mode
with:

```console
sudo chmod 0644 /etc/ppstime/ppstime.env
```

## Time source remains network NTP

This is correct before GPS lock, while PPS is inactive, or while Chrony gathers
samples. Check GPS fix and PPS first. Once both are stable, inspect whether `PPS`
is selectable and whether `GPS` is visible as a `noselect` source.

Network fallback is a feature. It becomes a fault only when healthy GPS/PPS
never regain selection after sufficient settling time.

If PPS remains selected with reach `0` and an old `LastRx`, verify the generated
configuration does not mark PPS `prefer` and contains `maxclockerror 200` plus
`maxdistance 0.1`. Older candidates can retain a stale preferred PPS estimate
for an excessive period even though pulses stopped. Do not restart services to
hide the behavior; update PPSPi and repeat the antenna-loss test.

## LAN clients cannot query

Check listening sockets, allow rules, and client addressing:

```console
sudo ss -lunp | grep ':123'
sudo ppstime-config show
chronyc clients
```

The client must be inside an `NTP_ALLOW` CIDR. Apply changes with
`ppstime-config apply`. Also check host and network firewalls for UDP 123. PPSPi
does not open firewall rules because Raspberry Pi OS deployments differ.

## Raspberry Pi model differences

Pi 3, Pi 5, Pi 400, Compute Modules, and Zero models can differ in UART aliases,
GPIO controllers, boot firmware, thermal behavior, and header use. The current
model guard prevents accidental installation. Do not bypass it for a release;
create and test a separate profile and acceptance plan.

## Services repeatedly fail

```console
systemctl status chrony gpsd ppstime-rtc-restore.service
journalctl -b -u chrony -u gpsd -u ppstime-rtc-restore.service
```

GPSD waits a bounded 30 seconds for devices and uses a five-second restart
delay. Persistent retries mean a required kernel device is absent. The passive
health timer never restarts services, so it is not the source of a loop.
