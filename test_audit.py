import unittest
from audit import keys, ownership, pr_urls, github_query


class AuditTests(unittest.TestCase):
    def test_github_uses_one_date_range_qualifier(self):
        q = github_query('cisco-aispg', '2025-11-16T08:00:00Z', '2026-01-01T00:00:00+00:00')
        self.assertEqual(q.count('updated:'), 1)
        self.assertIn('updated:2025-11-16T08:00:00Z..2026-01-01T00:00:00Z', q)

    def test_key_boundaries_and_duplicates(self):
        self.assertEqual(keys('AISTUDIO-12 aistudio-12 XAISTUDIO-34'), ['AISTUDIO-12'])

    def test_missing_links_are_not_external(self):
        self.assertIsNone(ownership([]))
        self.assertEqual(ownership(['cisco-sbg/ai-studio-ui']), 'Core-owned only')
        self.assertEqual(ownership(['cisco-sbg/aispg-splunk-terraform']), 'Core-owned only')

    def test_three_ownership_groups(self):
        self.assertEqual(ownership(['cisco-aispg/ai-studio', 'cisco-aispg/ai-ui']), 'Core-owned only')
        self.assertEqual(ownership(['cisco-aispg/ai-ui', 'cisco-aispg/ai-services']), 'Core-owned and external')
        self.assertEqual(ownership(['cisco-aispg/ai-services']), 'Externally owned only')
        self.assertEqual(ownership(['another-org/ai-ui']), 'Externally owned only')

    def test_only_canonical_github_pr_links(self):
        self.assertEqual(pr_urls(['https://github.com/cisco-aispg/ai-ui/pull/42/files', 'https://evil.test/a/b/pull/9']), ['https://github.com/cisco-aispg/ai-ui/pull/42'])


if __name__ == '__main__':
    unittest.main()
