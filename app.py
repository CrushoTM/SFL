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
st.markdown("""
<style>
.stApp {background:#0b1220;color:#e5eefb;}
.block-container {padding-top:2.5rem;max-width:1400px;}
[data-testid="stSidebar"] {background:#101c30;}
div[data-testid="stMetric"] {background:#15233a;border:1px solid #263956;border-radius:15px;padding:15px 18px;}
div[data-testid="stMetricLabel"] {color:#9cb0cc;}
.stTabs [data-baseweb="tab-list"] {gap:12px;border-bottom:1px solid #263956;}
.stTabs [data-baseweb="tab"] {padding:12px 20px;background:#122037;border-radius:9px 9px 0 0;}
div[data-testid="stDataFrame"] {border-radius:12px;overflow:hidden;}
.hero {border:1px solid #2a4162;background:linear-gradient(115deg,#172a47,#102035);
border-radius:22px;padding:28px 32px;margin:2px 0 20px;}
.hero h1 {font-size:2.4rem;letter-spacing:-1px;margin:0;color:#f7fbff;}
.hero p {color:#a8bdd7;margin:10px 0 0;}
</style>
""", unsafe_allow_html=True)
st.markdown('<div class="hero"><h1>Sports Forecast Lab</h1><p>MLB · NFL · Soccer | Independent sports research dashboard</p></div>', unsafe_allow_html=True)
st.caption('Public game feeds · Automatic page refresh every five minutes · Experimental, uncalibrated forecasts')
st.warning('Forecast probabilities are experimental, not validated. Player numbers below are historical averages, NOT predictions. Missing lineups and limited game samples can cause substantial errors.')
league = st.sidebar.selectbox('Sport / league', list(LEAGUES))
st.sidebar.write('Refreshes every 5 minutes while open. Scheduled GitHub workflow snapshots are separate.')
if st.sidebar.button('Refresh now'):
    st.cache_data.clear()
    st.rerun()

@st.cache_data(ttl=300, show_spinner=False)
def get_games(league):
    return load_games(league, before=45 if league == 'NFL' else 25, after=7)

@st.cache_data(ttl=3600, show_spinner=False)
def get_players(league, event_ids):
    # Capture past-event IDs in cache key so updates invalidate the cache.
    games, _ = get_games(league)
    return rolling_player_projections(games, league, limit_games=30 if league == 'NFL' else 20)

def show_history(frame, chart_key):
    """A small comparable table and chart for one specific historical stat."""
    if frame.empty:
        st.caption('Not available in the recent box-score sample.')
        return
    frame = frame.sort_values('Recent average', ascending=False).head(30)
    st.dataframe(frame[['Player', 'Team', 'Position', 'Recent average', 'Sample games', 'Observed min', 'Observed max']],
                 hide_index=True, use_container_width=True)
    st.bar_chart(frame.head(12).set_index('Player')['Recent average'])
    st.download_button('Export CSV', frame.drop(columns=['Stat upper', 'Category lower'], errors='ignore').to_csv(index=False),
                       file_name='observations_' + str(abs(hash(chart_key))) + '.csv',
                       mime='text/csv', key='csv_' + str(abs(hash(chart_key))))

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

# Retrieve recent observed player data automatically once per selected league.
# Streamlit tabs share cached records so changing tabs makes no extra requests.
with st.spinner('Automatically loading player history (initial load may take a moment)…'):
    records = get_players(league, tuple(g['id'] for g in finished[-(30 if league == 'NFL' else 20):]))

t1, t2, t3, t4, t5 = st.tabs(['🏟 Matchups', '📡 Live & Results', '⚾ / 🏈 Player stats', '🏈 Touchdown history', '📈 Accuracy'])

with t1:
    st.subheader('Upcoming matchups')
    st.caption('Elo estimates represent an uncalibrated model baseline; they are not reliability or confidence guarantees.')
    if not upcoming:
        st.info('No upcoming fixtures in the next seven days. Try another sport or check again later.')
    for g in upcoming[:30]:
        p = predict(g, ratings)
        with st.container(border=True):
            left, mid, right = st.columns([2, 1, 2])
            left.markdown(f"**{g['away']}**")
            mid.markdown('### vs')
            right.markdown(f"**{g['home']}**")
            st.caption(f"Kickoff (UTC): {g['date'][:16].replace('T', ' ')} · {p['method']}")
            a_col, h_col = st.columns(2)
            a_col.metric('Away model probability', f"{p['away'] * 100:.1f}%")
            h_col.metric('Home model probability', f"{p['home'] * 100:.1f}%")
            if league.startswith('Soccer'):
                st.caption(f"Draw model probability: {p['draw'] * 100:.1f}%")
            st.progress(min(1.0, max(0.0, p['home'])))
    st.info('Projected exact scores are not supplied by the current Elo-only engine. The historical score trends on this page are descriptive; a separate validated scoring model would be needed to make defensible score forecasts.')

with t2:
    st.subheader('Live scores and recent results')
    chosen = live + list(reversed(finished))[:45]
    if not chosen:
        st.info('No live or recently completed games are available.')
    else:
        rows = [{'Date (UTC)': g['date'][:16].replace('T', ' '), 'Away': g['away'],
                 'Away score': g['away_score'], 'Home': g['home'],
                 'Home score': g['home_score'], 'Status': g['status']} for g in chosen]
        st.dataframe(pd.DataFrame(rows), hide_index=True, use_container_width=True)

with t3:
    st.subheader('Player performance explorer')
    st.caption('Automatically loaded historical box-score averages (30 NFL / 20 other recent league games). Cached up to one hour; not player projections.')
    if records:
        frame = pd.DataFrame(records)
        frame['Stat upper'] = frame['Stat'].astype(str).str.upper().str.strip()
        frame['Position'] = frame['Position'].fillna('').astype(str).str.upper().str.strip()
        frame['Category lower'] = frame['Category'].astype(str).str.lower()
        search = st.text_input('Search player', key=f'search_{league}')
        if search:
            frame = frame[frame['Player'].str.contains(search, case=False, regex=False)]
        if league == 'MLB':
            categories = [('Hits', ['H']), ('Runs', ['R']), ('RBI', ['RBI']), ('Home runs', ['HR'])]
            for label, codes in categories:
                st.markdown('#### ' + label + ' — observed averages')
                selection = frame[frame['Stat upper'].isin(codes) & frame['Category lower'].str.contains('bat', na=False)]
                show_history(selection, f'mlb_{label}')
        elif league == 'NFL':
            for title, position, section, codes in [
                ('Quarterbacks · passing', ['QB', 'Q'], 'pass', ['YDS', 'PASS YDS']),
                ('Wide receivers · receiving', ['WR'], 'receiv', ['YDS', 'REC YDS']),
                ('Tight ends · receiving', ['TE'], 'receiv', ['YDS', 'REC YDS']),
                ('Running backs · rushing', ['RB', 'HB', 'FB'], 'rush', ['YDS', 'RUSH YDS'])]:
                st.markdown('#### ' + title + ' — observed yards')
                selection = frame[frame['Position'].isin(position) &
                                  frame['Category lower'].str.contains(section, na=False) &
                                  frame['Stat upper'].isin(codes)]
                show_history(selection, f'nfl_{title}')
            st.markdown('#### Other NFL player observations')
            st.caption('If your data provider omits a position or uses a different stat label, those entries remain visible below.')
            st.dataframe(frame[['Player', 'Team', 'Position', 'Category', 'Stat', 'Recent average', 'Sample games']].sort_values('Sample games', ascending=False).head(150), hide_index=True, use_container_width=True)
        else:
            st.markdown('#### Soccer · observed player statistics')
            stat_filter = st.selectbox('Statistic', sorted(frame['Stat'].unique()), key='soccer_stats')
            show_history(frame[frame['Stat'] == stat_filter], 'soccer')
    else:
        st.info('The public feed did not return enough box-score history. Try another league or check back later.')
    else:
        st.info('Player data is currently unavailable from the public feed. Please retry later.')
with t4:
    st.subheader('Touchdown performance history')
    if league != 'NFL':
        st.info('Choose NFL in the left sidebar to view historical touchdown statistics.')
    else:
        frame = pd.DataFrame(records)
        if frame.empty:
            st.info('No player records available.')
        else:
            frame['Category lower'] = frame['Category'].astype(str).str.lower()
            frame['Stat upper'] = frame['Stat'].astype(str).str.upper().str.strip()
            for label, section in [('Passing touchdowns (historical)', 'pass'),
                                   ('Rushing touchdowns (historical)', 'rush'),
                                   ('Receiving touchdowns (historical)', 'receiv')]:
                st.markdown('#### ' + label)
                subset = frame[(frame['Stat upper'].isin(['TD', 'TDS'])) &
                               frame['Category lower'].str.contains(section, na=False)]
                show_history(subset, label)
            st.caption('These are averages of recorded touchdowns. They do not estimate the chance of scoring one or two touchdowns in a future game.')
with t5:
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
