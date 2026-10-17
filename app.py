"""Streamlit web UI for educational MLB/NFL/soccer forecasting."""
import datetime as dt
import json
from pathlib import Path
import pandas as pd
import streamlit as st
from streamlit_autorefresh import st_autorefresh
from engine import LEAGUES, load_games, fit_ratings, predict, calibration_metrics, rolling_player_projections

st.set_page_config(page_title='Sports Forecast Lab', page_icon='📊', layout='wide')
st_autorefresh(interval=300_000, key='refresh_interval')
st.title('📊 Sports Forecast Lab')
st.caption('Free research prototype • MLB · NFL · Soccer • educational projections, not wagering recommendations')
st.info('Forecasts use a basic Elo rating system. Probabilities are **not yet empirically calibrated**; player averages are descriptive, not verified predictive models. Live games do not receive in-game win probabilities.')
league = st.sidebar.selectbox('Sport / league', list(LEAGUES))
st.sidebar.write('Refreshes every 5 minutes while open. Scheduled GitHub workflow snapshots are separate.')
if st.sidebar.button('Refresh now'):
    st.cache_data.clear()
    st.rerun()

@st.cache_data(ttl=300, show_spinner=False)
def get_games(league):
    return load_games(league, before=25, after=7)

@st.cache_data(ttl=3600, show_spinner=False)
def get_players(league, event_ids):
    # Capture past-event IDs in cache key so updates invalidate the cache.
    games, _ = get_games(league)
    return rolling_player_projections(games, league, limit_games=8)

with st.spinner('Retrieving public scores and schedules…'):
    games, errors = get_games(league)
if errors:
    st.warning(f'{len(errors)} date requests failed. Data may be incomplete; see diagnostics below.')
if not games:
    st.error('No fixtures could be loaded. Check network/API availability and select a different league.')
    st.stop()

now = dt.datetime.now(dt.timezone.utc)
finished = [g for g in games if g['state'] == 'post' and g['date'] < now.isoformat()]
ratings = fit_ratings(finished)
upcoming = [g for g in games if g['state'] == 'pre' and g['date'] > now.isoformat()]
live = [g for g in games if g['state'] == 'in']
c1,c2,c3 = st.columns(3)
c1.metric('Upcoming fixtures', len(upcoming))
c2.metric('Live games', len(live))
c3.metric('Completed games in fetched window',len(finished))

t1,t2,t3,t4 = st.tabs(['Forecasts','Live / results','Player history','Accuracy & diagnostics'])
with t1:
    if not upcoming:
        st.info('No upcoming fixtures in the seven-day window; this is normal during breaks or off-season.')
    else:
        rows=[]
        for g in upcoming:
            p=predict(g, ratings)
            rows.append({'Kickoff (UTC)': g['date'][:16].replace('T',' '), 'Away': g['away'],
                         'Home':g['home'], 'Away %':round(100*p['away'],1),
                         'Draw %':round(100*p['draw'],1), 'Home %':round(100*p['home'],1),
                         'Method':p['method']})
        st.dataframe(pd.DataFrame(rows), hide_index=True, use_container_width=True)
        st.caption('Ratings use only completed games in the fetched lookback; low sample size and omitted context can create significant errors.')
with t2:
    chosen = live + list(reversed(finished))[:35]
    if not chosen: st.write('No currently live or recently completed games.')
    else:
        st.dataframe(pd.DataFrame([{'UTC date':g['date'][:16].replace('T',' '),
          'Game':g['away']+' @ '+g['home'], 'Score':str(g['away_score'])+' - '+str(g['home_score']),
          'Status':g['status']} for g in chosen]), hide_index=True, use_container_width=True)
with t3:
    st.subheader('Observed player statistics')
    st.caption('This module retrieves box scores for up to eight recent completed games per league. Recent averages are NOT predictive probabilities and may reflect very small samples.')
    if st.button('Load player history (additional API requests)'):
        with st.spinner('Reading box scores…'):
            records=get_players(league, tuple(g['id'] for g in finished[-8:]))
        if records:
            frame=pd.DataFrame(records)
            search=st.text_input('Filter player', '')
            if search: frame=frame[frame['Player'].str.contains(search, case=False, regex=False)]
            st.dataframe(frame, hide_index=True, use_container_width=True)
            st.download_button('Download player averages CSV',frame.to_csv(index=False),'player_observations.csv','text/csv')
        else:
            st.info('No box score statistics with at least two appearances were available from the provider for this sample.')
with t4:
    path=Path(__file__).parent/'data'/'history.json'
    history=json.loads(path.read_text()) if path.exists() else []
    eligible=[r for r in history if r.get('league')==league]
    metrics=calibration_metrics(eligible)
    if metrics:
        a,b,c=st.columns(3)
        a.metric('Scored forecasts',metrics['games'])
        b.metric('Brier score (lower better)',metrics['brier'])
        c.metric('Top class accuracy',f"{100*metrics['top_class_accuracy']:.1f}%")
        st.caption('Brier score is multiclass (sum of squared errors); forecast snapshots must precede the fixture start time.')
    else:
        st.info('No valid pregame forecast/result pairs yet. Accuracy tracking begins as scheduled snapshots accumulate and games finish.')
    if eligible:
        st.dataframe(pd.DataFrame([{'Match':r['away']+' @ '+r['home'], 'Forecast made':r['forecast_created'],
          'Home %':round(100*r['probabilities']['home'],1), 'Draw %':round(100*r['probabilities']['draw'],1),
          'Away %':round(100*r['probabilities']['away'],1), 'Actual':r.get('actual') or 'Pending'} for r in eligible[-100:]]),hide_index=True,use_container_width=True)
    with st.expander('Provider diagnostics'):
        st.write('Source: publicly accessible ESPN scoreboard and game-summary endpoints (unofficial; availability and terms can change).')
        for err in errors[:15]: st.code(err)
    st.caption('History file is persisted by the GitHub scheduled collector, not by in-browser refresh. Cloud deploy requires a public or private GitHub repository.')
