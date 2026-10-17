"""Offline unit tests for the NFL-only forecast baseline."""
import unittest
from nfl_model import forecast, team_metrics, rolling_validation

def game(date, home="H", away="A", hs=0, aw=0, state="post"):
    return {"date":date, "home":home, "away":away, "home_id":home,
            "away_id":away, "home_score":hs, "away_score":aw, "state":state}

class NflBaselineTests(unittest.TestCase):
    def test_offense_defense_direction(self):
        games = [game(f"2026-09-{i:02d}T12:00:00Z", hs=30, aw=10) for i in range(1,8)]
        h = team_metrics(games, "H")
        a = team_metrics(games, "A")
        self.assertGreater(h["offense_ppg"], a["offense_ppg"])
        self.assertLess(h["allowed_ppg"], a["allowed_ppg"])
    def test_favorite_probability_sums_to_one(self):
        games = [game(f"2026-09-{i:02d}T12:00:00Z", hs=31, aw=7) for i in range(1,8)]
        f = forecast(game("2026-10-01T12:00:00Z", state="pre"), games)
        self.assertEqual(f["winner_side"], "home")
        self.assertAlmostEqual(f["home_probability"] + f["away_probability"], 1.0, places=4)
    def test_future_results_never_enter_pregame_data(self):
        games = [game("2026-09-01T12:00:00Z", hs=30, aw=10),
                 game("2026-10-05T12:00:00Z", hs=0, aw=60)]
        f = forecast(game("2026-10-01T12:00:00Z", state="pre"), games)
        self.assertEqual(f["home"]["games"], 1)
        self.assertEqual(f["winner_side"], "home")
    def test_no_data_validation(self):
        self.assertIsNone(rolling_validation([]))

if __name__ == "__main__":
    unittest.main()
