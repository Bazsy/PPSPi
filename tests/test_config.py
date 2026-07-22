from __future__ import annotations

import math
import sys
import tempfile
import unittest
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT / "files" / "ppstime"))

from ppstime_core import (
    CONFIG_KEYS,
    ConfigError,
    load_config,
    model_is_supported,
    parse_env_file,
    validate_config,
)


class ConfigTests(unittest.TestCase):
    def setUp(self) -> None:
        self.config = load_config(PROJECT_ROOT, environ={})

    def test_uputronics_values_are_source_verified_defaults(self) -> None:
        self.assertEqual(self.config["PPS_GPIO"], "18")
        self.assertEqual(self.config["RTC_OVERLAY"], "rv3028")
        self.assertEqual(self.config["RTC_BACKUP_SWITCH_MODE"], "3")
        self.assertEqual(self.config["GPS_DEVICE"], "/dev/serial0")
        self.assertEqual(self.config["GPS_BAUD"], "115200")
        self.assertEqual(self.config["PPS_ASSERT_EDGE"], "rising")

    def test_default_ntp_access_covers_standard_private_lan_ranges(self) -> None:
        self.assertEqual(
            self.config["NTP_ALLOW"],
            "10.0.0.0/8,172.16.0.0/12,192.168.0.0/16,fc00::/7",
        )
        self.assertEqual(self.config["CHRONY_MAX_CLOCK_ERROR_PPM"], "200")
        self.assertEqual(self.config["CHRONY_MAX_DISTANCE"], "0.1")

    def test_host_health_threshold_defaults_and_validation(self) -> None:
        self.assertEqual(self.config["HOST_DISK_WARNING_PERCENT"], "15.0")
        self.assertEqual(self.config["HOST_TEMPERATURE_CRITICAL_C"], "85.0")
        self.assertEqual(self.config["HOST_UPDATE_CRITICAL_HOURS"], "168.0")
        invalid_cases = (
            {"HOST_DISK_CRITICAL_PERCENT": "20"},
            {"HOST_INODE_WARNING_PERCENT": "101"},
            {"HOST_TEMPERATURE_WARNING_C": "90"},
            {"HOST_UPDATE_CRITICAL_HOURS": "24"},
            {"HOST_DISK_WARNING_PERCENT": "nan"},
        )
        for changes in invalid_cases:
            with self.subTest(changes=changes), self.assertRaises(ConfigError):
                validate_config(dict(self.config, **changes))

    def test_active_configuration_has_no_secret_keys(self) -> None:
        sensitive = ("PASSWORD", "SECRET", "TOKEN", "PRIVATE", "WIFI", "SSID", "KEY")
        self.assertFalse(
            [key for key in CONFIG_KEYS if any(fragment in key for fragment in sensitive)]
        )

    def test_environment_override_is_validated(self) -> None:
        config = load_config(PROJECT_ROOT, environ={"NTP_ALLOW": "10.42.0.0/16"})
        self.assertEqual(config["NTP_ALLOW"], "10.42.0.0/16")

    def test_custom_file_can_select_profile(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            custom = Path(temporary) / "custom.env"
            custom.write_text(
                "PPSTIME_PROFILE=uputronics-gps-rtc-hat\nNTP_ALLOW=10.50.0.0/16\n",
                encoding="utf-8",
            )
            config = load_config(PROJECT_ROOT, custom_path=custom, environ={})
        self.assertEqual(config["PPSTIME_PROFILE"], "uputronics-gps-rtc-hat")
        self.assertEqual(config["NTP_ALLOW"], "10.50.0.0/16")

    def test_rejects_non_lan_or_invalid_cidr(self) -> None:
        for value in (
            "0.0.0.0/0",
            "8.8.8.0/24",
            "127.0.0.0/8",
            "169.254.0.0/16",
            "100.64.0.0/10",
            "224.0.0.0/4",
            "::1/128",
            "fe80::/10",
            "ff00::/8",
            "2001:db8::/32",
            "192.168.1.1/24",
            "not-a-cidr",
        ):
            with self.subTest(value=value):
                invalid = dict(self.config, NTP_ALLOW=value)
                with self.assertRaises(ConfigError):
                    validate_config(invalid)

    def test_rejects_nonfinite_chrony_offsets(self) -> None:
        for value in ("nan", "inf", "-inf"):
            with self.subTest(value=value):
                self.assertFalse(math.isfinite(float(value)))
                with self.assertRaises(ConfigError):
                    validate_config(dict(self.config, CHRONY_GPS_OFFSET=value))

    def test_rejects_unsafe_chrony_fallback_bounds(self) -> None:
        cases = {
            "CHRONY_MAX_CLOCK_ERROR_PPM": ("0", "1001", "nan", "not-a-number"),
            "CHRONY_MAX_DISTANCE": ("0", "0.009", "1.1", "inf"),
        }
        for key, values in cases.items():
            for value in values:
                with self.subTest(key=key, value=value), self.assertRaises(ConfigError):
                    validate_config(dict(self.config, **{key: value}))

    def test_rejects_baud_rates_not_supported_by_gpsd(self) -> None:
        for value in ("1200", "14400", "115201", "921600"):
            with self.subTest(value=value), self.assertRaises(ConfigError):
                validate_config(dict(self.config, GPS_BAUD=value))

    def test_rejects_device_path_traversal(self) -> None:
        with self.assertRaises(ConfigError):
            validate_config(dict(self.config, GPS_DEVICE="/dev/../etc/shadow"))

    def test_rejects_invalid_rtc_backup_switch_modes(self) -> None:
        for value in ("-1", "4", "level", "3.0"):
            with self.subTest(value=value), self.assertRaises(ConfigError):
                validate_config(dict(self.config, RTC_BACKUP_SWITCH_MODE=value))

        for value in ("0", "1", "2", "3"):
            with self.subTest(value=value):
                validate_config(dict(self.config, RTC_BACKUP_SWITCH_MODE=value))

        with self.assertRaises(ConfigError):
            validate_config(
                dict(self.config, RTC_OVERLAY="ds3231", RTC_BACKUP_SWITCH_MODE="3")
            )

    def test_rejects_unknown_and_duplicate_keys(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / "bad.env"
            path.write_text("GPS_DEVICE=/dev/serial0\nUNKNOWN=value\n", encoding="utf-8")
            with self.assertRaises(ConfigError):
                parse_env_file(path)
            path.write_text("GPS_DEVICE=/dev/serial0\nGPS_DEVICE=/dev/ttyAMA0\n", encoding="utf-8")
            with self.assertRaises(ConfigError):
                parse_env_file(path)

    def test_model_support_matrix(self) -> None:
        cases = {
            "Raspberry Pi 4 Model B Rev 1.1": True,
            "Raspberry Pi 4 Model B Rev 1.5": True,
            "Raspberry Pi 3 Model B Plus Rev 1.3": False,
            "Raspberry Pi 5 Model B Rev 1.0": False,
            "Raspberry Pi Zero 2 W Rev 1.0": False,
            "Raspberry Pi 400 Rev 1.0": False,
        }
        for model, expected in cases.items():
            with self.subTest(model=model):
                self.assertEqual(model_is_supported(model, self.config), expected)


if __name__ == "__main__":
    unittest.main()