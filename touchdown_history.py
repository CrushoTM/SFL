"""NFL touchdown history extracted from completed-game box scores.

This is a *descriptive* module, not a model for future individual scorers.
"""
from collections import defaultdict
from engine import player_observations


def recent_team_games(completed, team_id, limit=6):
    games = [g for g in completed if team_id in (g.get("home_id"), g.get("away_id"))]
    return sorted(games, key=lambda x: x["date"], reverse=True)[:limit]


def summarize_touchdowns(completed, team_id, team_name, limit=6):
    games = recent_team_games(completed, team_id, limit)
    by_player = defaultdict(lambda: {"name": "", "rushing": 0, "receiving": 0,
                                      "observed_games": set(), "td_games": set()})
    missing = 0
    for g in games:
        stats = player_observations("NFL", g)
        # Empty fetches are reported as incomplete, never silently counted as zeros.
        if not stats:
            missing += 1
            continue
        matched_team = False
        for row in stats:
            if row.get("team") != team_name:
                continue
            matched_team = True
            category = str(row.get("category", "")).lower()
            stat = str(row.get("stat", "")).upper().strip()
            if not ("rush" in category or "receiv" in category):
                continue
            key = str(row.get("player_id") or row["player"])
            player = by_player[key]
            player["name"] = row["player"]
            player["observed_games"].add(g["id"])
            if stat not in {"TD", "TDS", "TOUCHDOWNS"}:
                continue
            count = max(0, int(row.get("value", 0)))
            kind = "rushing" if "rush" in category else "receiving"
            player[kind] += count
            if count:
                player["td_games"].add(g["id"])
        if not matched_team:
            missing += 1
    results = []
    for player in by_player.values():
        total = player["rushing"] + player["receiving"]
        if total == 0:
            continue
        results.append({"Player": player["name"], "Rushing TD (observed)": player["rushing"],
                        "Receiving TD (observed)": player["receiving"],
                        "Total offensive TD": total,
                        "Games with TD observed": len(player["td_games"]),
                        "Games with recorded stats": len(player["observed_games"])})
    results.sort(key=lambda row: (-row["Total offensive TD"], row["Player"]))
    return {"team": team_name, "games_requested": len(games), "missing_games": missing,
            "rows": results}
