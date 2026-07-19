# Security policy

## Supported versions

PPSPi has not published a hardware-accepted stable release. Security fixes are
currently applied to the default branch and the latest pre-release line only.

## Reporting a vulnerability

Please use GitHub's private vulnerability reporting for this repository:

1. open the repository **Security** tab;
2. choose **Advisories**;
3. choose **Report a vulnerability**.

If private reporting is unavailable, open a minimal issue asking the maintainer
for a private contact channel. Do not publish exploit details, credentials,
private network data, support bundles, or device identifiers in a public issue.

Include the affected commit or release, impact, reproduction conditions, and a
suggested mitigation if known. You should receive an acknowledgement within
seven days. Disclosure timing will be coordinated after a fix is available.

## Security boundaries

PPSPi serves unauthenticated NTP by design, but only to configured private
networks. It does not expose an administration API. SSH configuration, user
creation, operating-system updates, physical access, and LAN firewall policy
remain the operator's responsibility.

Password-authenticated SSH is supported for an appliance on a trusted private
LAN when the password is strong and unique. PPSPi does not install a firewall
rule that restricts SSH to `NTP_ALLOW`; do not publish, port-forward, or
otherwise expose TCP port 22 to the Internet. Public-key authentication is
recommended optional hardening, not a requirement.

Time from civilian GNSS and unauthenticated public NTP can be jammed, spoofed,
or delayed. PPSPi source selection and fallback improve resilience but do not
provide cryptographic proof of UTC. Deploy independent time sources and
monitoring where incorrect time has safety, financial, or security impact.
