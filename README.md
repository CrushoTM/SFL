# Sports Forecast Lab — free educational prototype

An executable Streamlit website showing publicly available MLB, NFL, and soccer schedules/results, separate league-based Elo forecast tables, player box-score averages, and an automatically maintained pregame forecast audit trail.

**Not a gambling tool.** The forecast numbers are experimental and **not calibrated**. They are unsuitable for staking decisions. The player module displays averages, not statistically validated predictions. No injury, confirmed lineup, odds, or real-time play-by-play model is included.

## 1. Run locally

Install Python 3.11 or newer. In this directory:

```bash
python -m pip install -r requirements.txt
streamlit run app.py
```

Your browser opens at `http://localhost:8501`. The page refreshes every 5 minutes while open; the public ESPN endpoints require internet access. An API outage can temporarily remove fixtures or leave incomplete data. Some leagues have no games in the seven-day window.

## 2. Deploy a free public website

1. Create a GitHub repository and upload **all files**, including `.github/workflows/collect.yml`.
2. Visit https://share.streamlit.io/ and choose **Create app**, connecting your repository.
3. Select the entrypoint `app.py` and deploy. You get a shareable `streamlit.app` address.
4. In your GitHub repo's **Actions** tab, enable Actions if prompted and run `Collect educational forecasts` once with **Run workflow**. Confirm that `data/history.json` was committed.
5. Keep the repository Actions workflow enabled. Its requested schedule is every 30 minutes. GitHub can delay or skip scheduled runs; actions may be disabled after prolonged inactivity, especially for public repos.

**Important free-tier limits:** Streamlit Community Cloud apps sleep after inactivity. The GitHub workflow operates independently even while the website sleeps, provided scheduled GitHub Actions continue running. It cannot guarantee uninterrupted, exact-time, 24/7 collection. The page refreshes its live data only while someone is viewing it. Some providers prohibit or rate-limit automated usage; check upstream conditions before scaling.

## How forecasts are computed

- One independent Elo rating table per sport/competition, updated from each completed match in a rolling 25-day window. Ratings start at 1500 and home advantage is assumed to be 50 Elo points. This is a basic demonstration, not a validated league model.
- Game probabilities derive from the Elo logistic formula; soccer additionally applies an **uncalibrated** heuristic draw percentage. Data gaps can bias ratings.
- Player history reads recent box-score categories and displays arithmetic averages for numeric observations with at least two appearances. No assumptions about lineup status, playing time, or opportunity adjustments.
- `collector.py` snapshots forecasts **before** game start; when a game finishes, it adds the result without overwriting pregame probabilities. The dashboard reports multiclass Brier score and top-class accuracy only after real forecasts have been scored. No historical backtest scores are fabricated.

## Sources & known limitations

Public, unofficial ESPN site API endpoints are used without an API key. These are not documented contractual APIs, and responses may change or become unavailable. NFL tie probabilities are not separately modeled, and the dashboard displays 0% for draws outside soccer. Soccer is split into EPL, LaLiga, UCL and MLS to avoid improperly combining rating pools. The 25-day rating lookback is particularly weak for NFL; long-term season data and league-specific calibration are high-priority improvements.

A production-quality next version should add season-to-season persistent Elo updates, time-ordered backtesting, dedicated models for each sport, calibrated outcomes, better handling of playoff/extra-time rules, starting-player verification, missing-data diagnostics, and an authorized licensed feed with reliable service guarantees.
