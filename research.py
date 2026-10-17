"""Public-source roster verification and matchup research (not wagering forecasts).

Endpoints are unofficial; always distinguish unavailable data from verified negatives.
"""
from __future__ import annotations
from collections import defaultdict
from datetime import datetime, timezone
from engine import BASE, LEAGUES, fetch_json


def roster_snapshot(league: str, team_id: str) -> dict:
    sport, code = LEAGUES[league]
    url = f"{BASE}/{sport}/{code}/teams/{team_id}/roster"
    result = {"source": url, "retrieved_utc": datetime.now(timezone.utc).isoformat(),
              "verified": False, "players": [], "error": ""}
    try:
        raw = fetch_json(url)
        # ESPN has both a flat athletes list and position groups, varying by sport.
        entries = raw.get("athletes") or []
        flat = []
        if isinstance(entries, list):
            for entry in entries:
                if not isinstance(entry, dict):
                    continue
                if isinstance(entry.get("items"), list):
                    flat.extend(item for item in entry["items"] if isinstance(item, dict))
                else:
                    flat.append(entry)
        for a in flat:
            player_id = a.get("id")
            if not player_id:
                continue
            position = a.get("position") or {}
            injury = a.get("injury") or {}
            if not isinstance(injury, dict):
                injury = {}
            result["players"].append({
                "id": str(player_id),
                "name": a.get("displayName") or a.get("fullName") or a.get("name") or "",
                "position": position.get("abbreviation", "") if isinstance(position, dict) else str(position),
                "injury_status": injury.get("status") or injury.get("type") or "",
                "injury_note": injury.get("detail") or injury.get("description") or "",
            })
        result["verified"] = bool(result["players"])
        if not result["verified"]:
            result["error"] = "The provider returned no usable roster entries."
    except Exception as exc:
        result["error"] = f"Roster request failed: {type(exc).__name__}"
    return result


def team_defense_history(games: list, team_id: str, n: int = 8) -> dict:
    past = [g for g in games if g.get("state") == "post" and
            team_id in (g.get("home_id"), g.get("away_id"))]
    past = sorted(past, key=lambda g: g["date"])[-n:]
    conceded = [g["away_score"] if g["home_id"] == team_id else g["home_score"] for g in past]
    scored = [g["home_score"] if g["home_id"] == team_id else g["away_score"] for g in past]
    return {"games": len(past),
            "avg_allowed": round(sum(conceded) / len(conceded), 2) if conceded else None,
            "avg_scored": round(sum(scored) / len(scored), 2) if scored else None,
            "scores_allowed": conceded}


def quality_summary(records: list, home_roster: dict, away_roster: dict) -> dict:
    return {
        "rosters_verified": home_roster["verified"] and away_roster["verified"],
        "roster_players": len(home_roster["players"]) + len(away_roster["players"]),
        "player_stat_rows": len(records),
        "injury_data_complete": False,  # roster pages are NOT an official full injury report
        "trades_verified": False,        # roster membership does not establish recent trade history
    }
