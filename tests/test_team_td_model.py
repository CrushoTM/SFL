import unittest
from team_td_model import project_team_tds

class TeamTouchdownProjectionTests(unittest.TestCase):
    def test_no_games_yields_identical_team_priors(self):
        match = {"home_id":"1","away_id":"2","date":"2026-10-20T18:00:00Z"}
        result = project_team_tds(match, [])
        self.assertEqual(result["away"]["expected"], result["home"]["expected"])
        self.assertGreaterEqual(result["home"]["low"], 0)
        self.assertEqual(result["home_games"], 0)
    def test_future_games_cannot_leak(self):
        match = {"home_id":"1","away_id":"2","date":"2026-10-20T18:00:00Z"}
        future = {"home_id":"1","away_id":"2","date":"2026-10-21T18:00:00Z",
                  "home_score":80,"away_score":0,"state":"post"}
        self.assertEqual(project_team_tds(match, []), project_team_tds(match, [future]))

if __name__ == "__main__":
    unittest.main()
