# Chrony GPS/PPS design

## Generated sources

PPSPi generates a fragment in `/etc/chrony/conf.d/ppstime.conf`. The essential
shape is:

```text
refclock SOCK /run/chrony.serial0.sock refid GPS ... noselect
refclock PPS /dev/pps0 refid PPS lock GPS poll 0 dpoll 0 prefer ...
pool pool.ntp.org iburst maxsources 4
allow 10.0.0.0/8
allow 172.16.0.0/12
allow 192.168.0.0/16
allow fc00::/7
```

The complete file is rendered from validated values and includes comments. Do
not edit it directly; use `ppstime-config`.

## GPS SOCK source

GPSD sends serial-derived samples to the Unix datagram socket that Chrony
creates for the basename of the GPS device. `/dev/serial0` therefore maps to
`/run/chrony.serial0.sock`.

The source has:

- `refid GPS` so it can label and lock PPS;
- `poll 2` and `filter 4` to smooth serial messages;
- `precision 1e-1` and `delay 0.2` to represent coarse delivery;
- configurable `CHRONY_GPS_OFFSET`, default `0.0`;
- `noselect` so an uncalibrated serial delay never outranks PPS or network NTP.

Do not copy placeholder offsets from examples online. Measure the receiver,
firmware, UART, and system combination over several hours before changing the
offset.

## Direct kernel PPS source

Chrony's PPS driver reads `/dev/pps0` directly. This avoids userspace PPS
timestamp jitter and gives the configuration an explicit `lock GPS` relationship.
The normal assert/rising event is used unless the profile selects a falling
edge, in which case both the kernel overlay and Chrony use their falling-edge
options.

`poll 0` processes one-second groups, `dpoll 0` matches the one-hertz pulse,
`precision 1e-7` advertises a conservative sub-microsecond source precision,
and `prefer` keeps a valid PPS source ahead of network sources.

PPS alone is not usable after a large clock error because it cannot distinguish
one second from another. The GPS lock provides that identity.

## Network startup and fallback

`NTP_FALLBACK_POOL` expands to up to four sources with `iburst`. These sources:

- initialize a system before GNSS lock;
- provide independent sanity references;
- take over during antenna or receiver failure;
- remain lower preference than healthy PPS.

The default is `pool.ntp.org`; regional or organizational pools can be selected
through the profile. Public sources are clients of PPSPi, not LAN access rules.

## Serving the LAN

Each comma-separated `NTP_ALLOW` CIDR becomes one Chrony `allow` directive.
Validation accepts only subnets inside:

- `10.0.0.0/8`;
- `172.16.0.0/12`;
- `192.168.0.0/16`;
- `fc00::/7`.

The default includes all four ranges, so common LANs such as
`192.168.1.0/24`, `10.20.0.0/16`, and `172.20.0.0/16` work without changing the
image. IPv6 ULA clients are also included.

The following address classes are deliberately not accepted as LAN policy:

- public and default routes such as `0.0.0.0/0` and `::/0`;
- IPv4 and IPv6 loopback;
- IPv4 APIPA and IPv6 link-local;
- `100.64.0.0/10` carrier-grade NAT space;
- multicast;
- documentation and benchmark networks.

These ranges are non-global for different reasons, but they are not
administrator-assigned private LAN space. Localhost can query Chrony without an
`allow` directive, and IPv6 link-local addresses also require interface scope,
making them a poor default client policy.

The four-range default is convenient but intentionally broad. Operators with
routing, VPNs, or several private network zones can optionally narrow
`NTP_ALLOW` to the client subnets that should receive time. Chrony opens UDP
port 123 because at least one `allow` directive exists; command monitoring
remains local.

Response rate limiting uses an interval of two seconds with a bounded burst of
16 to tolerate normal client startup while reducing accidental request floods.

## Clock correction and logging

`makestep 1.0 3` allows steps larger than one second only in the first three
valid updates after Chrony starts. Later corrections slew so normal operation
does not jump time.

PPSPi retains Chrony's drift and source history, uses the system timezone leap
database, and logs tracking, source statistics, and refclock samples. Logs are
valuable for offset calibration but must be monitored for storage use.

## RTC interaction

The RTC is deliberately not a Chrony refclock. A systemd service restores it
before Chrony, and a timer writes it only after `chronyc tracking` reports
`Leap status: Normal`. This avoids treating an inexpensive holdover RTC as
precision UTC or writing it continuously.

## Verification

```console
chronyd -p -f /etc/chrony/chrony.conf
chronyc tracking
chronyc sources -v
chronyc sourcestats -v
chronyc clients
```

Healthy settled source symbols normally include `#* PPS`, `#- GPS`, and one or
more reachable network sources. The exact network symbols vary as Chrony forms
its selection cluster.

## References

- [Chrony 4.6 configuration manual](https://chrony-project.org/doc/4.6/chrony.conf.html)
- [GPSD time service HOWTO](https://gpsd.io/gpsd-time-service-howto.html)
