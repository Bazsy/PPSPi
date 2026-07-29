# PPSPi v0.2.4 release notes

PPSPi v0.2.4 fixes the dashboard activation defect discovered after a successful
production-signed v0.2.3 application update. The update committed and its timing
validation passed, but the already-running dashboard process retained an older
literal interface address after configuration regeneration.

> [!IMPORTANT]
> v0.2.4 does not change the PPS, GPSD, Chrony, RTC, or hardware profile policy.
> It makes dashboard configuration activation transactional and restart-safe.

## Fixes

- application update activation restarts an already-running dashboard after
  regenerating `/etc/ppstime/ppstime.env`;
- the newly installed deep-test executable provides the activation bridge when
  the updater process performing the transaction is from an older release;
- systemd runs dashboard bind preflight after stopping the previous service
  process, so switching between a literal private address and `0.0.0.0` does not
  collide with the old listener;
- `ppstime-config apply` re-reads regenerated settings before unit
  reconciliation, then enables both dashboard units, restarts the HTTP service,
  and starts the sampler timer;
- root/boot free-space and CPU-temperature summary values display with one
  decimal place while stored/API precision remains unchanged.

## Appliance evidence

The supported Raspberry Pi 4/Uputronics Rev 6.4 appliance committed signed
transaction `20260729T094909Z-ef4be723-0.2.3` at release commit
`e8eaf385a47890414d325d0e349491e4d60bee0f`. Both dashboard units were enabled
and active and sampling succeeded. However:

- generated bind: `10.0.10.110:8080`;
- active process listener: `10.0.10.173:8080`;
- HTTP on `10.0.10.173`: `200 OK`;
- HTTP on `10.0.10.110` and loopback: connection refused.

After setting the validated bind to `0.0.0.0` and restarting only the dashboard
service, `ss` reported `0.0.0.0:8080` and loopback, `10.0.10.110`, and
`10.0.10.173` each returned `HTTP/1.0 200 OK`. This restores the documented
zero-touch Ethernet/Wi-Fi behavior without restarting timing services.

## Update

After all seven v0.2.4 assets are attached and independently verified:

```console
sudo ppstime-update check --version 0.2.4
sudo ppstime-update apply --version 0.2.4 --yes
ppstime-update status
systemctl status ppstime-dashboard.service
```

Then open `http://ppspi:8080` or either current private IPv4 address. A literal
operator-selected `DASHBOARD_BIND` remains preserved; use `0.0.0.0` to listen on
all IPv4 interfaces.

## Scope

The complete local suite passes 188 tests. Ruff, ShellCheck, shfmt, yamllint,
actionlint, and markdownlint-cli2 also pass. Production v0.2.3-to-v0.2.4 apply,
local rollback/reapply, routed out-of-CIDR denial, and public-image smoke remain
pending until the signed assets are published and exercised. Evidence remains
tracked in [issue #95](https://github.com/Bazsy/PPSPi/issues/95).
