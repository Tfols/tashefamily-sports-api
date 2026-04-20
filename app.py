import os
import time
from datetime import datetime

import pytz
import requests
from flask import Flask, jsonify

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


if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port)
