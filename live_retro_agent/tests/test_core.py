import unittest

from live_retro_agent.analysis import classify, parse_range
from live_retro_agent.workbooks import parse_number


class CoreTests(unittest.TestCase):
    def test_time_range(self):
        self.assertEqual(parse_range("00:12:03-00:13:05"), (723.0, 785.0))

    def test_number_units(self):
        self.assertEqual(parse_number("3.16万"), 31600)
        self.assertEqual(parse_number("¥1,999"), 1999)

    def test_five_stage_classification(self):
        self.assertEqual(classify("马上要下播了，赶紧去拍", "催单")[0], "逼单")
        self.assertEqual(classify("你看我六十一岁这个头发和脸的状态", "人设")[0], "塑品")


if __name__ == "__main__":
    unittest.main()
