"""Offline checks for educational player touchdown allocation."""
import unittest
from player_td_model import player_td_projection

def game(when, state="post"):
    return {"id": "NFL|1", "date": when, "state": state,
            "home_id": "H", "away_id": "A",
            "home": "Home", "away": "Away",
            "home_score": 21, "away_score": 14}

class PlayerTDTests(unittest.TestCase):
    def test_allocation_and_no_quarterback_passing_td(self):
        prior = game("2026-10-01T12:00:00Z")
        match = game("2026-10-20T12:00:00Z", "pre")
        def roster(league, team):
            return {"verified": True, "error": "", "players": [
                {"id": "1", "name": "Receiver", "position": "WR"},
                {"id": "2", "name": "Passer", "position": "QB"}]}
        def stats(league, previous):
            return [
                {"player_id": "1", "player": "Receiver", "category": "receiving",
                 "stat": "TD", "value": 1., "team": "Home"},
                {"player_id": "1", "player": "Receiver", "category": "receiving",
                 "stat": "YDS", "value": 70., "team": "Home"},
                {"player_id": "2", "player": "Passer", "category": "passing",
                 "stat": "TD", "value": 4., "team": "Home"}]
        result = player_td_projection(match, [prior], roster_loader=roster,
                                      observations_loader=stats)
        self.assertEqual(len(result["home"]["rows"]), 1)
        self.assertEqual(result["home"]["rows"][0]["Player"], "Receiver")
        self.assertGreater(result["home"]["rows"][0]["Projected TD equivalent"], 0)
    def test_no_data_no_fabricated_players(self):
        match = game("2026-10-20T12:00:00Z", "pre")
        result = player_td_projection(
            match, [], roster_loader=lambda *args: {"verified":False,"error":"","players":[]},
            observations_loader=lambda *args: [])
        self.assertEqual(result["home"]["rows"], [])
        self.assertEqual(result["away"]["rows"], [])

if __name__ == "__main__":
    unittest.main()
