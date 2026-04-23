import os
import time
from datetime import datetime, date, timedelta

import pytz
import recurring_ical_events
import requests
from flask import Flask, jsonify, send_from_directory
from icalendar import Calendar as iCal

app = Flask(__name__)

TEAMS = {
    'phillies':   {'sport': 'baseball', 'league': 'mlb',              'id': '22'},
    'eagles':     {'sport': 'football', 'league': 'nfl',              'id': '21'},
    'yankees':    {'sport': 'baseball', 'league': 'mlb',              'id': '10'},
    'nationals':  {'sport': 'baseball', 'league': 'mlb',              'id': '20'},
    'commanders': {'sport': 'football', 'league': 'nfl',              'id': '28'},
    'pitt':       {'sport': 'football', 'league': 'college-football', 'id': '221'},
}

_cache = {}
ET = pytz.timezone('America/New_York')


def espn_get(sport, league, path, ttl=120):
    url = f'https://site.api.espn.com/apis/site/v2/sports/{sport}/{league}/{path}'
    now = time.time()
    if url in _cache and now - _cache[url]['ts'] < ttl:
        return _cache[url]['data']
    try:
        r = requests.get(url, timeout=8, headers={'User-Agent': 'Mozilla/5.0'})
        r.raise_for_status()
        data = r.json()
        _cache[url] = {'data': data, 'ts': now}
        return data
    except Exception:
        return _cache.get(url, {}).get('data')


def parse_score(raw):
    if raw is None:
        return '0'
    if isinstance(raw, dict):
        return str(raw.get('displayValue', raw.get('value', '0')))
    return str(raw)


def fmt_date(date_str, include_time=False):
    try:
        dt = datetime.fromisoformat(date_str.replace('Z', '+00:00')).astimezone(ET)
        if include_time:
            t = dt.strftime('%I:%M%p').lstrip('0').lower()
            return dt.strftime('%-m/%-d ') + t
        return dt.strftime('%-m/%-d')
    except Exception:
        return '?'


def live_game(sport, league, team_id):
    data = espn_get(sport, league, 'scoreboard', ttl=60)
    if not data:
        return None

    for event in data.get('events', []):
        comp = event.get('competitions', [{}])[0]
        competitors = comp.get('competitors', [])
        if not any(c.get('team', {}).get('id') == team_id for c in competitors):
            continue
        if comp.get('status', {}).get('type', {}).get('state') != 'in':
            continue

        us = next(c for c in competitors if c.get('team', {}).get('id') == team_id)
        them = next(c for c in competitors if c.get('team', {}).get('id') != team_id)
        ha = 'vs' if us.get('homeAway') == 'home' else '@'
        opp = them.get('team', {}).get('abbreviation', '?')
        our_score = parse_score(us.get('score'))
        opp_score = parse_score(them.get('score'))
        detail = comp.get('status', {}).get('type', {}).get('detail', '')

        return {
            'line1': f'🔴 {ha} {opp}  {our_score}-{opp_score}  {detail}',
            'line2': '—',
        }
    return None


def schedule_info(sport, league, team_id):
    data = espn_get(sport, league, f'teams/{team_id}/schedule', ttl=300)
    if not data:
        return {'line1': 'No data', 'line2': '—'}

    completed, upcoming = [], []
    for event in data.get('events', []):
        comp = event.get('competitions', [{}])[0]
        state = comp.get('status', {}).get('type', {}).get('state', '')
        date = event.get('date', '')
        competitors = comp.get('competitors', [])
        if state == 'post':
            completed.append((date, competitors))
        elif state == 'pre':
            upcoming.append((date, competitors))

    completed.sort(key=lambda x: x[0], reverse=True)
    upcoming.sort(key=lambda x: x[0])

    line1 = 'No recent games'
    if completed:
        date, competitors = completed[0]
        us = next((c for c in competitors if c.get('team', {}).get('id') == team_id), {})
        them = next((c for c in competitors if c.get('team', {}).get('id') != team_id), {})
        ha = 'vs' if us.get('homeAway') == 'home' else '@'
        opp = them.get('team', {}).get('abbreviation', '?')
        wl = 'W' if us.get('winner') else 'L'
        our_score = parse_score(us.get('score'))
        opp_score = parse_score(them.get('score'))
        line1 = f'{wl} {our_score}-{opp_score} {ha} {opp} · {fmt_date(date)}'

    line2 = 'No upcoming games'
    if upcoming:
        date, competitors = upcoming[0]
        us = next((c for c in competitors if c.get('team', {}).get('id') == team_id), {})
        them = next((c for c in competitors if c.get('team', {}).get('id') != team_id), {})
        ha = 'vs' if us.get('homeAway') == 'home' else '@'
        opp = them.get('team', {}).get('abbreviation', '?')
        line2 = f'{ha} {opp} · {fmt_date(date, include_time=True)}'

    return {'line1': line1, 'line2': line2}


STOCKS_API = 'https://tashefamily-stocks-api-production.up.railway.app'
SYMBOLS = ['SPY', 'QQQ', 'DIA', 'BAH', 'RKLB', 'OCO.V', 'RGTI', 'AVTI', 'LUNR', 'IONQ', 'NVDA']
_stock_cache = {}


def fetch_quote(symbol, ttl=900):
    now = time.time()
    if symbol in _stock_cache and now - _stock_cache[symbol]['ts'] < ttl:
        return _stock_cache[symbol]['data']
    try:
        r = requests.get(f'{STOCKS_API}/quote/{symbol}', timeout=8)
        r.raise_for_status()
        data = r.json()
        _stock_cache[symbol] = {'data': data, 'ts': now}
        return data
    except Exception:
        return _stock_cache.get(symbol, {}).get('data')


def fmt_quote(data):
    if not data:
        return '—'
    price = data.get('price', 0)
    change = data.get('change', 0)
    arrow = '▲' if change >= 0 else '▼'
    return f'{price:.2f}  {arrow}{abs(change):.2f}'


@app.route('/quotes/all')
def get_all_quotes():
    return jsonify({s: fmt_quote(fetch_quote(s)) for s in SYMBOLS})


TEAM_LABELS = {
    'phillies':   'Phillies',
    'eagles':     'Eagles',
    'yankees':    'Yankees',
    'nationals':  'Nats',
    'commanders': 'Commanders',
    'pitt':       'Pitt',
}


def combined_line(d):
    line1, line2 = d.get('line1', ''), d.get('line2', '')
    if line2 in ('—', 'No upcoming games', 'No recent games', ''):
        return line1
    return f'{line1}  ·  {line2}'


@app.route('/sports/all')
def get_all_teams():
    result = {}
    for slug, info in TEAMS.items():
        d = live_game(info['sport'], info['league'], info['id']) or \
            schedule_info(info['sport'], info['league'], info['id'])
        result[slug] = combined_line(d)
    return jsonify(result)


@app.route('/sports/<team_slug>')
def get_team(team_slug):
    team = TEAMS.get(team_slug.lower())
    if not team:
        return jsonify({'error': 'Unknown team'}), 404
    sport, league, team_id = team['sport'], team['league'], team['id']
    result = live_game(sport, league, team_id) or schedule_info(sport, league, team_id)
    return jsonify(result)


@app.route('/health')
def health():
    return jsonify({'status': 'ok'})


@app.route('/debug-env')
def debug_env():
    """Shows which expected env vars are present (not their values)."""
    keys = ['OPENWEATHERMAP_API_KEY', 'GOOGLE_ICAL_URL', 'PORT']
    return jsonify({k: bool(os.environ.get(k)) for k in keys})


# ── Dashboard HTML ────────────────────────────────────────────────
@app.route('/')
def dashboard():
    return send_from_directory('static', 'index.html')


# ── Calendar proxy ────────────────────────────────────────────────
_ical_cache = {}

@app.route('/ical')
def get_calendar():
    ical_url = os.environ.get('GOOGLE_ICAL_URL', '')
    if not ical_url:
        return jsonify([])
    now = time.time()
    if 'data' in _ical_cache and now - _ical_cache.get('ts', 0) < 300:
        return jsonify(_ical_cache['data'])
    try:
        r = requests.get(ical_url, timeout=10)
        r.raise_for_status()
        cal = iCal.from_ical(r.content)
        today = datetime.now(ET).date()
        cutoff = today + timedelta(days=60)
        # Use recurring_ical_events to expand RRULE recurrences so future
        # instances of recurring series (swim lessons, etc.) are included.
        start_dt = datetime(today.year, today.month, today.day, tzinfo=ET)
        end_dt   = datetime(cutoff.year, cutoff.month, cutoff.day, 23, 59, 59, tzinfo=ET)
        expanded = recurring_ical_events.of(cal).between(start_dt, end_dt)
        events = []
        for component in expanded:
            dtstart = component.get('DTSTART')
            if not dtstart:
                continue
            dt = dtstart.dt
            if isinstance(dt, datetime):
                edate = dt.astimezone(ET).date()
                etime = dt.astimezone(ET).strftime('%I:%M %p').lstrip('0')
            else:
                edate = dt
                etime = 'All day'
            events.append({
                'title': str(component.get('SUMMARY', 'Untitled')),
                'date':  edate.isoformat(),
                'time':  etime,
            })
        events.sort(key=lambda e: e['date'])
        result = events[:20]
        _ical_cache['data'] = result
        _ical_cache['ts']   = now
        return jsonify(result)
    except Exception as e:
        return jsonify(_ical_cache.get('data') or {'error': str(e)})


# ── Weather proxy ─────────────────────────────────────────────────
_wx_cache = {}

@app.route('/weather')
def get_weather():
    api_key = os.environ.get('OPENWEATHERMAP_API_KEY', '')
    if not api_key:
        return jsonify({})
    now = time.time()
    if 'data' in _wx_cache and now - _wx_cache.get('ts', 0) < 600:
        return jsonify(_wx_cache['data'])
    try:
        r = requests.get(
            'https://api.openweathermap.org/data/2.5/weather',
            params={'lat': 38.8048, 'lon': -77.0469, 'appid': api_key, 'units': 'imperial'},
            timeout=8,
        )
        r.raise_for_status()
        d = r.json()
        result = {
            'temp':        round(d['main']['temp']),
            'feels_like':  round(d['main']['feels_like']),
            'description': d['weather'][0]['description'].title(),
            'humidity':    d['main']['humidity'],
            'wind':        round(d['wind']['speed']),
        }
        _wx_cache['data'] = result
        _wx_cache['ts']   = now
        return jsonify(result)
    except Exception as e:
        return jsonify(_wx_cache.get('data') or {'error': str(e)})


if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port)
