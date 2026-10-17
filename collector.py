"""Run on a schedule to save genuine pregame model forecasts and final outcomes."""
import datetime as dt
import json
from pathlib import Path
from engine import LEAGUES, fit_ratings, load_games, predict, final_outcome

PATH = Path(__file__).parent / 'data' / 'history.json'

def run():
    existing = json.loads(PATH.read_text()) if PATH.exists() else []
    by_id = {r['id']: r for r in existing}
    now = dt.datetime.now(dt.timezone.utc)
    for league in LEAGUES:
        games, errors = load_games(league, before=12, after=7, today=now.date())
        print(league, 'games', len(games), 'date errors', len(errors))
        past = [g for g in games if g['state'] == 'post' and g['date'] < now.isoformat()]
        ratings = fit_ratings(past)
        for g in games:
            if g['id'] in by_id:
                prior = by_id[g['id']]
                if prior.get('actual') is None and g['state'] == 'post':
                    prior['actual'] = final_outcome(g)
                    prior['final_score'] = f'{g["away_score"]}-{g["home_score"]}'
                continue
            if g['state'] != 'pre' or g['date'] <= now.isoformat():
                continue
            by_id[g['id']] = {**g, 'forecast_created': now.isoformat(),
                              'probabilities': predict(g, ratings), 'actual': None}
    PATH.parent.mkdir(parents=True, exist_ok=True)
    PATH.write_text(json.dumps(sorted(by_id.values(), key=lambda r:r['date']), indent=2) + '\n')
    print('saved', len(by_id), 'forecast records')

if __name__ == '__main__':
    run()
