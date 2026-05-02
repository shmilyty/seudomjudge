import unittest

from rollboard.tools import patch_xcpcio_dist


class PatchXcpcioDistTest(unittest.TestCase):
    def test_injects_rollboard_base_and_root_data_host(self):
        html = (
            '<script>function normalizePath(_){}'
            'try{let _=__BASE_URL__;window.BASE_URL=_}catch(_){}'
            'try{let _=__DATA_HOST__;_=normalizePath(_),window.DATA_HOST=_}'
            'catch(_){window.DATA_HOST="/data/"}'
            "</script>"
        )

        patched = patch_xcpcio_dist.patch_html(html, base_path="/rollboard/", data_host="/")

        self.assertIn('window.BASE_URL="/rollboard/"', patched)
        self.assertIn('window.DATA_HOST="/"', patched)
        self.assertNotIn('window.DATA_HOST="/data/"', patched)

    def test_patch_is_idempotent(self):
        html = (
            '<script>function normalizePath(_){}'
            'try{let _=__BASE_URL__;window.BASE_URL=_}catch(_){}'
            'try{let _=__DATA_HOST__;_=normalizePath(_),window.DATA_HOST=_}'
            'catch(_){window.DATA_HOST="/data/"}'
            "</script>"
        )

        once = patch_xcpcio_dist.patch_html(html, base_path="/rollboard/", data_host="/")
        twice = patch_xcpcio_dist.patch_html(once, base_path="/rollboard/", data_host="/")

        self.assertEqual(once, twice)


if __name__ == "__main__":
    unittest.main()
