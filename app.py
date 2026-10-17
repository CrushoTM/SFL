"""A single-purpose NFL upcoming-game research dashboard."""
import datetime as dt
import json
import pandas as pd
import streamlit as st
from streamlit_autorefresh import st_autorefresh
from engine import load_games
from nfl_model import forecast, rolling_validation
from team_td_model import project_team_tds
from player_td_model import player_td_projection

st.set_page_config(page_title="NFL Forecast Lab", page_icon="🏈", layout="wide")
st_autorefresh(interval=900_000, key="nfl_refresh")

st.markdown("""
<style>
.stApp {background: #0a0f1b;color:#eaf1ff;}
.block-container {max-width:1160px;padding-top:3.5rem;}
[data-testid="stSidebar"] {background:#10192a;}
.hero {background:linear-gradient(105deg,#142541,#0f192c);
  border:1px solid #283b57;padding:27px 31px;border-radius:18px;margin-bottom:20px;}
.hero h1 {font-size:2.65rem;font-weight:760;letter-spacing:-1.25px;margin:0;color:#f4f8ff}
.hero p {color:#9caec9;margin:9px 0 0;font-size:1rem}
.game {font-size:1.32rem;font-weight:700;}
div[data-testid="stMetric"] {background:#121f32;border:1px solid #263950;
  padding:13px 16px;border-radius:12px;}
div[data-testid="stVerticalBlockBorderWrapper"] > div {border-radius:16px;}
div.stButton > button {border-radius:10px;}
.note {color:#a7b8d0;font-size:.88rem;}
</style>""", unsafe_allow_html=True)
st.markdown('<div class="hero"><h1>🏈 NFL Forecast Lab</h1><p>Upcoming NFL matchups · Offense versus defense · Research-model favorites</p></div>', unsafe_allow_html=True)

@st.cache_data(ttl=900, show_spinner=False)
def retrieve():
    # 48 days captures the current early-season NFL sample in October.
    # Public endpoints may be slow; cache all retrieved games for 15 minutes.
    return load_games("NFL", before=48, after=14)

st.sidebar.header("NFL research")
st.sidebar.caption("Upcoming games only. Refreshes every 15 minutes while this page is open.")
if st.sidebar.button("↻ Refresh data"):
    st.cache_data.clear()
    st.rerun()
st.sidebar.caption("Model version: offense/defense + Elo + recent form. Not calibrated.")

with st.spinner("Loading upcoming NFL games and team history…"):
    games, errors = retrieve()
if not games:
    st.error("Could not load NFL fixtures from the public provider. Try Refresh data later.")
    st.stop()

now = dt.datetime.now(dt.timezone.utc)
completed = [g for g in games if g["state"] == "post" and g["date"] < now.isoformat()]
upcoming = [g for g in games if g["state"] == "pre" and g["date"] > now.isoformat()]
upcoming.sort(key=lambda x: x["date"])

c1,c2,c3 = st.columns(3)
c1.metric("Upcoming NFL games", len(upcoming))
c2.metric("Completed games analyzed", len(completed))
c3.metric("Data coverage", "Partial" if errors else "Loaded")
st.caption("Source: public ESPN NFL schedule and results. Updated on request or every 15 minutes while open. Missing provider days: " + str(len(errors)))
st.info("Model win shares are experimental estimates, NOT calibrated confidence levels. Offense and defense are approximated by points scored/allowed. Injuries, confirmed starters, transactions and position-specific defensive ratings have not been verified and are NOT part of this model.")

game_tab, touchdown_tab, player_tab = st.tabs(["🏈 Upcoming games", "📈 Projected team TDs", "👤 Projected player TDs"])

with game_tab:
    if not upcoming:
        st.info("There are no upcoming games in the next 14 days returned by this feed. This can happen during breaks or provider outages.")
    else:
        forecasts = [(g, forecast(g, completed)) for g in upcoming]
        display = st.radio("Show matchups", ["All upcoming", "Next 7 days"], horizontal=True)
        if display == "Next 7 days":
            deadline = now + dt.timedelta(days=7)
            forecasts = [(g,p) for g,p in forecasts if dt.datetime.fromisoformat(g["date"].replace("Z","+00:00")) <= deadline]
        st.markdown("### Upcoming matchups")
        if not forecasts:
            st.caption("No upcoming fixtures in this date range.")
        for game, pred in forecasts:
            with st.container(border=True):
                kickoff = dt.datetime.fromisoformat(game["date"].replace("Z","+00:00"))
                st.caption(kickoff.strftime("%a %b %d · %I:%M %p UTC") + " · Pre-game")
                left, sep, right = st.columns([5, 1, 5], vertical_alignment="center")
                with left:
                    st.markdown("### " + game["away"])
                with sep:
                    st.markdown("**@**")
                with right:
                    st.markdown("### " + game["home"])
                st.markdown("**Model favorite: " + pred["winner"] + "**")
                home_col, away_col = st.columns(2)
                home_col.metric(game["home"] + " · experimental win share", f'{pred["home_probability"] * 100:.1f}%')
                away_col.metric(game["away"] + " · experimental win share", f'{pred["away_probability"] * 100:.1f}%')
                st.progress(pred["home_probability"], text="Home-team model share")
                if pred["sample_games_min"] < 3:
                    st.warning("Very small recent sample. Treat the model estimate as low-information.")
                with st.expander("Why does the model lean this way?"):
                    st.caption("Numbers below are points per game from completed games, smoothed toward 22.0 when samples are small.")
                    stats = pd.DataFrame([
                        {"Team": game["away"], "Games": pred["away"]["games"],
                         "Offense · pts/game": pred["away"]["offense_ppg"],
                         "Defense · pts allowed/game": pred["away"]["allowed_ppg"],
                         "Recent average point margin": pred["away"]["recent_margin"]},
                        {"Team": game["home"], "Games": pred["home"]["games"],
                         "Offense · pts/game": pred["home"]["offense_ppg"],
                         "Defense · pts allowed/game": pred["home"]["allowed_ppg"],
                         "Recent average point margin": pred["home"]["recent_margin"]},
                    ])
                    st.dataframe(stats, hide_index=True, use_container_width=True)
                    st.write("Model factors: offensive scoring versus opposing points allowed, past-results Elo, recent point margins, and fixed home-field adjustment.")
                    st.caption("Unavailable inputs: official injury status, trades, confirmed active starters, offensive/defensive efficiency per play, turnovers, opponent-adjusted efficiency. No assertions are made about their impact.")
    
    with st.expander("Model methodology and historical check"):
        st.write("Each team receives smoothed offense/defense ratings using completed NFL points scored and allowed. A transparent, fixed-weight model combines these with previous-game Elo, four-game form, and home advantage. These weights are heuristic, not learned from a validated training set.")
        validation = rolling_validation(completed)
        if validation:
            a,b,c = st.columns(3)
            a.metric("Historical checks", validation["games"])
            b.metric("Correct favorites", f'{100 * validation["winner_accuracy"]:.1f}%')
            c.metric("Brier score · lower is better", f'{validation["brier"]:.3f}')
            st.caption("Sequential retrospective check with 16 prior completed games minimum. It is NOT an independent holdout or proof of predictive validity.")
        else:
            st.caption("Insufficient completed games for the chronological check.")
        st.caption("Ties are excluded from the historical check; the binary model does not separately predict ties.")
    
with touchdown_tab:
    st.subheader("Upcoming-game touchdown projections")
    st.caption("Experimental TEAM offensive touchdown-equivalent estimates for scheduled games, not past player totals or touchdown-scorer betting picks.")
    st.warning("These are touchdown equivalents derived from expected team points, not verified projected touchdown counts. Field goals, defensive scores, injuries, trades and lineups are not modeled. The range is illustrative, NOT a confidence interval.")
    if not upcoming:
        st.info("There are no upcoming NFL games to project in the current schedule window.")
    else:
        for match in upcoming:
            result = project_team_tds(match, completed)
            with st.container(border=True):
                kickoff = dt.datetime.fromisoformat(match["date"].replace("Z", "+00:00"))
                st.caption(kickoff.strftime("%a %b %d · %I:%M %p UTC"))
                st.markdown("#### " + match["away"] + " @ " + match["home"])
                left, right = st.columns(2)
                for col, side, name, sample in [
                    (left, "away", match["away"], result["away_games"]),
                    (right, "home", match["home"], result["home_games"])
                ]:
                    with col:
                        st.metric(name + " · projected TD equivalents", f'{result[side]["expected"]:.2f}')
                        st.caption(f'Illustrative range: {result[side]["low"]:.2f}–{result[side]["high"]:.2f}')
                        st.caption(f'Estimated team points: {result[side]["points"]:.1f} · {sample} past team games')
                if min(result["away_games"], result["home_games"]) < 3:
                    st.info("Limited historical sample — low-information estimate.")
        with st.expander("How are projected team touchdowns calculated?"):
            st.write("The model blends each team's season-to-date points per game (55%) with the upcoming opponent's points allowed per game (45%). It converts the expected points to rough touchdown equivalents by dividing by seven.")
            st.write("This does NOT identify individual future scorers or calculate probabilities of one or two touchdowns. It is an exploratory scoring-strength indicator, not a validated touchdown forecast.")

@st.cache_data(ttl=3600, show_spinner=False)
def load_player_td_projections(match_json, completed_json):
    # Lazy per-matchup fetching; do not download entire league's box scores on page load.
    return player_td_projection(json.loads(match_json), json.loads(completed_json))

with player_tab:
    st.subheader("Upcoming player touchdown projections")
    st.caption("Experimental expected OFFENSIVE touchdown equivalents for the NEXT game, informed by team scoring, opponent points allowed and players' sampled rushing/receiving touchdown involvement. These are forward estimates, not past totals.")
    st.warning("Player availability and injuries are NOT confirmed. Roster presence does not mean active game-day status. Values are uncalibrated scoring allocations, not 1+ TD or 2+ TD likelihoods.")
    if not upcoming:
        st.info("No upcoming NFL matchup is available in the current schedule window.")
    else:
        labels = [g["away"] + " @ " + g["home"] + " · " + g["date"][:10] for g in upcoming]
        idx = st.selectbox("Upcoming matchup", list(range(len(labels))),
                           format_func=lambda i: labels[i], key="player_td_game")
        match = upcoming[idx]
        st.markdown("### " + match["away"] + " @ " + match["home"])
        with st.spinner("Checking recent player involvement and roster snapshots…"):
            result = load_player_td_projections(json.dumps(match, sort_keys=True),
                                                json.dumps(completed, sort_keys=True))
        for side in ("away", "home"):
            team = result[side]
            st.markdown("#### " + team["team"])
            st.caption(f'Team projected TD equivalents: {team["total_expected_tds"]:.2f} · '
                       f'{team["boxscore_games"]} historical games checked')
            if team["missing_games"]:
                st.warning(f'{team["missing_games"]} selected game(s) had no usable player stats for this team.')
            if not team["roster_verified"]:
                st.warning("Current roster could not be verified; listed players may have changed teams. "
                           + (team["roster_error"] or ""))
            if team["rows"]:
                frame = pd.DataFrame(team["rows"])
                st.dataframe(frame, hide_index=True, use_container_width=True,
                             column_config={"Projected TD equivalent": st.column_config.NumberColumn(
                                 "Projected TDs (experimental)", format="%.2f")})
            else:
                st.info("Insufficient verified player data to generate projections for this team. No names or figures were fabricated.")
        with st.expander("How are these player projections generated?"):
            st.write("For each team, a projected team TD-equivalent total is calculated from team offense and opposing defense. The model then allocates that expected total across sampled players using their previous rushing and receiving TD involvement with a small smoothing prior.")
            st.write("Passing touchdowns are NOT attributed to quarterbacks as scoring touchdowns. The model does not know snap shares, targets, route participation, official injuries, depth-chart changes or confirmed starters. Small samples and incomplete box scores can substantially distort the estimates.")
            st.caption("Not validated, not probabilities, and not betting recommendations.")
