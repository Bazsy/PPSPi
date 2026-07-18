# Hardware

## Supported target

The initial profile targets:

- Raspberry Pi 4 Model B;
- Uputronics **GPS/RTC Expansion Board for Raspberry Pi** V6.0 or later, with
  RV-3028-C7 RTC;
- active external GNSS antenna;
- Ethernet;
- Raspberry Pi OS Lite 64-bit Bookworm.

The Uputronics product description says the current board works with Raspberry
Pi boards using the 2x20 header and is backward-compatible with previous GPS
boards. PPSPi does **not** interpret that statement as proof that every older RTC
revision uses the same overlay.

## Verified current-board mapping

| Function | BCM GPIO / bus | Header pin | Linux/PPSPi setting | Evidence |
| --- | --- | --- | --- | --- |
| GPS UART transmit from Pi | GPIO 14 / TXD | 8 | `/dev/serial0` | Uputronics-linked pinout |
| GPS UART receive at Pi | GPIO 15 / RXD | 10 | `/dev/serial0`, 115200 baud | Uputronics V6.4 datasheet |
| PPS | GPIO 18 | 12 | `dtoverlay=pps-gpio,gpiopin=18` | Uputronics-linked pinout and firmware overlay definition |
| RTC I2C data | GPIO 2 / SDA1 | 3 | I2C1 | Uputronics-linked pinout |
| RTC I2C clock | GPIO 3 / SCL1 | 5 | I2C1 | Uputronics-linked pinout |
| RTC | I2C address `0x52` | I2C bus | `dtoverlay=i2c-rtc,rv3028` | current-board pinout and firmware overlay definition |

The current board is described as using a Micro Crystal **RV-3028-C7** RTC and
a u-blox M8-family GNSS receiver. The linked pinout identifies the u-blox device
at I2C address `0x42`, but PPSPi uses its UART output for GPSD.

The Uputronics datasheet revision 6.4 (March 2026) says it applies to PCB V6.4
and covers all versions later than V6.0. Page 2 specifies a default baud rate of
**115200 bps**, and page 6 verifies serial operation with `minicom -b 115200`.
The same page explicitly states that **older boards defaulted to 9600 baud**.
PPSPi therefore fixes GPSD at 115200 for this V6.0+ profile instead of waiting
for autobaud. An older board needs a separately identified profile or an
explicit, hardware-verified override.

The Raspberry Pi firmware overlay documentation confirms:

- `pps-gpio` defaults to GPIO 18 and accepts `gpiopin`,
  `assert_falling_edge`, `capture_clear`, and `pull` parameters;
- `i2c-rtc` accepts `rv3028` for the Micro Crystal RV3028 family.

## Sources

Authoritative or manufacturer-selected references checked for this profile:

- [Uputronics current product page](https://store.uputronics.com/products/raspberry-pi-gps-rtc-expansion-board)
- [Uputronics current-board datasheet](https://cdn.shopify.com/s/files/1/0835/7707/8094/files/Uputronics_Raspberry_Pi_GPS_RTC_Board_Datasheet_9eec2e77-d368-45ee-acc2-be899ff1d0be.pdf?v=1736517155)
- [Pinout page linked by Uputronics](https://pinout.xyz/pinout/uputronics_gps_expansion_board)
- [Official Raspberry Pi firmware overlay definitions](https://github.com/raspberrypi/firmware/blob/master/boot/overlays/README)
- [Official Raspberry Pi `config.txt` documentation](https://www.raspberrypi.com/documentation/computers/config_txt.html)

Source verification does not replace direct board identification and hardware
testing.

## Board revision gate

Before a release candidate is accepted:

1. photograph or record the HAT revision and RTC marking;
2. confirm the RTC appears at `0x52` with `i2cdetect -y 1`;
3. confirm the driver reports an RV-3028 device;
4. confirm the board's PPS trace reaches physical pin 12 / BCM GPIO 18;
5. confirm GPSD reports 115200 bps for the serial device;
6. run the complete [hardware acceptance plan](hardware-test-plan.md).

If the physical board has another RTC, stop. Add a separately named profile
only after finding authoritative documentation for that revision. Do not change
the current profile to accommodate an unidentified board.

## UART and Bluetooth

PPSPi uses `/dev/serial0`, Raspberry Pi's stable alias for the primary header
UART, and sets `enable_uart=1`. It removes the serial-console kernel argument so
the GPS receiver has exclusive access.

The profile does **not** disable Bluetooth. On Pi 4, Raspberry Pi firmware and
OS aliases choose the primary header UART. `enable_uart=1` also handles the
clocking requirement when the mini UART is selected. A future profile may
explicitly select the PL011 and disable or remap Bluetooth only if measured
timing evidence justifies that trade-off.

## PPS polarity

The current profile uses the Linux PPS assert event on the rising edge. Both the
boot overlay and Chrony renderer change together if a profile selects `falling`.
Polarity changes require oscilloscope, logic-analyser, manufacturer, or direct
`ppstest` evidence; visual LED behavior is not enough.

## RTC role

The RV-3028 maintains approximate UTC while the Pi is powered off. It is not a
precision or authoritative reference. PPSPi restores from it early at boot and
writes it only after Chrony reports valid synchronization, initially after 20
minutes and then at a randomized daily time.

Timing hierarchy:

```text
PPS              -> precision
GPS time-of-day  -> absolute second label
network NTP      -> startup and fallback
RTC              -> offline boot approximation
```
