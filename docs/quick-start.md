# Five-minute quick start

This is the shortest supported path for a first PPSPi appliance. You do not need
Git, Docker, YAML, or GPIO knowledge.

The guided setup takes about five minutes of user input. Downloading, writing,
first boot, and satellite acquisition take additional time.

## What you need

Release-tested v0.1.0 requires:

- Raspberry Pi 4 Model B Rev 1.5, or another Pi 4 Model B revision accepted by
  the current model policy;
- Uputronics GPS/RTC Expansion Board Rev 6.4; PPSPi uses the V6.0+ profile, but
  Rev 6.4 is the release-tested PCB revision;
- active GNSS antenna placed outdoors with a broad sky view;
- microSD card and Raspberry Pi 4 power supply;
- wired Ethernet;
- another computer with Raspberry Pi Imager 2.x.

| Status | Hardware | What it means |
| --- | --- | --- |
| Release-tested | Raspberry Pi 4 Model B Rev 1.5 with Uputronics Rev 6.4 | The exact v0.1.0 hardware acceptance target. |
| Planned | Pi 3 B/B+, CM4, Pi 5, and GNSS products listed in the roadmap | Not supported yet; each requires an exact contributor test report. |
| Experimental | None currently | Used only after one exact setup passes the experimental checklist. |

Other Pi and GNSS combinations are planned contribution work. None has earned
Experimental status yet, and they are not drop-in substitutes.

## 1. Download one file

Open the [latest PPSPi release](https://github.com/Bazsy/PPSPi/releases/latest),
expand **Assets**, and download only:

`ppspi-<version>-raspios-trixie-arm64.rpi-imager-manifest`

That small manifest tells Raspberry Pi Imager where to download the exact image
and includes its expected size and SHA-256. Beginners do not need to download
the image, checksum, or `build-info.json` separately.

The `/latest` link is only a discovery page. The downloaded manifest points to
an immutable, versioned GitHub Release asset—not a mutable "latest image" URL.

## 2. Open the manifest in Imager

Use Raspberry Pi Imager 2.x. Double-click the downloaded manifest.

If it does not open automatically:

1. open Raspberry Pi Imager;
2. choose **App Options**;
3. open **Content Repository** and choose **Edit**;
4. choose **Use custom file**;
5. select the `.rpi-imager-manifest`;
6. choose **Apply & restart**.

Select the versioned **PPSPi** image shown by Imager. Do not use Imager's generic
**Use custom** image path; that path does not know PPSPi uses `cloudinit-rpi`.

## 3. Choose first-boot settings

Use **Next** on every customisation page and set:

- a hostname, such as `ppspi`;
- your own username and a strong unique password, or an SSH public key;
- locale, keyboard layout, and time zone;
- SSH only if you want remote administration;
- no Wi-Fi for the recommended wired setup.

Before writing, check that **Customisations to apply** lists your hostname and
user. **Skip customisation** discards all settings; it does not skip only the
current page.

Choose the microSD card and write the image. Imager downloads and checks the
release image using the manifest metadata.

## 4. Assemble and boot

1. power off the Pi;
2. fit the Uputronics HAT carefully on the 40-pin header;
3. attach the active antenna and put it outdoors with a broad sky view;
4. connect Ethernet;
5. insert the microSD card;
6. connect power.

Do not treat an indoor window as open sky. Modern coated glass, buildings, and
foliage can show visible satellites but still lose a reliable 3D fix and PPS.

First boot can take several minutes while cloud-init creates the account and
applies settings. A cold GNSS fix can take several more minutes.

## 5. Check the appliance

Log in locally or over SSH, then run:

```console
cloud-init status --wait
ppstime-status
sudo ppstime-test
```

A settled healthy appliance should show:

- cloud-init `status: done`;
- GPSD `ACTIVE` and GPS fix `3D`;
- several satellites used, with the exact count varying by sky view;
- PPS pulses `ACTIVE`;
- RTC `OK`;
- Chrony `SYNCHRONIZED`;
- selected source `PPS`;
- Stratum `1`;
- `Essential checks: PASS`.

Immediately after boot, network time or `NO FIX` can be normal. Wait outdoors for
several minutes and retry. If PPS never becomes selected, start with
[troubleshooting](troubleshooting.md).

## Use PPSPi from another device

Clients on the same private LAN can use `ppspi` as their NTP server. If that name
does not resolve, use the private address assigned by your router. Do not expose
UDP 123 or SSH directly to the public Internet.

## What are the other release files?

The release keeps four separate assets for auditability:

- `.rpi-imager-manifest` — the one beginner download;
- `.img.xz` — the compressed image for offline/manual flashing;
- `.img.xz.sha256` — independent command-line verification;
- `build-info.json` — exact source, OS, architecture, and profile identity.

Advanced and offline workflows are documented in the
[Raspberry Pi Imager guide](raspberry-pi-imager.md).

## Small glossary

| Term | Plain-language meaning |
| --- | --- |
| GNSS/GPS | Satellites and the receiver that provide UTC date/time. |
| GPSD | Reads the receiver and supplies time data to other programs. |
| PPS | One electrical pulse per second, used for the precise second boundary. |
| RTC | A small battery/supercapacitor-backed clock used for approximate boot time. |
| Chrony | Selects time sources and disciplines the Pi's system clock. |
| NTP | Protocol that lets devices on your LAN ask PPSPi for time. |
| Stratum 1 | An NTP server synchronized directly from a reference such as GNSS/PPS. |
