"""Experimental NFL team-level offensive touchdown estimates.

Only model team scoring opportunities; never interpret as player TD likelihoods.
The model maps estimated scoring to touchdown equivalents and is not calibrated.
"""
from nfl_model import team_metrics

def project_team_tds(match, completed):
    # Completed results strictly before kickoff prevent future information leakage.
    previous = [g for g in completed if g.get("state") == "post" and g["date"] < match["date"]]
    home = team_metrics(previous, match["home_id"])
    away = team_metrics(previous, match["away_id"])
    def estimate(offense, opposing_defense):
        # Approximate scoring opportunities using 55% team offense / 45% opponent points conceded.
        expected_points = .55 * offense["offense_ppg"] + .45 * opposing_defense["allowed_ppg"]
        # Seven points per touchdown equivalent is a heuristic, not exact football scoring:
        # field goals, 2-point conversions, safeties and defensive scores are not separated.
        center = max(0., expected_points / 7.0)
        # Wide, non-statistical illustrative sensitivity band (+/- 30%).
        return {"expected": round(center, 2),
                "low": round(max(0., center * .7), 2),
                "high": round(center * 1.3, 2),
                "points": round(expected_points, 1)}
    return {
        "away": estimate(away, home),
        "home": estimate(home, away),
        "away_games": away["games"],
        "home_games": home["games"],
        "method": "Scoring touchdown equivalents (unvalidated heuristic)"
    }
