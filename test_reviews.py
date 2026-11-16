import unittest
from reviews import rounds


def request(day, actor='Team'):
    return {'__typename': 'ReviewRequestedEvent', 'createdAt': f'2026-11-{day:02}T00:00:00Z',
            'requestedReviewer': {'__typename': actor, 'login': 'robot' if actor == 'Bot' else 'reviewer'}}


def review(day, actor='User', login='reviewer'):
    return {'__typename': 'PullRequestReview', 'createdAt': f'2026-11-{day:02}T00:00:00Z',
            'submittedAt': f'2026-11-{day:02}T00:00:00Z', 'state': 'APPROVED', 'author': {'__typename': actor, 'login': login}}


class RoundTests(unittest.TestCase):
    def run_rounds(self, events):
        return rounds({'author': {'login': 'author'}, 'events': events}, '2026-11-16T00:00:00Z')

    def test_bot_response_does_not_end_human_round(self):
        r = self.run_rounds([request(1), review(1, 'Bot'), review(3)])
        self.assertEqual(r[0]['response_hours'], 48)

    def test_rerequest_starts_next_round(self):
        r = self.run_rounds([request(1), review(2), request(3), review(5)])
        self.assertEqual([x['response_hours'] for x in r], [24, 48])

    def test_simultaneous_reviewer_requests_do_not_reset_wait(self):
        r = self.run_rounds([request(1), request(2), review(3)])
        self.assertEqual(r[0]['response_hours'], 48)

    def test_author_and_bot_requests_are_excluded(self):
        self.assertEqual(self.run_rounds([request(1, 'Bot'), review(2)]), [])
        self.assertIsNone(self.run_rounds([request(1), review(2, login='author')])[0]['responded_at'])

    def test_no_request_does_not_invent_a_round(self):
        self.assertEqual(self.run_rounds([review(2)]), [])

    def test_draft_cancels_pending_round(self):
        r = self.run_rounds([request(1), {'__typename': 'ConvertToDraftEvent', 'createdAt': '2026-11-02T00:00:00Z'}])
        self.assertIsNone(r[0]['response_hours'])

    def test_removed_request_is_conservatively_unmeasured(self):
        r = self.run_rounds([request(1), {'__typename': 'ReviewRequestRemovedEvent', 'createdAt': '2026-11-02T00:00:00Z'}, review(3)])
        self.assertIsNone(r[0]['response_hours'])


if __name__ == '__main__':
    unittest.main()
