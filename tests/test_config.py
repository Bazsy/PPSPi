from __future__ import annotations

import math
import sys
import tempfile
import unittest
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT / "files" / "ppstime"))

from ppstime_core import (
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
        self.assertEqual(self.config["GPS_DEVICE"], "/dev/serial0")
        self.assertEqual(self.config["PPS_ASSERT_EDGE"], "rising")

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

    def test_rejects_public_or_invalid_cidr(self) -> None:
        for value in ("0.0.0.0/0", "8.8.8.0/24", "192.168.1.1/24", "not-a-cidr"):
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

    def test_rejects_device_path_traversal(self) -> None:
        with self.assertRaises(ConfigError):
            validate_config(dict(self.config, GPS_DEVICE="/dev/../etc/shadow"))

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