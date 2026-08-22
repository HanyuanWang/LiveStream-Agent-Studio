import unittest

import local_gateway


class DirectorSourceUrlTests(unittest.TestCase):
    def test_extracts_short_link_from_douyin_share_copy(self):
        value = "743 文案 https://v.douyin.com/jK586QrMSRI/复制此链接，打开抖音搜索"
        self.assertEqual(
            local_gateway.validate_source_url(value),
            "https://v.douyin.com/jK586QrMSRI/",
        )

    def test_keeps_direct_video_query(self):
        value = "https://www.douyin.com/video/7671508520651765157?previous_page=web_code_link"
        self.assertEqual(local_gateway.validate_source_url(value), value)

    def test_rejects_douyin_home_page(self):
        with self.assertRaisesRegex(RuntimeError, "具体视频链接"):
            local_gateway.validate_source_url("https://www.douyin.com/")


if __name__ == "__main__":
    unittest.main()
