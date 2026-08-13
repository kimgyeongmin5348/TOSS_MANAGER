import unittest

from toss_manager.repository import mask_account_number


class AccountMaskTests(unittest.TestCase):
    def test_masks_all_but_last_four_characters(self) -> None:
        self.assertEqual(mask_account_number("1234-5678-9012"), "********9012")

    def test_short_value_still_has_mask(self) -> None:
        self.assertEqual(mask_account_number("123"), "****123")

    def test_empty_value_returns_none(self) -> None:
        self.assertIsNone(mask_account_number(None))
        self.assertIsNone(mask_account_number("---"))


if __name__ == "__main__":
    unittest.main()
