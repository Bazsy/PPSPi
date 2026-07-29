# PPSPi v0.2.2 release notes

PPSPi v0.2.2 makes the sanitized read-only status dashboard available on a
trusted private LAN immediately after installation, signed application update,
or boot. It supersedes assetless v0.2.1 and is the deployable same-series update
for v0.2.0 appliances; no SD-card reflash is required.

> [!IMPORTANT]
> The v0.2.1 release workflow failed before signing or upload because its image
> installer combined `systemctl enable --now` inside pi-gen's systemd-less
> chroot. v0.2.2 separates enablement from runtime start: pi-gen enables the units
> for first boot, while a running appliance also starts them immediately.
>
> The dashboard uses plain HTTP without authentication and admits loopback plus
> all RFC 1918 clients by default. Narrow or disable it on shared or untrusted
> networks. Live update/rollback and direct-LAN evidence remain tracked in
> [issue #95](https://github.com/Bazsy/PPSPi/issues/95).

## Changes

- enable the dashboard HTTP service and two-minute sampler by default;
- bind to `0.0.0.0:8080`, covering assigned Ethernet and Wi-Fi IPv4 addresses;
- admit only `127.0.0.1/32`, `10.0.0.0/8`, `172.16.0.0/12`, and
  `192.168.0.0/16` by default through socket-peer CIDR checks;
- migrate only the exact untouched v0.2.0 dashboard tuple while preserving
  customized dashboard settings and transactional rollback;
- enable and start dashboard units with separate `systemctl` operations so the
  installer works on both a running appliance and pi-gen's chroot.

## Update an existing v0.2.0 appliance

After all seven v0.2.2 assets are attached and independently verified:

```console
sudo ppstime-update check --version 0.2.2
sudo ppstime-update apply --version 0.2.2 --yes
```

The updater verifies the production minisign signature, exact version,
compatibility series, canonical manifest, archive hash, and every managed file.
It preserves Raspberry Pi OS, accounts, SSH, Wi-Fi, cloud-init, timing settings,
and unrelated files.

Then inspect `ppstime-update status`, `ppstime-status`, and the dashboard service
and timer. Open `http://ppspi:8080` or either private IPv4 address. One-step local
rollback remains available with `sudo ppstime-update rollback --yes`.

Source installations require the explicit first-adoption flow in
[verified application updates](application-updates.md).

## Security and hardware boundaries

- exact GET/HEAD-only routes, sanitized closed schema, bounds, rate/concurrency
  limits, security headers, disabled access logging, local assets, and hardened
  services remain unchanged;
- `0.0.0.0` controls listening only and does not bypass peer-CIDR admission;
- no raw GPS position, client/source listings, credentials, command execution,
  administration, or external browser requests are exposed;
- two-minute sampling creates approximately 720 bounded SQLite transactions per
  day;
- Raspberry Pi 4, the Uputronics V6.0+ profile, Trixie arm64, compatibility
  series `0.2`, and pi-gen commit
  `ca8aeed0ae300c2a89f55ce9617d5f96a27e99e5` remain unchanged;
- GPSD, PPS, Chrony, RTC, boot overlay, and hardware-profile behavior are
  unchanged from the physically accepted v0.2.0 baseline.

See the [v0.2.2 hardware report](hardware-test-report-v0.2.2.md) and
[release readiness](release-readiness-v0.2.2.md).

## Release assets

The protected release workflow rebuilds and attaches exactly seven assets: the
compressed image, image checksum, build information, Imager manifest,
application archive, canonical application manifest, and minisign signature.
Wait for successful workflow completion and independent verification before
updating the appliance.
