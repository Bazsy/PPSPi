# PPSPi v0.2.1 release notes

> [!CAUTION]
> The v0.2.1 image build failed before signing or uploading any assets. This tag
> has no deployable image or application bundle and is retained only as an
> immutable release record. Use v0.2.2 instead.

PPSPi v0.2.1 makes the sanitized read-only status dashboard available on a
trusted private LAN immediately after installation, update, or boot. It is a
same-series application update for existing v0.2.0 image installations and does
not require reflashing the SD card.

> [!IMPORTANT]
> The dashboard uses plain HTTP and has no authentication because it exposes only
> the closed sanitized status projection. The default admits loopback and all
> RFC 1918 clients. Narrow or disable it on shared or untrusted networks.
>
> Public assets, a real v0.2.0-to-v0.2.1 appliance update/rollback, direct-LAN
> boundary measurement, and shortened public-image smoke are tracked in
> [issue #95](https://github.com/Bazsy/PPSPi/issues/95). They are not represented
> as having passed before publication.

## Changes

- enable the dashboard HTTP service and two-minute sampler by default;
- bind to `0.0.0.0:8080`, covering all assigned Ethernet and Wi-Fi IPv4
  addresses without knowing DHCP addresses in advance;
- admit only `127.0.0.1/32`, `10.0.0.0/8`, `172.16.0.0/12`, and
  `192.168.0.0/16` by default through the existing socket-peer CIDR check;
- migrate only the exact v0.2.0 disabled/loopback dashboard tuple during
  configuration regeneration;
- preserve every operator-customized dashboard tuple;
- retain transactional configuration/unit snapshots, failed-apply restoration,
  boot recovery, and one-step local rollback.

## Update an existing v0.2.0 appliance

After the release workflow has attached and verified the signed application
assets:

```console
sudo ppstime-update check --version 0.2.1
sudo ppstime-update apply --version 0.2.1 --yes
```

The updater verifies the production minisign signature, exact version,
compatibility series, canonical manifest, archive hash, and every managed file
before activation. It does not replace Raspberry Pi OS, accounts, SSH, Wi-Fi,
cloud-init, or unrelated files.

After apply, open `http://ppspi:8080` or use either private IPv4 address. Check
`ppstime-update status`, `ppstime-status`, and both dashboard units. A local
rollback remains available with `sudo ppstime-update rollback --yes`.

Source installations require the existing explicit first-adoption flag described
in [verified application updates](application-updates.md).

## Security and operational boundaries

- exact GET/HEAD-only routes and a closed response schema remain unchanged;
- raw GPS position, addresses, hostnames, client/source listings, credentials,
  arbitrary command output, and administrative actions remain excluded;
- request/response bounds, rate/concurrency limits, security headers, disabled
  access logging, local static assets, and hardened systemd services remain;
- `0.0.0.0` is only the listen address: it does not bypass peer-CIDR admission;
- the page is plain HTTP and must not be exposed to the internet;
- enabled two-minute sampling creates approximately 720 bounded SQLite
  transactions per day; use endurance-rated storage or disable history when it
  is unnecessary.

## Hardware and compatibility

- supported target remains Raspberry Pi 4 Model B with the documented
  Uputronics V6.0+ GPS/RTC profile;
- Raspberry Pi OS remains Trixie arm64;
- pi-gen remains pinned at
  `ca8aeed0ae300c2a89f55ce9617d5f96a27e99e5`;
- compatibility series remains `0.2`;
- timing, GPSD, PPS, Chrony, RTC, boot overlay, and hardware-profile behavior are
  unchanged from v0.2.0.

See the [v0.2.1 hardware report](hardware-test-report-v0.2.1.md) and
[release readiness](release-readiness-v0.2.1.md).

## Release assets

The protected release workflow rebuilds and attaches exactly seven assets:

- compressed Trixie arm64 image;
- image SHA-256;
- `build-info.json`;
- Raspberry Pi Imager manifest;
- application archive;
- canonical application manifest;
- minisign signature for the manifest.

Wait for the release workflow to finish and verify all seven attachments before
running the appliance update.
