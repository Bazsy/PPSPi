# PPSPi hardware test report: v0.2.4

Status: **v0.2.3 UPDATE PASSED; DASHBOARD FIX PHYSICALLY VERIFIED; v0.2.4 APPLY PENDING**

This corrective patch is driven by live evidence from the supported Raspberry
Pi 4 Model B Rev 1.5 and Uputronics GPS/RTC Expansion Board Rev 6.4 appliance.

## Successful v0.2.3 application update

- installed identity: v0.2.3 commit
  `e8eaf385a47890414d325d0e349491e4d60bee0f`;
- committed transaction: `20260729T094909Z-ef4be723-0.2.3`;
- install origin: image;
- last action: apply;
- automatic post-update timing validation passed, allowing the transaction to
  commit;
- dashboard service and sampler timer were enabled and active;
- sampler one-shots completed successfully every two minutes.

## Dashboard activation defect

The appliance had private addresses `10.0.10.110` and `10.0.10.173`. Generated
configuration selected `.110`, but the Python process still listened on its
older `.173` address. Local measurements showed:

| Probe | Result |
| --- | --- |
| Listener before correction | `10.0.10.173:8080` |
| Loopback HTTP | Connection refused |
| `10.0.10.110` HTTP | Connection refused |
| `10.0.10.173` HTTP | 200 OK |
| Dashboard service/timer | Enabled and active |
| Dashboard sampling | Repeated pass |

This isolates the defect to service activation after atomic config regeneration,
not to dashboard HTTP behavior, peer-CIDR authorization, sampling, or appliance
network interfaces.

## Physical correction verification

The active configuration was changed through `ppstime-config` to the documented
`0.0.0.0` wildcard and only `ppstime-dashboard.service` was restarted. The
listener then changed to `0.0.0.0:8080`; loopback, `.110`, and `.173` each
returned `HTTP/1.0 200 OK` with the expected PPSPi security headers and fixed
local HTML asset.

## v0.2.4 correction

v0.2.4 restarts the dashboard after update configuration regeneration, provides
an old-updater bridge in the newly installed deep-test executable, moves bind
preflight into systemd's stopped-service start path, and makes
`ppstime-config apply` reconcile regenerated values. The dashboard also exits
when atomic update/rollback replaces its loaded executable or configuration, so
systemd starts the installed or restored version. Summary-card percentages and
temperature are displayed with one decimal while stored sanitized values remain
unchanged.

## Feature disposition

| Feature | Result | Notes |
| --- | --- | --- |
| Signed v0.2.3 application apply | PASS | Transaction committed |
| v0.2.3 post-update timing validation | PASS | Required for commit |
| Dashboard service and sampling | PASS | Enabled, active, repeated samples |
| Stale bind reproduction | PASS | Config/listener mismatch measured |
| Wildcard listener correction | PASS | `0.0.0.0:8080` measured |
| Loopback and both private addresses | PASS | HTTP 200 on all three |
| v0.2.4 activation regressions | AUTOMATED PASS | Old/current updater and config apply |
| One-decimal card rendering | AUTOMATED PASS | Exact appliance values covered |
| Production v0.2.3-to-v0.2.4 apply | PENDING | Requires published signed assets |
| Rollback/reapply and routed denial | PENDING | Continue issue #95 evidence |
| Public-image shortened smoke | PENDING | Post-publication |

GPSD configuration, PPS, Chrony policy, RTC, boot overlays, hardware profiles,
and the supported target are unchanged from the v0.2.0 physical timing
baseline.

## Decision

Publish signed v0.2.4 assets after protected checks pass, independently verify
them, and then repeat dashboard acceptance without manual config or service
action. Remaining physical checks stay **PENDING** until recorded in
[issue #95](https://github.com/Bazsy/PPSPi/issues/95).
