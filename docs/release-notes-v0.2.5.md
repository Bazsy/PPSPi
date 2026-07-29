# PPSPi v0.2.5 release notes

PPSPi v0.2.5 fixes the immediate dashboard-restart failure discovered during a
production-signed v0.2.3-to-v0.2.4 application update. The v0.2.4 transaction
failed health validation and automatically restored v0.2.3 without disturbing
the healthy timing baseline.

> [!IMPORTANT]
> v0.2.5 does not change the PPS, GPSD, Chrony, RTC, or hardware profile policy.
> It makes dashboard socket replacement compatible with both forward update and
> automatic rollback.

## Fixes

- use `SO_REUSEADDR` consistently in dashboard bind preflight and the real HTTP
  server;
- allow an older non-reuse listener's TCP state to settle for a bounded period
  during the first corrected restart;
- create a root-only kernel maintenance lock and pass its open descriptor to the
  sandboxed `DynamicUser` dashboard through systemd;
- bind the candidate dashboard while withholding HTTP acceptance until the
  updater releases its exclusive lock;
- make a candidate exit on update or rollback file replacement before serving,
  preventing candidate-created `TIME_WAIT` sockets from blocking restoration of
  an older non-reuse dashboard;
- verify that only an exact direct `ppstime-update` parent can prepare the lock
  handoff, without relaxing the lock file's `0600` permissions.

## Appliance evidence

All seven public v0.2.4 assets passed independent checksum, metadata, image,
archive-inventory, and production-minisign verification. The supported Raspberry
Pi 4/Uputronics Rev 6.4 appliance then attempted signed transaction
`20260729T133031Z-582d1b16-0.2.4` from v0.2.3 commit
`e8eaf385a47890414d325d0e349491e4d60bee0f` to v0.2.4 commit
`d5267cc009c6501fbf6bf65e0f452ebff4cb56f2`.

The new dashboard repeatedly failed with `EADDRINUSE` after the old server had
served HTTP. Chrony selected a network source after six seconds and PPS after
nine seconds, showing that timing was settling normally rather than exhausting
the validation window. The update rolled back automatically, and all 16
essential `ppstime-test` checks passed afterward.

Local reproduction proved the socket boundary: `SO_REUSEADDR` on only one side
cannot bridge an old non-reuse listener to a new reuse listener, or safely
restore an old non-reuse listener after candidate traffic. The maintenance-lock
design closes both forward-update and rollback cases without a detached helper,
PID inference, `/proc` access, or world-readable lock state.

## Update

After all seven v0.2.5 assets are attached and independently verified:

```console
sudo ppstime-update check --version 0.2.5
sudo ppstime-update apply --version 0.2.5 --yes
ppstime-update status
sudo ppstime-test --json
systemctl status ppstime-dashboard.service
```

Then open `http://ppspi:8080` or either current private IPv4 address. No manual
configuration edit or service restart should be required.

## Scope

The complete local suite passes 194 tests. Ruff, ShellCheck, shfmt, yamllint,
actionlint, markdownlint-cli2, and whitespace checks also pass. Production
v0.2.3-to-v0.2.5 apply, local rollback/reapply, routed out-of-CIDR denial, and
public-image smoke remain pending until the signed assets are published and
exercised. Evidence remains tracked in
[issue #95](https://github.com/Bazsy/PPSPi/issues/95).
