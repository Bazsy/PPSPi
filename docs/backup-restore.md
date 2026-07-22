# Configuration backup and disaster recovery

`ppstime-backup` creates a small, portable backup of PPSPi-owned configuration.
It is intended for SD-card replacement, migration to a compatible Pi, and
rollback before changing PPSPi.

This command is available in the current `0.2.0-dev` branch and is not included
in the published v0.1.0 image.

## What is included

A backup contains exactly two files:

- `manifest.json` — format version, creation time, PPSPi/build identity, source
  hardware model, profile, model policy, and configuration SHA-256;
- `ppstime.env` — the complete validated PPSPi source configuration.

The archive does **not** copy generated Chrony/GPSD files or boot fragments.
Restore regenerates them with the currently installed PPSPi version, avoiding
stale generated state.

The default archive also excludes:

- usernames and password hashes;
- SSH host/user keys and `authorized_keys`;
- Wi-Fi credentials and NetworkManager profiles;
- cloud-init user data;
- tokens, API keys, and browser/dashboard credentials;
- journals, diagnostics, client/source addresses, and unrelated OS files.

The PPSPi configuration is designed to be non-secret, but it can contain a
hostname, private CIDRs, fallback pool, and hardware paths. Backups are therefore
mode `0600`; inspect them locally before sharing.

## Create a backup

On the appliance:

```console
ppstime-backup export --output "$HOME/ppstime-backup.tar.gz"
```

The command validates every configuration value, serializes it canonically,
binds it to the manifest with SHA-256, refuses to overwrite an existing file,
and prints the archive identity. Keep a copy away from the Pi and its SD card.

Inspect without extracting:

```console
ppstime-backup inspect "$HOME/ppstime-backup.tar.gz"
ppstime-backup inspect "$HOME/ppstime-backup.tar.gz" --json
```

Inspection requires exactly the two expected regular files, enforces size
limits, validates the closed manifest schema, verifies SHA-256, parses the strict
configuration, and rejects non-canonical or modified content.

A SHA-256 inside the same archive detects corruption and accidental mismatch; it
does not turn a locally stored archive into a cryptographically signed release.
Protect the archive from unauthorized replacement.

## Restore safely

Copy the archive to the target Pi. Install or flash a PPSPi version that contains
and recognizes the archived profile, then run a dry-run:

```console
sudo ppstime-backup restore /path/to/ppstime-backup.tar.gz --dry-run
```

Dry-run verifies:

- archive structure and SHA-256;
- every configuration key/value;
- that the archived profile exists in the installed PPSPi version;
- that loading through current defaults/profile does not change the archive;
- that the target Raspberry Pi model matches the archived profile policy;
- every file path the configuration engine would write.

No file is changed during dry-run. Review the source/target hardware identity and
planned paths. Then restore explicitly:

```console
sudo ppstime-backup restore /path/to/ppstime-backup.tar.gz --yes
sudo reboot
```

Before writing, PPSPi creates a mode-`0600` backup of the target's current
configuration under `/var/backups/ppstime/`. It snapshots every managed target
file in memory, regenerates configuration through `configure-profile.py`, and
verifies the applied source configuration. A configure or verification failure
restores the previous managed files immediately.

Restore does not restart timing services part-way through. Reboot after success
so boot overlays and all services start together from the restored configuration.

## Roll back a restore

The successful restore prints a path such as:

```text
/var/backups/ppstime/ppstime-pre-restore-20260722T120000Z.tar.gz
```

Inspect and restore it like any other backup:

```console
sudo ppstime-backup inspect \
  /var/backups/ppstime/ppstime-pre-restore-20260722T120000Z.tar.gz
sudo ppstime-backup restore \
  /var/backups/ppstime/ppstime-pre-restore-20260722T120000Z.tar.gz \
  --dry-run
sudo ppstime-backup restore \
  /var/backups/ppstime/ppstime-pre-restore-20260722T120000Z.tar.gz \
  --yes
sudo reboot
```

Each actual restore creates another pre-restore archive. Existing archives are
never overwritten, including multiple operations within the same second.

## Replace a failed SD card

1. Flash the current compatible PPSPi image using the one-file
   [quick start](quick-start.md).
2. Recreate the operator account, SSH choice, locale, time zone, and any Wi-Fi
   settings in Raspberry Pi Imager. These OS/account settings are intentionally
   not part of the PPSPi backup.
3. Boot with wired Ethernet and copy the backup to the new Pi.
4. Run `ppstime-backup inspect`.
5. Run `sudo ppstime-backup restore ... --dry-run`.
6. If the profile/model check and planned paths are correct, restore with
   `--yes` and reboot.
7. Run `ppstime-status` and `sudo ppstime-test` after convergence.

Restoring to a different Pi revision is allowed only when the archived profile's
model policy accepts that exact model string. Restoring an archive onto Pi 5, an
unknown carrier, or a profile unavailable in the installed PPSPi version fails
before writing.

## Sensitive OS backup is separate

PPSPi does not attempt to package accounts, SSH, Wi-Fi, or arbitrary operating
system state. Those are deployment-specific secrets and can make a portable
archive dangerous. Use Raspberry Pi Imager to recreate first-boot identity and
network choices, or use an operator-managed encrypted system backup outside
PPSPi. Never commit or attach such a backup to a public issue.

## Before updates

Create and copy a PPSPi backup before:

- changing profiles or site configuration;
- upgrading PPSPi between releases;
- enabling unattended maintenance;
- replacing hardware or storage.

This archive protects PPSPi configuration. It is not a full disk image and does
not replace tested application rollback or OS package rollback.
