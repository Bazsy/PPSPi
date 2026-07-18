# PPSPi pi-gen integration

PPSPi uses the official [RPi-Distro/pi-gen](https://github.com/RPi-Distro/pi-gen)
project without vendoring or patching it. `PI_GEN_COMMIT` pins the
`bookworm-arm64` revision used by local and GitHub Actions builds.

`scripts/build-image.sh` performs the integration:

1. checks out the exact pinned pi-gen commit;
2. copies `stage-pps-pi` into that checkout;
3. creates a source payload from the current PPSPi checkout;
4. generates `build-info.json` once for both the image and release artifacts;
5. invokes pi-gen's supported Docker build entry point;
6. passes the image to `scripts/package-release.sh`.

Stage 2 is built as PPSPi's Raspberry Pi OS Lite base, but its intermediate
image export is suppressed with `SKIP_IMAGES`. Only `stage-pps-pi` exports an
image. Packaging additionally selects the exact configured `IMG_NAME`, so stale
or unexpected pi-gen images cannot be attached to a release.

The custom stage installs its package list through pi-gen and then runs the same
`scripts/install.sh` used for a live Raspberry Pi OS installation. This prevents
the image path and installer path from becoming unrelated implementations.

The image intentionally leaves `FIRST_USER_PASS` unset, keeps SSH disabled, and
retains pi-gen's first-boot user rename. Raspberry Pi Imager customisation is the
supported way to create the initial user and optionally install an SSH public key.
