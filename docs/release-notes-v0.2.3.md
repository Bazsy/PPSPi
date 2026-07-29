# PPSPi v0.2.3 release notes

PPSPi v0.2.3 corrects the real-appliance application-update path discovered when
a healthy v0.2.0 appliance attempted v0.2.2. The signed update was verified and
installed transactionally, but the updater restarted GPSD and Chrony and ran its
full timing test before they had settled. Validation failed and the appliance
correctly rolled back to v0.2.0.

> [!IMPORTANT]
> Update a v0.2.0 appliance directly to v0.2.3. Do not retry v0.2.2: its
> immediate post-restart validation can reproduce the rollback. v0.2.3 includes
> a compatibility bridge in the newly installed deep-test executable, so it
> works even though the v0.2.0 updater process remains loaded during apply.

## Fixes

- when directly invoked by `ppstime-update`, deep validation retries for up to
  90 seconds while GPSD, PPS, Chrony, and local NTP settle;
- ordinary `ppstime-test` runs remain immediate and do not hide persistent
  failures;
- each retry is bounded by the remaining deadline and the complete validation
  still fits within v0.2.0's 180-second updater timeout;
- the dashboard sampler timer pulls in the dashboard service, making it start
  immediately when the old updater starts the newly installed timer;
- current updater reconciliation also explicitly enables and starts the
  dashboard service;
- persistent post-update failures name their exact essential checks;
- read-only `ppstime-update status` no longer opens the root-owned maintenance
  lock, so it works unprivileged after v0.2.3;
- apply, rollback, recovery, and maintenance remain exclusively locked and
  root-controlled.

## Update from v0.2.0

After all seven v0.2.3 assets are attached and independently verified:

```console
sudo ppstime-update check --version 0.2.3
sudo ppstime-update apply --version 0.2.3 --yes
ppstime-update status
ppstime-status
systemctl status ppstime-dashboard.service
systemctl status ppstime-dashboard-sample.timer
```

The existing v0.2.0 updater verifies the production minisign signature,
canonical manifest, exact version/compatibility series, archive hash, and every
managed file before replacement. Its transaction snapshot and rollback path are
unchanged; the observed v0.2.2 failure demonstrated successful automatic
restoration to v0.2.0.

After success, open `http://ppspi:8080` or either private Ethernet/Wi-Fi IPv4
address. The dashboard remains plain HTTP, read-only, sanitized, and limited to
loopback plus RFC 1918 peers by default.

## Scope and evidence

The appliance passed all 16 essential checks after the v0.2.2 rollback,
confirming that the failure was a settling race rather than persistent hardware
or timing degradation. Production v0.2.0-to-v0.2.3 apply, preservation,
direct-LAN boundary, rollback/reapply, and public-image smoke remain pending
until v0.2.3 assets are published and exercised. Evidence stays in
[issue #95](https://github.com/Bazsy/PPSPi/issues/95).

Supported hardware, Trixie arm64, compatibility series `0.2`, and pinned pi-gen
commit `ca8aeed0ae300c2a89f55ce9617d5f96a27e99e5` remain unchanged.
