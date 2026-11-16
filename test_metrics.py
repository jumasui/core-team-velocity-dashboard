import unittest
from metrics import timeline, timestamp, primary_keys, dependencies


def issue(status='6'):
    return {'key': 'AISTUDIO-1', 'fields': {'created': '2025-11-01T00:00:00Z', 'status': {'id': status}}}


def change(day, old, new):
    return {'created': f'2025-11-{day:02}T00:00:00Z', 'items': [{'field': 'status', 'from': old, 'to': new}]}


class TimelineTests(unittest.TestCase):
    def test_later_changes_do_not_rewrite_cutoff_state(self):
        r = timeline(issue('3'), [change(2, '10056', '6'), change(12, '6', '3')], '2025-11-10T00:00:00Z', {'6'})
        self.assertFalse(r['open'])
        self.assertTrue(r['reached_done'])
        self.assertEqual(r['history_errors'], [])

    def test_reopened_ticket_still_reached_done(self):
        r = timeline(issue('3'), [change(2, '10056', '6'), change(5, '6', '3')], '2025-11-10T00:00:00Z', {'6'})
        self.assertTrue(r['open'])
        self.assertTrue(r['reached_done'])
        self.assertIsNone(r['done_at'])

    def test_dependency_direction_not_reversed(self):
        links = [{'type': {'inward': 'is blocked by', 'outward': 'blocks'}, 'inwardIssue': {'key': 'AISTUDIO-2'}},
                 {'type': {'inward': 'is blocked by', 'outward': 'blocks'}, 'outwardIssue': {'key': 'AISTUDIO-3'}}]
        self.assertEqual(dependencies(links), ['AISTUDIO-2'])

    def test_carried_in_and_missing_resolution(self):
        r = timeline(issue(), [change(10, '10056', '3'), change(20, '3', '6')], '2025-11-21T00:00:00Z', {'6'})
        self.assertEqual(r['todo_to_progress_days'], 9)
        self.assertEqual(r['cycle_days'], 10)
        self.assertEqual(r['lead_days'], 19)

    def test_reopened_and_repeated_review_visits(self):
        h = [change(2, '10056', '3'), change(3, '3', '10083'), change(5, '10083', '6'),
             change(6, '6', '3'), change(7, '3', '10083'), change(9, '10083', '6')]
        r = timeline(issue(), list(reversed(h)), '2025-11-10T00:00:00Z', {'6'})
        self.assertEqual(r['reopened'], 1)
        self.assertEqual(r['state_days']['10083'], 4)
        self.assertEqual(r['lead_days'], 8)
        self.assertEqual(r['progress_to_review_days'], 1)
        self.assertEqual(r['review_to_done_days'], 6)
        self.assertEqual(sum(r['state_days'].values()), 9)

    def test_open_ticket_has_age_without_completion(self):
        r = timeline(issue('3'), [], '2025-11-10T00:00:00Z', {'6'})
        self.assertTrue(r['open'])
        self.assertIsNone(r['done_at'])

    def test_inconsistent_history_is_flagged(self):
        r = timeline(issue(), [change(2, '3', '10083'), change(3, '3', '6')], '2025-11-10T00:00:00Z', {'6'})
        self.assertTrue(r['history_errors'])

    def test_body_only_references_are_candidates(self):
        self.assertEqual(primary_keys({'title': 'AISTUDIO-1 fix', 'body': 'Related AISTUDIO-2'}), (['AISTUDIO-1'], ['AISTUDIO-2']))

    def test_invalid_timestamp_is_rejected(self):
        with self.assertRaises(ValueError):
            timestamp('missing')


if __name__ == '__main__':
    unittest.main()
