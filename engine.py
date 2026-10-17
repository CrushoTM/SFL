"""Educational sports forecasting engine. Not for wagering decisions."""
from __future__ import annotations
import datetime as dt
import math
import statistics
import requests
from collections import defaultdict

LEAGUES = {
    'MLB': ('baseball', 'mlb'),
    'NFL': ('football', 'nfl'),
    'Soccer — EPL': ('soccer', 'eng.1'),
    'Soccer — LaLiga': ('soccer', 'esp.1'),
    'Soccer — UCL': ('soccer', 'uefa.champions'),
    'Soccer — MLS': ('soccer', 'usa.1'),
}
BASE = 'https://site.api.espn.com/apis/site/v2/sports'
SESSION = requests.Session()
SESSION.headers['Accept'] = 'application/json'


def fetch_json(url, params=None):
    response = SESSION.get(url, params=params, timeout=14)
    response.raise_for_status()
    return response.json()


def scoreboard(league, day):
    sport, code = LEAGUES[league]
    return fetch_json(f'{BASE}/{sport}/{code}/scoreboard', {'dates': day.strftime('%Y%m%d'), 'limit': 100}).get('events', [])


def normalize(raw, league):
    try:
        competition = raw['competitions'][0]
        clubs = competition['competitors']
        home = next(x for x in clubs if x['homeAway'] == 'home')
        away = next(x for x in clubs if x['homeAway'] == 'away')
        state = competition.get('status', raw.get('status', {})).get('type', {}).get('state', 'pre')
        return {
            'id': f'{league}|{raw["id"]}', 'api_id': str(raw['id']), 'league': league,
            'date': raw['date'], 'home': home['team']['displayName'], 'away': away['team']['displayName'],
            'home_id': str(home['team']['id']), 'away_id': str(away['team']['id']),
            'home_score': int(float(home.get('score', 0) or 0)), 'away_score': int(float(away.get('score', 0) or 0)),
            'state': state, 'status': raw.get('status', {}).get('type', {}).get('description', state)
        }
    except (KeyError, IndexError, StopIteration, TypeError, ValueError):
        return None


def load_games(league, before=25, after=7, today=None):
    today = today or dt.datetime.now(dt.timezone.utc).date()
    games = {}
    errors = []
    for offset in range(-before, after + 1):
        day = today + dt.timedelta(days=offset)
        try:
            for raw in scoreboard(league, day):
                game = normalize(raw, league)
                if game:
                    games[game['id']] = game
        except (requests.RequestException, ValueError) as e:
            errors.append(f'{day}: {str(e)[:100]}')
    return sorted(games.values(), key=lambda g: g['date']), errors


def fit_ratings(games):
    """No-lookahead sequential Elo. Match forecasts must be made *before* result updates."""
    ratings = defaultdict(lambda: 1500.0)
    home_edge = 50
    for g in sorted(games, key=lambda x: x['date']):
        if g['state'] != 'post':
            continue
        h, a = g['home_id'], g['away_id']
        delta = ratings[h] + home_edge - ratings[a]
        p = 1 / (1 + 10 ** (-delta / 400))
        hs, aw = g['home_score'], g['away_score']
        result = 1 if hs > aw else (0 if hs < aw else .5)
        margin_factor = min(2.3, 1 + .18 * max(0, abs(hs - aw) - 1))
        k = 22 if 'NFL' in g['league'] else 18
        change = k * margin_factor * (result - p)
        ratings[h] += change
        ratings[a] -= change
    return ratings


def predict(game, ratings):
    diff = ratings.get(game['home_id'], 1500) + 50 - ratings.get(game['away_id'], 1500)
    base = 1 / (1 + 10 ** (-diff / 400))
    if game['league'].startswith('Soccer'):
        # Heuristic 3-way baseline: NOT calibrated. Outcomes sum exactly to 1.
        draw = .26 * (1 - .45 * abs(2 * base - 1))
        return {'home': round(base * (1 - draw), 4), 'draw': round(draw, 4),
                'away': round((1 - base) * (1 - draw), 4), 'method': 'Elo + heuristic draw prior (uncalibrated)'}
    return {'home': round(base, 4), 'draw': 0.0, 'away': round(1 - base, 4),
            'method': 'Elo baseline (uncalibrated)'}


def calibration_metrics(records):
    # Forecast MUST be timestamped before its event start to be eligible.
    scored = [r for r in records if r.get('actual') in ('home', 'away', 'draw')
              and r.get('forecast_created') and r.get('date')
              and r['forecast_created'] < r['date']]
    if not scored:
        return None
    brier = sum(sum((r['probabilities'][out] - (1 if r['actual'] == out else 0)) ** 2
                        for out in ('home', 'draw', 'away')) for r in scored) / len(scored)
    top = sum(max(r['probabilities'], key=r['probabilities'].get) == r['actual'] for r in scored) / len(scored)
    return {'games': len(scored), 'brier': round(brier, 4), 'top_class_accuracy': round(top, 4)}


def final_outcome(g):
    if g['state'] != 'post':
        return None
    return 'home' if g['home_score'] > g['away_score'] else ('away' if g['home_score'] < g['away_score'] else 'draw')


def player_observations(league, game, max_games=5):
    """Extract available per-game numeric boxscore stats; no fabricated projections."""
    sport, code = LEAGUES[league]
    try:
        report = fetch_json(f'{BASE}/{sport}/{code}/summary', {'event': game['api_id']})
        teams = report.get('boxscore', {}).get('players', [])
        result = []
        for team in teams:
            for group in team.get('statistics', []):
                labels = group.get('labels', [])
                category = group.get('name', 'stat')
                for athlete in group.get('athletes', []):
                    who = athlete.get('athlete', {})
                    values = athlete.get('stats', [])
                    for label, val in zip(labels, values):
                        try:
                            # skip compound entries (e.g. 2-4), percentages, and clock strings
                            numeric = float(val)
                            if math.isfinite(numeric) and numeric >= 0:
                                result.append({'player': who.get('displayName', '?'), 'player_id':str(who.get('id', who.get('displayName','?'))),
                                               'category': category, 'stat': label, 'value': numeric, 'date': game['date'],
                                               'position': ((who.get('position') or {}).get('abbreviation', '') if isinstance(who.get('position'), dict) else str(who.get('position') or '')) or ((athlete.get('position') or {}).get('abbreviation', '') if isinstance(athlete.get('position'), dict) else str(athlete.get('position') or '')),
                                               'team': team.get('team', {}).get('displayName', '')})
                        except (ValueError, TypeError):
                            pass
        return result
    except (requests.RequestException, ValueError, KeyError):
        return []


def rolling_player_projections(games, league, limit_games=8):
    historical = [g for g in games if g['state'] == 'post'][-limit_games:]
    by_key = defaultdict(list)
    for g in historical:
        for entry in player_observations(league, g):
            by_key[(entry['player_id'], entry['player'], entry['category'], entry['stat'], entry.get('position', ''), entry.get('team', ''))].append(entry['value'])
    output = []
    for (_, name, category, stat, position, team), values in by_key.items():
        # Keep one-game samples, but always display their sample size.
        avg = statistics.mean(values)
        output.append({'Player':name, 'Team':team, 'Position':position, 'Category':category, 'Stat':stat, 'Recent average':round(avg, 2),
                       'Sample games':len(values), 'Observed min':min(values), 'Observed max':max(values)})
    return sorted(output, key=lambda r: (-r['Sample games'], r['Player'], r['Stat']))
