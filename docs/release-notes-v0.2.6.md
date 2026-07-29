# PPSPi v0.2.6 release notes

PPSPi v0.2.6 restores direct same-series application-update compatibility for
appliances still running v0.2.3. The production-signed v0.2.5 application
manifest introduced `usr/lib/tmpfiles.d/ppstime.conf`, but the immutable v0.2.3
updater correctly rejected that new path before downloading or applying the
archive.

> [!IMPORTANT]
> The v0.2.5 `check` failure occurred before any application mutation or
> transaction. The appliance remains safely installed on v0.2.3. Do not retry
> v0.2.5; update directly to v0.2.6 after its public assets are verified.

## Fixes

- remove the out-of-boundary tmpfiles member from the signed application
  inventory consumed by legacy same-series updaters;
- add an equivalent root oneshot unit at the already permitted
  `etc/systemd/system/ppstime-dashboard-lock.service` path;
- create or validate the root-only maintenance lock without replacing its inode,
  preserving an updater's exclusive kernel `flock` during dashboard activation;
- make dashboard startup require lock preparation, including after a cold boot;
- reject unsafe lock ownership, file type, and symlink state while enforcing
  mode `0600`;
- test every current payload path against the exact immutable v0.2.3 boundary.

## Compatibility evidence

A representative 40-member v0.2.6 archive was generated from the corrected
source. The exact `ppstime_update.py` from v0.2.3 commit
`e8eaf385a47890414d325d0e349491e4d60bee0f` accepted its canonical manifest and
validated and extracted the complete archive. The candidate includes the lock
oneshot and excludes `usr/lib/tmpfiles.d/ppstime.conf`.

The v0.2.5 public release remains cryptographically valid: all seven assets,
production minisign signature, image hashes, metadata, and its exact 40-member
archive passed independent verification. Its application manifest is simply not
compatible with the deployed v0.2.3 updater's closed path boundary.

## Update

After all seven v0.2.6 assets are attached and independently verified:

```console
sudo ppstime-update check --version 0.2.6
sudo ppstime-update apply --version 0.2.6 --yes
ppstime-update status
sudo ppstime-test --json
systemctl status ppstime-dashboard.service
```

No manual application installation, configuration edit, or dashboard restart
should be required.

## Scope

The complete local suite passes 198 tests; one real-minisign fixture test is
skipped only when the local minisign binary is absent. Ruff, ShellCheck, shfmt,
yamllint, actionlint, markdownlint-cli2, and whitespace checks pass. Production
v0.2.3-to-v0.2.6 apply, rollback/reapply, routed out-of-CIDR denial, and
public-image smoke remain pending until the signed assets are published and
exercised. Evidence remains tracked in
[issue #95](https://github.com/Bazsy/PPSPi/issues/95).
