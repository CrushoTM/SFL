"""Offline checks for descriptive touchdown history."""
import unittest
from unittest.mock import patch
from touchdown_history import summarize_touchdowns


class TouchdownHistoryTests(unittest.TestCase):
    def test_counts_observed_td_without_guessing(self):
        game = {"id": "NFL|123", "date": "2026-10-01T12:00:00Z",
                "state": "post", "home_id": "1", "away_id": "2"}
        stats = [
            {"player": "Runner", "player_id": "7", "team": "Home",
             "category": "rushing", "stat": "TD", "value": 2},
            {"player": "Runner", "player_id": "7", "team": "Home",
             "category": "rushing", "stat": "YDS", "value": 85},
            {"player": "Passer", "player_id": "8", "team": "Home",
             "category": "passing", "stat": "TD", "value": 3},
        ]
        with patch("touchdown_history.player_observations", return_value=stats):
            result = summarize_touchdowns([game], "1", "Home")
        self.assertEqual(len(result["rows"]), 1)
        self.assertEqual(result["rows"][0]["Total offensive TD"], 2)
        self.assertEqual(result["rows"][0]["Games with TD observed"], 1)

    def test_missing_games_reported(self):
        game = {"id": "NFL|123", "date": "2026-10-01T12:00:00Z",
                "state": "post", "home_id": "1", "away_id": "2"}
        with patch("touchdown_history.player_observations", return_value=[]):
            result = summarize_touchdowns([game], "1", "Home")
        self.assertEqual(result["missing_games"], 1)
        self.assertEqual(result["rows"], [])


if __name__ == "__main__":
    unittest.main()
