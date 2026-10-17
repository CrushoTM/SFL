from engine import predict, fit_ratings, calibration_metrics

def test_probabilities_sum_to_one():
    game={'home_id':'1','away_id':'2','league':'Soccer — EPL'}
    result=predict(game,{})
    assert abs(sum(result[k] for k in ('home','away','draw'))-1)<0.0002

def test_no_history_metrics():
    assert calibration_metrics([]) is None

def test_elo_ignores_future():
    game={'home_id':'1','away_id':'2','league':'MLB','date':'2026-10-01','state':'pre','home_score':9,'away_score':0}
    assert dict(fit_ratings([game]))=={}
