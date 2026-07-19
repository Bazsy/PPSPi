# Raspberry Pi 4 hardware acceptance test plan

This plan is mandatory before an image is described as hardware-tested. Run it
on the exact image artifact and record results using
`hardware-test-report-template.md`.

## Test identity

Record before testing:

- PPSPi version, Git commit, image SHA-256, and Imager manifest filename;
- `build-info.json`;
- Raspberry Pi model, revision, RAM, and bootloader version;
- Uputronics product/revision markings and RTC chip marking;
- antenna model, cable, and approximate sky conditions;
- storage media and power supply;
- network topology and allowed/denied client CIDRs;
- test start/end UTC and ambient temperature range.

Do not include device serial numbers, public IPs, credentials, or precise site
location in a public report.

## Acceptance checks

For every check record **PASS**, **FAIL**, or **BLOCKED**, evidence, timestamp,
and notes. `BLOCKED` does not count as release acceptance.

### 1. Fresh image boots

Flash the released XZ after verifying SHA-256. Confirm a Pi 4 reaches first boot
without modifying the image filesystem.

### 2. First-boot user creation works

Open the supplied `.rpi-imager-manifest` in the current Raspberry Pi Imager.
Record the Imager version and confirm the PPSPi entry exposes `cloudinit-rpi`
customisation. Set a non-default hostname, initial username, locale, keyboard,
and time zone. Enable SSH with a strong, unique operator password on a trusted
private LAN. After first boot, verify every selected value, password SSH access,
and that no known/default `pi` password grants access. Confirm TCP port 22 is not
forwarded or otherwise exposed to the public Internet. Public-key SSH is an
optional hardening path, not a release requirement.

When Wi-Fi is part of the tested deployment, also configure it in Imager and
record successful association without exposing the credential. The initial
wired-Ethernet target does not require Wi-Fi to pass.

### 3. Ethernet obtains an address

Confirm wired DHCP or the operator's configured network works without Wi-Fi.

### 4. Serial alias exists

Confirm `/dev/serial0` exists and resolves to the expected header UART.

### 5. GPSD receives valid data

Capture bounded `gpspipe` or `gpsmon` evidence showing recognized NMEA/UBX data.
Confirm GPSD reports 115200 bps for a V6.0+ Uputronics board.

### 6. PPS device exists

Confirm `/dev/pps0`, udev ownership/mode, and kernel `pps-gpio` messages.

### 7. PPS pulses are active

Record at least ten consecutive increasing `ppstest /dev/pps0` assert events.

### 8. RTC device exists

Confirm the RV-3028 driver, I2C address `0x52`, `/dev/rtc0`, and a valid read.

### 9. Cold boot restores RTC time

Synchronize, shut down, remove network and antenna access, power off long enough
to be meaningful, then boot. Compare RTC-restored time with an independent UTC
reference and record error.

### 10. Outdoor GPS fix is acquired

Record time to first valid fix and satellites used under described conditions.

### 11. Chrony sees GPS and PPS

Save `chronyc sources -v` and `sourcestats -v` after stabilization.

### 12. PPS becomes selected

Confirm `#* PPS`, with `GPS` visible as a non-selected label source.

### 13. Server reports Stratum 1

Record `chronyc tracking` with normal leap status, Stratum 1, offsets, and root
dispersion.

### 14. Allowed LAN client can query

From an address inside `NTP_ALLOW`, query UDP 123 and record offset/stratum.

### 15. NTP is denied outside configured networks

From a routed address outside `NTP_ALLOW`, verify no NTP response. Confirm this
is Chrony access control, not only an intervening firewall.

### 16. Antenna removal causes graceful fallback

Remove or shield the antenna. Record loss detection, no service crash/restart
loop, and eventual network-source selection.

### 17. GPS restoration returns to PPS

Restore antenna view. Record time to fix and time until PPS is selected again.

### 18. Network loss does not crash services

With GPS/PPS healthy, disconnect Ethernet. Confirm Chrony/GPSD stay active and
PPS remains selected. Restore Ethernet and verify clients recover.

### 19. Reboot preserves configuration

Set a non-default private `NTP_ALLOW`, reboot, and verify active configuration,
generated files, services, and timing chain remain correct.

### 20. Sanitized diagnostics archive works

Generate a bundle, inspect every member, and confirm it contains useful timing
evidence but no SSH keys, password hashes, wireless credentials, tokens,
unrelated logs, or unexpected personal information.

## Timing observation

For a release candidate, collect at least 24 hours of stable operation after
initial convergence. Record:

- selected-source availability;
- mean/RMS/max system offset;
- PPS source offset and standard deviation;
- root dispersion;
- oscillator frequency and skew;
- temperature range;
- network and GNSS outages during the window.

Do not claim nanosecond or microsecond accuracy from Chrony's printed precision
alone. Measurement requires an independent traceable reference and a documented
method.

## Pass criteria

The release gate passes only when all 20 checks pass on the target hardware,
the observation window has no unexplained timing steps or service failures, and
the report identifies the exact public artifact candidate.
