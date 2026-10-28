"""Resolve pilot avatars from record uploaders; never infer ownership from names."""
import base64
import collections
import datetime as dt
import json
import os
from pathlib import Path
import re
import sys
import urllib.parse
import urllib.request

TARGETS = ['ZBosGaming', 'Kind1e']
ROOT = Path(__file__).resolve().parent

def video_id(url):
    p = urllib.parse.urlparse(str(url))
    host = (p.hostname or '').lower().removeprefix('www.')
    if host == 'youtu.be':
        value = p.path.strip('/').split('/')[0]
    elif host in ('youtube.com', 'm.youtube.com'):
        value = urllib.parse.parse_qs(p.query).get('v', [''])[0]
        if p.path.startswith(('/shorts/', '/embed/', '/live/')):
            value = p.path.split('/')[2]
    else:
        return None
    return value if re.fullmatch(r'[A-Za-z0-9_-]{11}', value) else None

def read_json(url):
    with urllib.request.urlopen(url, timeout=30) as response:
        return json.load(response)

def youtube(resource, ids, key):
    result = []
    for offset in range(0, len(ids), 50):
        query = urllib.parse.urlencode({'part': 'snippet', 'id': ','.join(ids[offset:offset+50]), 'key': key})
        try:
            result.extend(read_json('https://www.googleapis.com/youtube/v3/' + resource + '?' + query)['items'])
        except Exception:
            # Do not print exception URLs, which contain the secret key.
            raise RuntimeError('YouTube lookup failed; check API enablement, key restrictions, and quota.') from None
    return result

def build(catalog, lookup_videos, lookup_channels, now):
    links = {name: set() for name in TARGETS}
    for level in catalog:
        for name in TARGETS:
            raw = [r.get('link') for r in level.get('records', []) if str(r.get('user', '')).casefold() == name.casefold()]
            if str(level.get('verifier', '')).casefold() == name.casefold():
                raw.append(level.get('verification'))
            links[name].update(v for u in raw if (v := video_id(u)))
    videos = {v['id']: v['snippet']['channelId'] for v in lookup_videos(sorted(set().union(*links.values())))}
    channels = {c['id']: c['snippet'] for c in lookup_channels(sorted(set(videos.values())))}
    players, review = {}, {}
    for name, ids in links.items():
        counts = collections.Counter(videos[v] for v in ids if v in videos)
        candidates = [{'channelId': c, 'videoCount': n, 'title': channels.get(c, {}).get('title', '')} for c, n in counts.most_common()]
        # Multiple uploaders require human review. One surviving video is insufficient.
        if len(counts) != 1 or sum(counts.values()) < 2:
            review[name] = {'reason': 'mixed_channels' if len(counts) > 1 else 'insufficient_evidence', 'candidates': candidates}
            continue
        cid = next(iter(counts)); snippet = channels.get(cid, {})
        thumb = snippet.get('thumbnails', {})
        image = next((thumb[size]['url'] for size in ('high', 'medium', 'default') if size in thumb), '')
        if not image.startswith('https://'):
            review[name] = {'reason': 'missing_channel_picture', 'candidates': candidates}; continue
        players[name.casefold()] = {'imageUrl': image, 'channelId': cid, 'channelTitle': snippet.get('title', ''), 'matchedVideos': sum(counts.values()), 'checkedAt': now}
    return {'version': 1, 'updatedAt': now, 'players': players, 'review': review}

def embed_picture(url):
    host = (urllib.parse.urlparse(url).hostname or '').lower()
    if not (host.endswith('.ggpht.com') or host.endswith('.googleusercontent.com')):
        raise RuntimeError('Unexpected YouTube thumbnail host; image requires review.')
    with urllib.request.urlopen(url, timeout=30) as response:
        mime = response.headers.get_content_type()
        if mime not in ('image/png', 'image/jpeg', 'image/webp'):
            raise RuntimeError('Unsupported avatar image format.')
        image = response.read(1024 * 1024 + 1)
    if len(image) > 1024 * 1024:
        raise RuntimeError('Avatar exceeds 1 MB limit.')
    return 'data:' + mime + ';base64,' + base64.b64encode(image).decode('ascii')

def write_index(path, result):
    html = path.read_text()
    pattern = r'(<script type="application/json" id="youtube-avatar-data">\n).*?(\n</script>)'
    payload = json.dumps(result, indent=2, ensure_ascii=True).replace('<', '\\u003c')
    updated, count = re.subn(pattern, lambda m: m[1] + payload + m[2], html, flags=re.S)
    if count != 1:
        raise RuntimeError('Expected exactly one embedded avatar data block; no file changed.')
    temporary = path.with_suffix('.html.tmp')
    temporary.write_text(updated)
    temporary.replace(path)

def main():
    key = os.environ.get('YOUTUBE_API_KEY', '')
    if not key:
        sys.exit('YOUTUBE_API_KEY is missing. Add it as a repository Actions secret; no files changed.')
    base = 'https://raw.githubusercontent.com/The-Layout-List/website/main/data/'
    # Fetch the ranked catalog rather than the fork's stale copy.
    paths = read_json(base + '_list.json')
    from concurrent.futures import ThreadPoolExecutor
    def level(path):
        return read_json(base + urllib.parse.quote(str(path).lstrip('_'), safe='') + '.json')
    with ThreadPoolExecutor(max_workers=8) as pool:
        catalog = list(pool.map(level, paths))
    now = dt.datetime.now(dt.timezone.utc).isoformat()
    result = build(catalog, lambda ids: youtube('videos', ids, key), lambda ids: youtube('channels', ids, key), now)
    for row in result['players'].values():
        row['imageUrl'] = embed_picture(row['imageUrl'])
    write_index(ROOT / 'index.html', result)
    print(f"Resolved {len(result['players'])} pilot avatars; {len(result['review'])} need review.")

if __name__ == '__main__':
    main()

