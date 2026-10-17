"""Offline unit tests for descriptive matchup research."""
import unittest
from research import team_defense_history, quality_summary


class ResearchTests(unittest.TestCase):
    def test_defensive_context_uses_correct_score_side(self):
        games = [
            {'state': 'post', 'date': '2026-01-01T10:00:00Z', 'home_id': '1',
             'away_id': '2', 'home_score': 24, 'away_score': 14},
            {'state': 'post', 'date': '2026-01-08T10:00:00Z', 'home_id': '3',
             'away_id': '1', 'home_score': 20, 'away_score': 17},
            {'state': 'pre', 'date': '2026-01-15T10:00:00Z', 'home_id': '1',
             'away_id': '4', 'home_score': 0, 'away_score': 0},
        ]
        result = team_defense_history(games, '1')
        self.assertEqual(result['games'], 2)
        self.assertEqual(result['avg_allowed'], 17)
        self.assertEqual(result['avg_scored'], 20.5)

    def test_missing_injury_data_is_not_called_verified(self):
        empty = {'verified': False, 'players': []}
        flags = quality_summary([], empty, empty)
        self.assertFalse(flags['rosters_verified'])
        self.assertFalse(flags['injury_data_complete'])
        self.assertFalse(flags['trades_verified'])


if __name__ == '__main__':
    unittest.main()
