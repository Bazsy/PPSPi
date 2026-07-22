# Hardware support levels

PPSPi accepts useful hardware contributions before they reach release-grade
validation. Every setup is labeled honestly so an experimental result is never
mistaken for a release-tested promise.

## Level summary

| Level | Meaning | Minimum evidence |
| --- | --- | --- |
| Planned | An issue identifies exact hardware worth investigating. | Product/SKU and a contributor or evidence source are still needed. |
| Experimental | One named setup worked for one contributor. Expect rough edges. | Exact revisions, authoritative or measured mapping, automated tests, and the short smoke checklist below. |
| Community-validated | The setup has repeatable operational evidence beyond first success. | Experimental evidence plus fallback/recovery, reboot persistence, diagnostics review, and a short soak. |
| Release-tested | A release may make a tested compatibility claim for this exact setup. | Full applicable acceptance plan, exact release artifact, security review, and at least 24 hours of stable observation. |

Only release-tested combinations should be described without a maturity warning.
Promotion is evidence-based and does not happen because two products look
similar.

Before the first Experimental or Community-validated profile is merged, it must
be explicitly selected rather than used as the installer default, and its
support level must be visible in profile documentation and `ppstime-status`.
Only a Release-tested profile may become the default release profile.

## Experimental contribution checklist

A first hardware profile does **not** need a 24-hour observation, a denied-client
network, exhaustive screenshots, or polished long-form documentation.

Record only what another contributor needs to reproduce the result:

1. exact Raspberry Pi model/revision and exact GNSS board/module product and PCB
   revision, without serial numbers;
2. authoritative documentation or direct measurement for UART, baud/framing,
   PPS pin, voltage, edge/polarity, rate, and fix gating;
3. RTC chip/address/backup behavior when an RTC exists, or an explicit `N/A`
   when it does not;
4. Raspberry Pi OS/PPSPi version or commit and the selected profile;
5. successful boot/first-user setup;
6. recognized GPSD data;
7. at least ten consecutive kernel PPS assertions;
8. Chrony showing GPS labels and selected PPS at Stratum 1;
9. reboot persistence, no failed units, and a passing applicable deep test;
10. automated parser/rendering/model/installer tests and compact setup notes.

`N/A` is valid only when the exact product does not have that feature. It is not
a way to hide a failed required function. A GPS/PPS board without an RTC can be
experimental if its profile declares RTC absent and diagnostics/tests behave
accordingly.

## Compact experimental report

Post this in the relevant issue or pull request. Plain text is sufficient.

```text
Support level requested: Experimental
PPSPi version/commit:
Raspberry Pi model/revision:
GNSS product and PCB revision:
Receiver/module and firmware:
Connection: HAT / UART wiring / USB
Mapping evidence: datasheet/schematic URL or direct measurement method
UART device and reported baud:
UART framing and logic voltage:
PPS physical pin / BCM GPIO / edge:
PPS logic voltage / rate / fix gating:
RTC chip/address, or N/A with reason and evidence:
OS and kernel:
Antenna and approximate sky conditions:

Imager or installer completed: PASS / FAIL
GPSD recognized data: PASS / FAIL
Ten PPS assertions advanced: PASS / FAIL
Chrony selected PPS, Stratum 1: PASS / FAIL
Reboot persistence: PASS / FAIL
ppstime-test applicable checks: PASS / FAIL
Failed units / restart count:

Known limitations:
Evidence or sanitized diagnostics link:
```

Do not post credentials, private/public addresses, coordinates, serial numbers,
MAC addresses, host fingerprints, or unsanitized bundles.

## Community-validated promotion

Promotion normally needs:

- the experimental checklist on a clean install or image;
- antenna-loss or receiver-loss fallback without restart loops;
- automatic GPS/PPS recovery;
- reboot persistence;
- inspected sanitized diagnostics;
- at least a two-hour normal-use soak with no unexplained transition;
- ideally a second report from another contributor or hardware sample.

The maintainer may tailor non-applicable checks to the product. The report must
state every omission and why it does not weaken the claimed functions.

## Release-tested promotion

Release-tested status uses the complete applicable
[hardware acceptance plan](hardware-test-plan.md), an exact release artifact,
and at least a 24-hour observation. Waivers remain visible and are never counted
as measured passes.

A code or timing-configuration change after acceptance may require a new
candidate and observation. Documentation-only changes do not retroactively
invalidate hardware evidence.

## Regression and demotion

A support level applies to named hardware and software versions. A regression,
unverified product revision, OS/kernel change, or stale contributor report may
move a setup back to experimental until retested. Demotion is an honest status
update, not a rejection of the contributor's work.

## Review principles

- Prefer a small reproducible report over a large polished document.
- Ask for evidence only when it supports a concrete compatibility or safety
  claim.
- Help contributors sanitize logs instead of rejecting imperfect formatting.
- Never guess GPIO, voltage, RTC, baud, or polarity to make a profile appear
  complete.
- Keep timing-source changes conservative; a one-second mistake is worse than an
  unsupported profile.
