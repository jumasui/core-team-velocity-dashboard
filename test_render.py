import json
import unittest
from render import embedded_json


class RenderTests(unittest.TestCase):
    def test_untrusted_title_cannot_close_data_script(self):
        value = {'title': '</script><script>alert(1)</script>&'}
        encoded = embedded_json(value)
        self.assertNotIn('<', encoded)
        self.assertEqual(json.loads(encoded), value)


if __name__ == '__main__':
    unittest.main()
