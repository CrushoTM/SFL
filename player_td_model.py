"""Experimental expected offensive TD equivalents for upcoming NFL players.

Educational scoring allocation, not player touchdown probabilities or betting picks.
Only uses completed-game boxscore records from BEFORE a matchup.
"""
from collections import defaultdict
from engine import player_observations
from team_td_model import project_team_tds
from research import roster_snapshot


def player_td_projection(game, completed, limit=5, roster_loader=roster_snapshot,
                         observations_loader=player_observations):
    """Allocate each team's future TD-equivalent total to players by observed role.

    Uses touchdown production with conservative 0.20 smoothing for players with
    observed rushing or receiving involvement; passes are never counted as QB TDs.
    If current roster can be retrieved, only roster-verified athletes are included.
    Missing games and lineup/injury uncertainties are reported, not disguised.
    """
    past = sorted((g for g in completed if g["state"] == "post"
                   and g["date"] < game["date"]), key=lambda g: g["date"], reverse=True)
    team_tds = project_team_tds(game, completed)
    result = {}
    for side in ("away", "home"):
        team_id, team_name = game[side + "_id"], game[side]
        roster = roster_loader("NFL", team_id)
        roster_players = {p["id"]: p for p in roster.get("players", []) if p.get("id")}
        selected = [g for g in past if team_id in (g["home_id"], g["away_id"])][:limit]
        athletes = defaultdict(lambda: {"name": "", "position": "", "td": 0.0,
                                        "observed_games": set(), "td_games": set(),
                                        "categories": set()})
        missing_games = 0
        for old in selected:
            entries = observations_loader("NFL", old)
            if not entries:
                missing_games += 1
                continue
            relevant = []
            for r in entries:
                athlete_id = str(r.get("player_id", ""))
                # A roster match is stronger than comparing provider team name.
                if roster.get("verified"):
                    if athlete_id not in roster_players:
                        continue
                elif str(r.get("team", "")).casefold() != team_name.casefold():
                    continue
                category = str(r.get("category", "")).lower()
                if "rush" not in category and "receiv" not in category:
                    continue
                relevant.append(r)
            if not relevant:
                missing_games += 1
                continue
            for r in relevant:
                athlete_id = str(r.get("player_id") or r.get("player"))
                player = athletes[athlete_id]
                roster_entry = roster_players.get(athlete_id, {})
                player["name"] = roster_entry.get("name") or r.get("player", "Unknown")
                player["position"] = roster_entry.get("position") or r.get("position", "")
                player["observed_games"].add(old["id"])
                category = str(r.get("category", "")).lower()
                player["categories"].add("rush" if "rush" in category else "receiv")
                if str(r.get("stat", "")).upper().strip() in ("TD", "TDS", "TOUCHDOWNS"):
                    val = max(0., float(r.get("value", 0)))
                    player["td"] += val
                    if val > 0:
                        player["td_games"].add(old["id"])
        # Count only athletes with at least one rushing/receiving stat recorded.
        # Smooth each eligible athlete to avoid setting zero future usage for
        # someone who appeared but has not scored.
        denominator = sum(a["td"] + .20 for a in athletes.values())
        rows = []
        for a in athletes.values():
            share = ((a["td"] + .20) / denominator) if denominator else 0.0
            expected = share * team_tds[side]["expected"]
            rows.append({
                "Player": a["name"],
                "Position": a["position"] or "Unknown",
                "Projected TD equivalent": round(expected, 2),
                "Recorded games": len(a["observed_games"]),
                "Roster status": "Roster listed; availability unconfirmed" if roster.get("verified")
                    else "Roster not verified",
                "Data note": "Small sample" if len(a["observed_games"]) < 3 else "Experimental",
            })
        # Alphabetical so this is a research table, not a recommended player ranking.
        rows.sort(key=lambda r: r["Player"])
        result[side] = {
            "team": team_name, "rows": rows, "boxscore_games": len(selected),
            "missing_games": missing_games, "roster_verified": roster.get("verified", False),
            "roster_error": roster.get("error", ""),
            "total_expected_tds": team_tds[side]["expected"]
        }
    return result
