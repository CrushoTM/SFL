"""Streamlit web UI for educational MLB/NFL/soccer forecasting."""
import datetime as dt
import json
from pathlib import Path
import pandas as pd
import streamlit as st
from streamlit_autorefresh import st_autorefresh
from engine import LEAGUES, load_games, fit_ratings, predict, calibration_metrics, rolling_player_projections
from research import roster_snapshot, team_defense_history, quality_summary

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

@st.cache_data(ttl=3600, show_spinner=False)
def get_roster(league, team_id):
    return roster_snapshot(league, team_id)


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

t1, t2, t3, t4, t5, t6 = st.tabs(['🏟 Matchups', '📡 Live & Results', '⚾ / 🏈 Player stats', '🏈 Touchdown history', '📈 Accuracy', '🔎 Matchup research'])

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

with st.expander('Matchup context · recent defenses and data availability'):
    st.caption('Factual context from completed games in the loaded window; not a player projection.')
    if upcoming:
        context_rows = []
        for g in upcoming[:24]:
            home_allowed = [x['away_score'] for x in finished if x['home_id'] == g['home_id']] + [x['home_score'] for x in finished if x['away_id'] == g['home_id']]
            away_allowed = [x['away_score'] for x in finished if x['home_id'] == g['away_id']] + [x['home_score'] for x in finished if x['away_id'] == g['away_id']]
            context_rows.append({
                'Matchup': g['away'] + ' @ ' + g['home'],
                'Home defense · avg points conceded': round(sum(home_allowed)/len(home_allowed), 1) if home_allowed else None,
                'Away defense · avg points conceded': round(sum(away_allowed)/len(away_allowed), 1) if away_allowed else None,
                'Home defense sample': len(home_allowed),
                'Away defense sample': len(away_allowed)
            })
        st.dataframe(pd.DataFrame(context_rows), hide_index=True, use_container_width=True)
    st.caption('Injuries, trades, current depth charts and expected playing time are NOT verified by this data collector. Do not treat an unlisted player as healthy or currently rostered.')

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
            # ESPN often omits position metadata in event boxscores.
            # Group by verified stat category; do not hide missing-position athletes.
            groups = [
                ('Passing yards · quarterbacks and other passers', 'pass', ['YDS', 'PASS YDS']),
                ('Receiving yards · all receivers (WR / TE / RB)', 'receiv', ['YDS', 'REC YDS']),
                ('Rushing yards · running backs and other rushers', 'rush', ['YDS', 'RUSH YDS']),
            ]
            for title, section, codes in groups:
                st.markdown('#### ' + title)
                selection = frame[
                    frame['Category lower'].str.contains(section, na=False)
                    & frame['Stat upper'].isin(codes)
                ]
                show_history(selection, 'nfl_' + section)
            st.caption('Some players have no position in the public box score. These groups use the observed statistical category rather than guessing their roster position.')
            with st.expander('All observed NFL statistics and source labels'):
                st.dataframe(frame[['Player', 'Team', 'Position', 'Category', 'Stat', 'Recent average', 'Sample games']].sort_values('Sample games', ascending=False).head(200), hide_index=True, use_container_width=True)
        else:
            st.markdown('#### Soccer · observed player statistics')
            stat_filter = st.selectbox('Statistic', sorted(frame['Stat'].unique()), key='soccer_stats')
            show_history(frame[frame['Stat'] == stat_filter], 'soccer')
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
        scored = [r for r in eligible if r.get('actual') in ('home', 'away', 'draw')
                  and r.get('forecast_created', '') < r.get('date', '')]
        if scored:
            plotted = []
            for r in scored:
                outcome = max(('home', 'away', 'draw'), key=lambda k: r['probabilities'][k])
                plotted.append({'Forecast date': r['date'][:10],
                                'Highest class probability': 100 * r['probabilities'][outcome],
                                'Correct': int(outcome == r['actual'])})
            chart_frame = pd.DataFrame(plotted)
            st.subheader('Historical model performance')
            st.caption('This chart uses forecasts recorded BEFORE kickoff; in-sample accuracy alone does not establish calibration.')
            st.bar_chart(chart_frame.groupby('Forecast date', as_index=True)['Correct'].mean() * 100)
            st.caption('Daily share of highest-probability outcomes that occurred (%). Interpret cautiously when few games were scored.')
    if eligible:
        st.dataframe(pd.DataFrame([{'Match':r['away']+' @ '+r['home'], 'Forecast made':r['forecast_created'],
          'Home %':round(100*r['probabilities']['home'],1), 'Draw %':round(100*r['probabilities']['draw'],1),
          'Away %':round(100*r['probabilities']['away'],1), 'Actual':r.get('actual') or 'Pending'} for r in eligible[-100:]]),hide_index=True,use_container_width=True)
    with st.expander('Provider diagnostics'):
        st.write('Source: publicly accessible ESPN scoreboard and game-summary endpoints (unofficial; availability and terms can change).')
        for err in errors[:15]: st.code(err)
    st.caption('History file is persisted by the GitHub scheduled collector, not by in-browser refresh. Cloud deploy requires a public or private GitHub repository.')

with t6:
    st.subheader('Upcoming-match research')
    st.caption('Team rosters and descriptive defensive histories from public ESPN feeds. Not a player performance prediction.')
    if not upcoming:
        st.info('No upcoming fixture is available in this league and date range.')
    else:
        labels = [g['away'] + ' @ ' + g['home'] + ' · ' + g['date'][:10] for g in upcoming[:30]]
        selected = st.selectbox('Choose upcoming matchup', list(range(len(labels))),
                                format_func=lambda i: labels[i], key='research_' + league)
        match = upcoming[selected]
        home_defense = team_defense_history(finished, match['home_id'])
        away_defense = team_defense_history(finished, match['away_id'])
        st.markdown('#### Recent team and opponent context')
        h, a = st.columns(2)
        with h:
            st.markdown('**' + match['home'] + ' (home)**')
            st.metric('Points / goals conceded per game', home_defense['avg_allowed'] if home_defense['avg_allowed'] is not None else 'N/A')
            st.metric('Points / goals scored per game', home_defense['avg_scored'] if home_defense['avg_scored'] is not None else 'N/A')
            st.caption(str(home_defense['games']) + ' recent completed games')
        with a:
            st.markdown('**' + match['away'] + ' (away)**')
            st.metric('Points / goals conceded per game', away_defense['avg_allowed'] if away_defense['avg_allowed'] is not None else 'N/A')
            st.metric('Points / goals scored per game', away_defense['avg_scored'] if away_defense['avg_scored'] is not None else 'N/A')
            st.caption(str(away_defense['games']) + ' recent completed games')
        st.caption('These are team scoring averages, not passing/receiving/rushing defense rankings. Opponent strength and game pace are not adjusted.')
        with st.spinner('Checking team rosters for selected matchup…'):
            home_roster = get_roster(league, match['home_id'])
            away_roster = get_roster(league, match['away_id'])
        st.markdown('#### Current roster lookup')
        st.caption('Snapshot requested from the public provider. A player absent from the response is not proof they have been traded, released, or ruled out.')
        for side, snap in [(match['home'], home_roster), (match['away'], away_roster)]:
            with st.expander(side + ' — roster (' + str(len(snap['players'])) + ' listed)', expanded=False):
                if snap['verified']:
                    st.dataframe(pd.DataFrame(snap['players'])[['name', 'position', 'injury_status', 'injury_note']],
                                 hide_index=True, use_container_width=True)
                    st.caption('Source: ' + snap['source'] + ' · Fetched: ' + snap['retrieved_utc'][:19] + ' UTC')
                    notes = [p for p in snap['players'] if p['injury_status'] or p['injury_note']]
                    if notes:
                        st.warning(str(len(notes)) + ' roster entries include provider injury annotations. Not a complete injury report.')
                else:
                    st.warning(snap['error'] or 'Roster not available from this provider.')
        checks = quality_summary(records, home_roster, away_roster)
        st.markdown('#### Information quality')
        st.dataframe(pd.DataFrame([
            {'Data source': 'Both team rosters', 'Verified': checks['rosters_verified']},
            {'Data source': 'Recent team scoring', 'Verified': bool(home_defense['games'] and away_defense['games'])},
            {'Data source': 'Complete official injury reports', 'Verified': False},
            {'Data source': 'Recent trades and transactions', 'Verified': False},
            {'Data source': 'Projected snap counts / playing time', 'Verified': False},
        ]), hide_index=True, use_container_width=True)
        st.info('Full injury-report verification, transactions, confirmed starters, and defensive position-specific rankings require separately licensed or official feeds. Their absence is never treated as a clean bill of health.')
