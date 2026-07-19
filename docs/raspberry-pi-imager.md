# Raspberry Pi Imager

PPSPi images use Raspberry Pi OS Trixie's `cloudinit-rpi` first-boot format.
Use the current Raspberry Pi Imager 2.x release; these instructions and metadata
are validated against Imager 2.0.10. Imager 1.x cannot correctly customise a
current Trixie image.

## Flash a published release

Each GitHub Release includes:

- `ppspi-<version>-raspios-trixie-arm64.img.xz`;
- the matching `.sha256` file;
- `build-info.json`;
- `ppspi-<version>-raspios-trixie-arm64.rpi-imager-manifest`.

Verify the downloaded image before use:

```console
sha256sum --check ppspi-<version>-raspios-trixie-arm64.img.xz.sha256
```

Open the `.rpi-imager-manifest` file by double-clicking it. The manifest selects
the exact versioned image on the GitHub Release, identifies Raspberry Pi 4 Model
B as the supported target, and enables Imager's customisation pages through
`init_format: cloudinit-rpi`.

If the file association is unavailable, open Imager and choose **App Options** >
**Content Repository** > **Edit** > **Use custom file**, select the manifest,
and choose **Apply & restart**.

Configure at least:

1. a hostname;
2. an initial username and password or SSH public key;
3. locale, keyboard layout, and time zone;
4. SSH only when remote administration is required;
5. Wi-Fi only when the deployment will not use the preferred wired Ethernet.

> [!IMPORTANT]
> Use **Next** to continue from every customisation page. Imager's
> **Skip customisation** button discards **all** choices entered on every page;
> it does not skip only the current optional page. Before selecting **Write**,
> verify that the **Customisations to apply** summary lists the hostname, user,
> network, and SSH choices you expect. If that summary is absent, go back and
> enter the settings again. The image's unchanged default hostname is `ppspi`.

Password SSH is an accepted baseline for experimentation on a trusted private
LAN. Use a strong, unique password and do not forward or otherwise expose TCP
port 22 to the public Internet. Public-key authentication remains available as
optional hardening for operators comfortable managing keys.
The manifest contains no password, SSH key, Wi-Fi credential, or optional
hardware capability. Imager writes the operator's choices only to the selected
storage during flashing.

Do not select the image with **Use custom** when customisation is required.
Imager 2.x intentionally assigns `init_format: none` to an image selected that
way because it has no metadata describing the image's first-boot mechanism.

## Use an already-downloaded or test image

For an already-downloaded image or workflow test artifact, download the `.img.xz`
and its matching `build-info.json`. The test artifact does not contain a ready-made
`.rpi-imager-manifest`, because that local manifest must contain an absolute
`file://` URI for your computer. Generate it on the computer that will run Imager:

> [!IMPORTANT]
> Do **not** open `build-info.json` in Imager. It is input to the generator, not
> an Imager repository. Do not open the `.img.xz` directly either. After running
> the command below, open only the generated `.rpi-imager-manifest` file.

```console
python3 scripts/generate-imager-manifest.py \
  --image ppspi-<version>-raspios-trixie-arm64.img.xz \
  --build-info build-info.json
```

Run the script from the matching PPSPi release tag or candidate commit. It
validates the build metadata and XZ stream, computes compressed and extracted
sizes and SHA-256 values, and writes a `.rpi-imager-manifest` beside the image.
Open that generated manifest in Imager as described above.

Do not move the image after generating a local manifest. Regenerate the manifest
if its path changes. Release manifests use a versioned HTTPS URL and are not
affected by local file moves.

## Manual boot-partition fallback

This fallback is for local testing when Imager manifest loading is unavailable.
It is not preferable to Imager because hand-edited YAML is easier to get wrong.

1. Flash the image without customisation.
2. Reinsert the storage and mount its FAT boot partition.
3. Keep `meta-data` present.
4. Replace `user-data` and, when needed, `network-config` using spaces rather
   than tabs.
5. Unmount the storage cleanly before first boot.

A key-only headless `user-data` starting point is:

```yaml
#cloud-config
hostname: ppspi
manage_etc_hosts: true
locale: en_GB.UTF-8
timezone: Europe/Stockholm
keyboard:
  layout: gb
users:
  - name: operator
    groups: users,adm,dialout,audio,netdev,video,plugdev,cdrom,games,input,gpio,spi,i2c,render,sudo
    shell: /bin/bash
    lock_passwd: true
    ssh_authorized_keys:
      - ssh-ed25519 REPLACE_WITH_THE_OPERATOR_PUBLIC_KEY
    sudo: ALL=(ALL) NOPASSWD:ALL
enable_ssh: true
ssh_pwauth: false
```

Replace the username, locale, timezone, keyboard, and public key. Never put a
private key in `user-data`. For password login, use a strong salted password
hash in a `passwd` field, set `lock_passwd: false`, and enable `ssh_pwauth` only
when that risk is accepted. Do not store a plaintext password.

Wired DHCP can be made explicit in `network-config`:

```yaml
network:
  version: 2
  ethernets:
    eth0:
      dhcp4: true
      optional: false
```

For Wi-Fi, use Netplan's `wifis` configuration with `renderer:
NetworkManager`, the correct regulatory domain, SSID, and credential. Treat the
boot partition as sensitive because Wi-Fi credentials and first-boot data are
readable there until the card is booted and securely handled.

## Secure default without customisation

The image contains no usable default password, project SSH key, or wireless
credential, and SSH is disabled. This is intentional. A headless installation
must receive an operator account through Imager or valid manual cloud-init data;
do not weaken the image with a shared default credential.
