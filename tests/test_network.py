import unittest
from unittest.mock import Mock, patch

from toss_manager.network import get_public_ipv4, is_ip_not_allowed


class NetworkTests(unittest.TestCase):
    @patch("toss_manager.network.requests.get")
    def test_reads_public_ipv4(self, get: Mock) -> None:
        response = Mock()
        response.json.return_value = {"ip": "35.230.127.150"}
        get.return_value = response
        self.assertEqual(get_public_ipv4(), "35.230.127.150")
        response.raise_for_status.assert_called_once()

    @patch("toss_manager.network.requests.get")
    def test_rejects_private_address(self, get: Mock) -> None:
        response = Mock()
        response.json.return_value = {"ip": "127.0.0.1"}
        get.return_value = response
        with self.assertRaisesRegex(ValueError, "공인 IPv4"):
            get_public_ipv4()

    def test_detects_toss_ip_error(self) -> None:
        self.assertTrue(is_ip_not_allowed("access_denied: IP address not allowed"))
        self.assertFalse(is_ip_not_allowed("invalid token"))


if __name__ == "__main__":
    unittest.main()
