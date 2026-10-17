"""NFL-only, descriptive matchup forecasting research.

All numbers come from finished games in the fetched season window.
The weighted matchup probability is experimental and NOT calibrated.
No betting lines or wager recommendations are used.
"""
from collections import defaultdict
from datetime import datetime, timezone
from math import exp
from engine import fit_ratings


def team_metrics(finished, team_id):
    played = sorted([g for g in finished if team_id in (g["home_id"], g["away_id"])], key=lambda g: g["date"])
    scored = []
    allowed = []
    wins = 0
    for g in played:
        home = g["home_id"] == team_id
        pf = g["home_score"] if home else g["away_score"]
        pa = g["away_score"] if home else g["home_score"]
        scored.append(pf)
        allowed.append(pa)
        wins += int(pf > pa)
    # NFL context priors; preserve them when historical sampling is thin.
    prior_games = 3.0
    points_prior = 22.0
    n = len(played)
    offense = (sum(scored) + prior_games * points_prior) / (n + prior_games)
    defense_allowed = (sum(allowed) + prior_games * points_prior) / (n + prior_games)
    last = played[-4:]
    recent_margin = 0.0
    if last:
        margins = []
        for g in last:
            home = g["home_id"] == team_id
            margins.append((g["home_score"] - g["away_score"]) * (1 if home else -1))
        recent_margin = sum(margins) / len(margins)
    return {
        "games": n, "wins": wins, "losses": n - wins,
        "offense_ppg": round(offense, 2), "allowed_ppg": round(defense_allowed, 2),
        "recent_margin": round(recent_margin, 2),
        "raw_offense": round(sum(scored) / n, 2) if n else None,
        "raw_allowed": round(sum(allowed) / n, 2) if n else None,
        "last_games": len(last),
    }


def forecast(game, completed):
    """Predict a research-model winner using PRE-game results only."""
    historical = sorted([g for g in completed if g["state"] == "post" and g["date"] < game["date"]], key=lambda g: g["date"])
    ratings = fit_ratings(historical)
    home = team_metrics(historical, game["home_id"])
    away = team_metrics(historical, game["away_id"])
    # Matchup scoring context: opponent offense versus points allowed by defense.
    home_matchup = 0.55 * home["offense_ppg"] + 0.45 * away["allowed_ppg"]
    away_matchup = 0.55 * away["offense_ppg"] + 0.45 * home["allowed_ppg"]
    matchup_edge = home_matchup - away_matchup
    elo_home = ratings.get(game["home_id"], 1500.0)
    elo_away = ratings.get(game["away_id"], 1500.0)
    elo_edge = (elo_home - elo_away) / 28.0
    form_edge = (home["recent_margin"] - away["recent_margin"]) * 0.12
    # Transparent heuristic; home field prior ~1.5 points. No injury assumptions.
    combined_edge = 1.5 + 0.55 * matchup_edge + 0.30 * elo_edge + form_edge
    # 13.5 is a fixed sensitivity scale, not fitted calibration.
    home_prob = 1.0 / (1.0 + exp(-combined_edge / 6.75))
    home_prob = max(0.1, min(0.9, home_prob))
    winner = "home" if home_prob >= 0.5 else "away"
    observed = min(home["games"], away["games"])
    return {
        "winner": game[winner],
        "winner_side": winner,
        "win_probability": round(home_prob if winner == "home" else 1 - home_prob, 4),
        "home_probability": round(home_prob, 4),
        "away_probability": round(1 - home_prob, 4),
        "offense_defense_edge": round(matchup_edge, 2),
        "elo_edge": round(elo_edge, 2),
        "recent_form_edge": round(form_edge, 2),
        "home": home,
        "away": away,
        "sample_games_min": observed,
        "status": "Limited sample" if observed < 3 else "Experimental model",
    }


def rolling_validation(completed, minimum_prior_games=16):
    """Chronological evaluation: no future games used to create historical forecasts."""
    games = sorted([g for g in completed if g["state"] == "post"], key=lambda g: g["date"])
    outputs = []
    for i, game in enumerate(games):
        if i < minimum_prior_games or game["home_score"] == game["away_score"]:
            continue
        pred = forecast(game, games[:i])
        actual_home = int(game["home_score"] > game["away_score"])
        p = pred["home_probability"]
        outputs.append({"date": game["date"][:10], "brier": (p - actual_home) ** 2,
                        "correct": int((p >= .5) == bool(actual_home))})
    if not outputs:
        return None
    return {"games": len(outputs),
            "winner_accuracy": sum(x["correct"] for x in outputs) / len(outputs),
            "brier": sum(x["brier"] for x in outputs) / len(outputs)}
