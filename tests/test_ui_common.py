import unittest

from toss_manager.ui.formatting import percentage, percentage_text


class PercentageTests(unittest.TestCase):
    def test_ratio_is_displayed_as_percentage(self) -> None:
        self.assertEqual(percentage(0.03), 3.0)
        self.assertEqual(percentage_text(0.03), "+3.00%")

    def test_negative_ratio_is_displayed_as_percentage(self) -> None:
        self.assertEqual(percentage_text(-0.0125), "-1.25%")


if __name__ == "__main__":
    unittest.main()
