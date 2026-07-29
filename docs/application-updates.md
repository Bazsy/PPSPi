# Verified application updates and rollback

PPSPi can replace only its application-owned runtime, static profiles, systemd
units/drop-ins, udev rule, and modules-load rule from a signed release bundle.
Application updates are disabled by default and preserve operator configuration,
accounts, home directories, networking, SSH, cloud-init, package sources, and
unrelated operating-system files. A release may migrate an exact recognized old
default tuple in `/etc/ppstime/ppstime.env`; customized values are preserved and
the complete active configuration participates in transactional rollback.

This feature is available on the `0.2.x` development line. A v0 compatibility
series is `major.minor` (`0.2`); from v1 onward it is the major version. Network
updates cannot cross that boundary and cannot downgrade. Reflash or follow an
explicit migration procedure for a breaking release.

## Trust and release assets

Each published release contains three application assets:

- `ppspi-<version>-application.tar.gz`;
- its canonical `...manifest.json`;
- the manifest's `...manifest.json.minisig` signature.

The signed, closed-schema manifest binds the exact version, compatibility series,
compressed archive filename/size/SHA-256, and every payload path/mode/size/SHA-256.
The updater invokes `minisign` with an explicitly configured public key before it
downloads or parses the archive. The archive parser accepts bounded regular files
only, rejects links, devices, duplicates, traversal, PAX extensions, extra
members, and paths outside the PPSPi-owned allow-list, and never uses
`extractall`.

Versions use strict SemVer 2.0.0 throughout configuration, packaging, and runtime.
Numeric prerelease identifiers cannot have leading zeroes; build metadata is
accepted and remains part of the exact requested identity.

The repository pins the production public key at
`/usr/share/ppstime/application-update.pub`. The matching private key is stored
only in the protected GitHub release environment and an offline maintainer
recovery copy. Operators may pass a different reviewed public key with
`--public-key PATH` only for private testing. Never copy a secret signing key
onto an appliance.

## Explicit operation

Check an exact release without changing the appliance:

```console
sudo ppstime-update check --version 0.2.1 --public-key /secure/path/ppspi-update.pub
```

Apply that exact verified release:

```console
sudo ppstime-update apply --version 0.2.1 --yes
```

This updates the installed PPSPi application, static assets, profiles, and
systemd units in place. It does not reflash the SD card or replace Raspberry Pi
OS. A v0.2.0 image installation already contains the production public key and
can apply a published, signed same-series release such as v0.2.1 directly.

There is no branch, `latest`, tag-discovery, or implicit target resolution.
Local/offline verification accepts the matching `--archive`, `--manifest`, and
`--signature` together. A source installation is distinguished from an image
installation in `/var/lib/ppstime/install-origin.json`; its first apply also
requires `--adopt-source-install` because replacing a working tree installation
changes ownership expectations.

Inspect non-secret state:

```console
ppstime-update status
```

## Transaction and rollback

Before service changes, the updater verifies compatibility, available space,
manifest/archive identity, member hashes, and the staged candidate systemd
units/drop-ins through a candidate unit-path overlay. It then creates a
per-file snapshot below `/var/lib/ppstime/application-updates/<transaction>/`,
records `PREPARED` and `APPLYING` state atomically, replaces each allow-listed
file through a same-directory temporary file, reloads/restarts relevant services,
and runs the deep PPSPi test. Any failure restores the snapshot immediately.
A snapshot's files and directories are synced before `PREPARED`; live file
renames, deletions, JSON state changes, and restores sync their parent directory.
Recovery validates every required snapshot size/hash before changing any live
path and fails closed if any snapshot is missing or malformed.

After a successful apply,
`/var/lib/ppstime/application-installation.json` records the repository,
version, Git commit, manifest SHA-256, archive SHA-256, minisign key ID, and exact
managed-path inventory. A later release removes only paths in that prior signed
inventory which are absent from the new manifest; unknown administrator files
are never inferred or deleted. Updater-owned unit enablement is reconciled and
restored by rollback. A same-version request must match the complete persisted
identity and fails closed when legacy metadata cannot establish that identity.
A successful transaction remains local for one-step rollback:

```console
sudo ppstime-update rollback --yes
```

Rollback never contacts the network and restores the previous files and version
from the newest committed local transaction. Network downgrades are always
rejected.

## Interrupted-update recovery

`ppstime-update-recovery.service` runs before timing services at boot. If it finds
a transaction left in `PREPARED` or `APPLYING`, it restores that transaction's
snapshot and records `RECOVERED`. Normal boots with no interrupted transaction
are a no-op. To recover manually from rescue mode after mounting the root
filesystem normally:

```console
sudo ppstime-update recover
sudo systemctl daemon-reload
sudo systemctl restart gpsd.service chrony.service
sudo ppstime-test
```

Do not delete `/var/lib/ppstime/application-updates` until recovery and rollback
are no longer needed.

## Scheduled same-series maintenance

Automatic application updates are opt-in and require an exact target:

```ini
APP_UPDATES_ENABLED=false
APP_UPDATE_VERSION=
```

To schedule one reviewed same-series release in the existing weekly maintenance
window:

```console
sudo ppstime-config set APP_UPDATE_VERSION 0.2.1
sudo ppstime-config set APP_UPDATES_ENABLED true
sudo ppstime-config apply
```

The maintenance service runs the same verified `apply --version` path after OS
package audit. Empty targets, invalid versions, verification failures,
downgrades, and compatibility changes fail the maintenance job. Change or clear
the target deliberately after deployment; PPSPi never discovers a newer release.

## Diagnostics and retained boundaries

`ppstime-diagnostics` includes sanitized update origin/state, recovery-unit
status, and PPSPi update journals. It does not include signatures, signing keys,
operator credentials, network configuration, SSH data, or transaction file
contents. Review every support archive before sharing.
