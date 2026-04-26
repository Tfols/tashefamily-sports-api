import calendar as cal_module
import os
import time
from datetime import datetime, date, timedelta

import feedparser
import pytz
import recurring_ical_events
import requests
from html.parser import HTMLParser
from flask import Flask, jsonify, send_from_directory, request, Response
from icalendar import Calendar as iCal

app = Flask(__name__)

TEAMS = {
    'phillies':      {'sport': 'baseball',    'league': 'mlb',                       'id': '22'},
    'eagles':        {'sport': 'football',    'league': 'nfl',                       'id': '21'},
    'yankees':       {'sport': 'baseball',    'league': 'mlb',                       'id': '10'},
    'nationals':     {'sport': 'baseball',    'league': 'mlb',                       'id': '20'},
    'commanders':    {'sport': 'football',    'league': 'nfl',                       'id': '28'},
    'pitt':          {'sport': 'football',    'league': 'college-football',          'id': '221'},
    'pitt-mbb':      {'sport': 'basketball',  'league': 'mens-college-basketball',   'id': '221'},
    'pitt-wbb':      {'sport': 'basketball',  'league': 'womens-college-basketball', 'id': '221'},
    'pitt-baseball': {'sport': 'baseball',    'league': 'college-baseball',          'id': '221'},
    'pitt-msoc':     {'sport': 'soccer',      'league': 'mens-college-soccer',       'id': '221'},
    'pitt-wsoc':     {'sport': 'soccer',      'league': 'womens-college-soccer',     'id': '221'},
    'pitt-wvb':      {'sport': 'volleyball',  'league': 'womens-college-volleyball', 'id': '221'},
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
        # College sports: silently hide the row — ESPN API may not cover this sport
        # Pro sports: surface 'No data' so we know there's an issue
        return None if 'college' in league else {'line1': 'No data', 'line2': '—'}

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

    # Off-season detection applies only to college sports.
    # Professional leagues (NFL, MLB) always show their last result even in offseason.
    # college-football uses a 180-day window (season ends Nov-Jan, want to show through May).
    # All other college sports use 45 days.
    if 'college' in league and not upcoming:
        if not completed:
            return None
        try:
            last_dt = datetime.fromisoformat(completed[0][0].replace('Z', '+00:00'))
            days_ago = (datetime.now(pytz.utc) - last_dt.astimezone(pytz.utc)).days
            threshold = 180 if league == 'college-football' else 45
            if days_ago > threshold:
                return None
        except Exception:
            pass  # date parse failure → fall through and show what we have

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
    result = {s: fmt_quote(fetch_quote(s)) for s in SYMBOLS}
    ts_values = [_stock_cache[s]['ts'] for s in SYMBOLS if s in _stock_cache]
    if ts_values:
        result['fetched_at'] = int(min(ts_values))
    return jsonify(result)


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
        try:
            d = live_game(info['sport'], info['league'], info['id']) or \
                schedule_info(info['sport'], info['league'], info['id'])
            if d is not None:
                result[slug] = combined_line(d)
        except Exception:
            pass  # one team failing should never blank the whole response
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


@app.route('/links')
def links():
    return send_from_directory('static', 'links.html')


# ── Favicon proxy ─────────────────────────────────────────────────
_favicon_cache = {}
FAVICON_TTL = 3600   # 1 hour
FAVICON_VER = 2      # bump to invalidate all cached entries on redeploy
_HDR = {'User-Agent': 'Mozilla/5.0'}


class _FaviconParser(HTMLParser):
    def __init__(self):
        super().__init__()
        self.candidates = []

    def handle_starttag(self, tag, attrs):
        if tag != 'link':
            return
        d = dict(attrs)
        rel = d.get('rel', '').lower()
        href = d.get('href', '')
        if not href or 'icon' not in rel:
            return
        # prefer explicit "icon" over "apple-touch-icon" etc.
        if rel in ('icon', 'shortcut icon'):
            self.candidates.insert(0, href)
        else:
            self.candidates.append(href)


def _resolve_href(base, href):
    if href.startswith('http'):
        return href
    if href.startswith('//'):
        return 'https:' + href
    return base + (href if href.startswith('/') else '/' + href)


_IMAGE_MAGIC = (
    b'\x00\x00\x01\x00',  # ICO
    b'\x89PNG',            # PNG
    b'GIF87a', b'GIF89a', # GIF
    b'\xff\xd8\xff',       # JPEG
    b'RIFF',               # WEBP (check bytes 8-12 separately)
    b'<svg', b'<?xml',    # SVG
)


def _is_image(data, ct):
    ct = ct.lower().split(';')[0].strip()
    if any(k in ct for k in ('html', 'javascript', 'json', 'text/plain')):
        return False
    if 'image' in ct:
        return True
    return any(data.startswith(m) for m in _IMAGE_MAGIC)


def _fetch_image(url):
    r = requests.get(url, timeout=6, headers=_HDR, allow_redirects=True)
    ct = r.headers.get('content-type', '')
    if r.ok and r.content and len(r.content) > 64 and _is_image(r.content, ct):
        return r.content, ct if 'image' in ct.lower() else 'image/x-icon'
    return None, None


@app.route('/favicon')
def proxy_favicon():
    domain = request.args.get('domain', '').strip()
    if not domain.endswith('.tashefamily.com') and not domain.endswith('.up.railway.app'):
        return '', 403

    now = time.time()
    cached = _favicon_cache.get(domain)
    if cached and cached.get('ver') == FAVICON_VER and now - cached['ts'] < FAVICON_TTL:
        if cached.get('empty'):
            return '', 404
        return Response(cached['data'], content_type=cached['ct'])

    base = f'https://{domain}'

    # Pass 1: try common paths directly (fast, no HTML fetch needed)
    for path in ('/favicon.ico', '/favicon.png', '/favicon.svg'):
        try:
            data, ct = _fetch_image(base + path)
            if data:
                _favicon_cache[domain] = {'data': data, 'ct': ct, 'ts': now, 'ver': FAVICON_VER}
                return Response(data, content_type=ct)
        except Exception:
            pass

    # Pass 2: parse the page HTML for <link rel="icon">
    try:
        r = requests.get(base, timeout=8, headers=_HDR, allow_redirects=True)
        if r.ok:
            parser = _FaviconParser()
            parser.feed(r.text)
            for href in parser.candidates:
                try:
                    data, ct = _fetch_image(_resolve_href(base, href))
                    if data:
                        _favicon_cache[domain] = {'data': data, 'ct': ct, 'ts': now, 'ver': FAVICON_VER}
                        return Response(data, content_type=ct)
                except Exception:
                    pass
    except Exception:
        pass

    _favicon_cache[domain] = {'empty': True, 'ts': now, 'ver': FAVICON_VER}
    return '', 404


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


# ── Forecast proxy ────────────────────────────────────────────────
_forecast_cache = {}

@app.route('/forecast')
def get_forecast():
    api_key = os.environ.get('OPENWEATHERMAP_API_KEY', '')
    if not api_key:
        return jsonify([])
    now = time.time()
    if 'data' in _forecast_cache and now - _forecast_cache.get('ts', 0) < 900:
        return jsonify(_forecast_cache['data'])
    try:
        r = requests.get(
            'https://api.openweathermap.org/data/2.5/forecast',
            params={'lat': 38.8048, 'lon': -77.0469, 'appid': api_key,
                    'units': 'imperial', 'cnt': 40},
            timeout=8,
        )
        r.raise_for_status()
        d = r.json()

        # Group 3-hour slots by local date, compute daily high/low
        from collections import defaultdict
        days = defaultdict(list)
        for item in d.get('list', []):
            dt_local = datetime.utcfromtimestamp(item['dt']).replace(
                tzinfo=pytz.utc).astimezone(ET)
            days[dt_local.strftime('%Y-%m-%d')].append(item)

        result = []
        today_str = datetime.now(ET).strftime('%Y-%m-%d')
        for date_key in sorted(days.keys())[:7]:
            items = days[date_key]
            highs = [i['main']['temp_max'] for i in items]
            lows  = [i['main']['temp_min'] for i in items]
            # prefer a midday slot for representative icon
            midday = min(items, key=lambda i: abs(
                datetime.utcfromtimestamp(i['dt']).replace(
                    tzinfo=pytz.utc).astimezone(ET).hour - 12))
            icon = midday['weather'][0]['icon']
            desc = midday['weather'][0]['description'].title()
            day_dt = datetime.strptime(date_key, '%Y-%m-%d')
            result.append({
                'day':   'TODAY' if date_key == today_str else day_dt.strftime('%a').upper(),
                'date':  date_key,
                'high':  round(max(highs)),
                'low':   round(min(lows)),
                'desc':  desc,
                'icon':  icon,
            })

        _forecast_cache['data'] = result
        _forecast_cache['ts']   = now
        return jsonify(result)
    except Exception as e:
        return jsonify(_forecast_cache.get('data') or {'error': str(e)})


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
            'icon':        d['weather'][0]['icon'],
        }
        _wx_cache['data'] = result
        _wx_cache['ts']   = now
        return jsonify(result)
    except Exception as e:
        return jsonify(_wx_cache.get('data') or {'error': str(e)})


# ── News / RSS proxy ──────────────────────────────────────────────
# URLs can be swapped here without touching any other code.
# AP News no longer publishes public RSS; using RSSHub as a proxy.
NEWS_FEEDS = {
    # when:1d restricts Google News search to the last 24 hours so we
    # always get today's articles rather than cached older results.
    'ap':      'https://news.google.com/rss/search?q=site:apnews.com+when:1d&hl=en-US&gl=US&ceid=US:en',
    'reuters': 'https://news.google.com/rss/search?q=site:reuters.com+when:1d&hl=en-US&gl=US&ceid=US:en',
    'ars':     'https://feeds.arstechnica.com/arstechnica/index',
}
NEWS_TTL   = 600   # 10 min
NEWS_LIMIT = 6     # headlines per source

_news_cache = {}


@app.route('/news/<source>')
def get_news(source):
    feed_url = NEWS_FEEDS.get(source)
    if not feed_url:
        return jsonify({'error': 'Unknown source'}), 404

    now = time.time()
    if source in _news_cache and now - _news_cache[source].get('ts', 0) < NEWS_TTL:
        return jsonify(_news_cache[source]['data'])

    try:
        # feedparser respects ETags / Last-Modified automatically
        feed = feedparser.parse(
            feed_url,
            request_headers={'User-Agent': 'Mozilla/5.0 (tashefamily-dashboard/1.0)'},
        )
        # Suffixes Google News appends to titles, e.g. "Headline - AP News"
        STRIP_SUFFIXES = [
            ' - AP News', ' - The Associated Press', ' - Associated Press',
            ' - Reuters', ' - Ars Technica',
        ]

        # Sort newest-first regardless of feed order, then take top N
        sorted_entries = sorted(
            feed.entries,
            key=lambda e: e.get('published_parsed') or (0,) * 9,
            reverse=True,
        )

        items = []
        for entry in sorted_entries[:NEWS_LIMIT]:
            pub = entry.get('published_parsed') or entry.get('updated_parsed')
            age_str = ''
            if pub:
                pub_epoch = cal_module.timegm(pub)   # UTC struct → epoch
                age_secs  = now - pub_epoch
                if age_secs < 3600:
                    age_str = f'{max(1, int(age_secs / 60))}m ago'
                elif age_secs < 86400:
                    age_str = f'{int(age_secs / 3600)}h ago'
                else:
                    age_str = f'{int(age_secs / 86400)}d ago'
            title = entry.get('title', '(no title)')
            for sfx in STRIP_SUFFIXES:
                if title.endswith(sfx):
                    title = title[:-len(sfx)].strip()
                    break
            items.append({
                'title': title,
                'link':  entry.get('link', ''),
                'age':   age_str,
            })
        if items:
            _news_cache[source] = {'data': items, 'ts': now}
        return jsonify(items or _news_cache.get(source, {}).get('data', []))
    except Exception:
        return jsonify(_news_cache.get(source, {}).get('data') or [])


if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port)
