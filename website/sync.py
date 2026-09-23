#!/usr/bin/env python3
"""Render the complete public release history. Deploy mode has fixed write targets."""
import argparse
import datetime as dt
import fcntl
import html
import json
import os
from pathlib import Path
import re
import tempfile
import urllib.parse
import urllib.request

REPO = 'Hatcherthekid/chatgrowing-plugin-marketplace'
BASE = Path(__file__).resolve().parent
TARGET = Path('/var/www/chatgrowing/changelog-managed')


def fetch(url):
    req = urllib.request.Request(url, headers={'User-Agent': 'ChatGrowing-Changelog/1.0', 'Accept': 'application/vnd.github+json'})
    with urllib.request.urlopen(req, timeout=30) as response:
        return json.load(response)


def releases(fetcher=fetch):
    rows, page = [], 1
    while True:
        batch = fetcher(f'https://api.github.com/repos/{REPO}/releases?per_page=100&page={page}')
        if not isinstance(batch, list):
            raise ValueError('Invalid GitHub release response')
        rows.extend(batch)
        if len(batch) < 100:
            return rows
        page += 1


def timestamp(value):
    return dt.datetime.fromisoformat(value.replace('Z', '+00:00')).astimezone(dt.timezone.utc)


def combine(rows, history):
    result, seen = [], set()
    for r in rows:
        if r.get('draft') or r.get('prerelease'):
            continue
        tag = r['tag_name']
        version = tag.removeprefix('v')
        if not re.fullmatch(r'\d+\.\d+\.\d+', version):
            raise ValueError('Stable release must use a semantic version tag')
        if version in seen:
            raise ValueError('Duplicate stable release version')
        seen.add(version)
        expected = f'https://github.com/{REPO}/releases/tag/{urllib.parse.quote(tag, safe="")}'
        if r['html_url'] != expected:
            raise ValueError('Unexpected release URL')
        result.append(dict(version=version, date=r['published_at'], title=r.get('name') or tag,
                           body=r.get('body') or '', url=expected, kind='release', tag=tag))
    for row in history:
        if row['version'].split('+')[0] not in seen:
            result.append(row)
    return sorted(result, key=lambda r: timestamp(r['date']), reverse=True)


def inline(text):
    # Escape everything first; only explicit http(s) Markdown links become HTML.
    escaped = html.escape(text)
    def link(m):
        url = html.unescape(m[2])
        if urllib.parse.urlsplit(url).scheme not in ('https', 'http'):
            return m[0]
        return f'<a href="{html.escape(url, quote=True)}" rel="noopener noreferrer">{m[1]}</a>'
    return re.sub(r'\[([^\]\n]+)\]\((https?://[^\s)]+)\)', link, escaped)


def markdown(body):
    out, bullets, paragraph = [], [], []
    def flush():
        if paragraph:
            out.append('<p>'+inline(' '.join(paragraph))+'</p>'); paragraph.clear()
        if bullets:
            out.append('<ul>'+''.join('<li>'+inline(x)+'</li>' for x in bullets)+'</ul>'); bullets.clear()
    for line in body.splitlines():
        line = line.strip()
        if not line:
            flush()
        elif re.match(r'^#{1,6}\s', line):
            flush(); out.append('<h3>'+inline(re.sub(r'^#+\s+', '', line))+'</h3>')
        elif re.match(r'^[-*]\s', line):
            if paragraph: flush()
            bullets.append(line[2:])
        else:
            if bullets: flush()
            paragraph.append(line)
    flush()
    return ''.join(out)


def render(rows, template):
    if not rows:
        raise ValueError('Refuse to replace history with an empty page')
    esc = html.escape
    nav, cards = [], []
    for r in rows:
        version = r['version']; anchor = 'v'+version.split('+')[0]
        date = r.get('date_label') or timestamp(r['date']).strftime('%B %d, %Y')
        label = 'Released' if r['kind'] == 'release' else 'Marketplace commit' if r['kind']=='marketplace' else 'Archived · '+r['status']
        nav.append(f'<a href="#{esc(anchor)}">{esc(version.split("+")[0])}</a>')
        old_anchor = r.get('anchor', 'v'+version.split('+')[0].replace('.', '-'))
        source_label = 'GitHub Release' if r['kind']=='release' else 'Original marketplace record' if r['kind']=='marketplace' else 'Archived changelog source'
        cards.append(f'<article class="release" id="{esc(anchor)}" data-version="{esc(version)}"><header class="release-meta"><time datetime="{esc(r["date"])}">{esc(date)}</time><span class="status">{esc(label)}</span></header><div class="article-body"><span id="{esc(old_anchor)}"></span><h2>{esc(r["title"])}</h2>'+markdown(r['body'])+f'<p><a href="{esc(r["url"], quote=True)}">{source_label} ↗</a></p></div></article>')
    latest=esc(rows[0]['version'].split('+')[0])
    main='<main id="main" class="editorial changelog-history"><header class="shell editorial-hero"><p class="eyebrow">PRODUCT UPDATES</p><h1>What’s new in ChatGrowing.</h1><p class="lede">New features, improvements, and fixes — every version, newest first.</p></header><div class="shell"><aside id="version-status" class="editorial-note version-status"><p><strong>'+str(len(rows))+' documented versions</strong> · Latest release: <strong>'+latest+'</strong></p><p>Refresh the marketplace, explicitly update the installed plugin, then open a new task. <a href="https://github.com/'+REPO+'/blob/main/INSTALL.md">Update instructions ↗</a></p></aside><nav class="version-jumps" aria-label="Versions">'+''.join(nav)+'</nav><div class="release-list">'+''.join(cards)+'</div><p class="editorial-meta">New release notes synchronize from GitHub. Earlier website records retain their original dates and status; historical candidate notes describe their status at that time.</p></div></main>'
    if template.count('<!-- RELEASE_HISTORY -->') != 1:
        raise ValueError('Invalid page template')
    return template.replace('<!-- RELEASE_HISTORY -->', main)


def atomic(path, content):
    fd, tmp = tempfile.mkstemp(prefix='.changelog-', dir=path.parent)
    try:
        with os.fdopen(fd, 'w') as f:
            f.write(content); f.flush(); os.fsync(f.fileno())
        os.chmod(tmp, 0o644); os.replace(tmp, path)
    finally:
        if os.path.exists(tmp): os.unlink(tmp)


def build():
    rows = combine(releases(), json.loads((BASE/'history.json').read_text()))
    for r in rows:
        if r['kind'] == 'release':
            manifest = fetch(f'https://raw.githubusercontent.com/{REPO}/{urllib.parse.quote(r["tag"], safe="")}/plugins/chatgrowing/.codex-plugin/plugin.json')
            if manifest['version'] != r['version']:
                raise ValueError('Release tag/plugin version mismatch')
    return rows, render(rows, (BASE/'template.html').read_text())


def main():
    parser = argparse.ArgumentParser(); parser.add_argument('--deploy', action='store_true'); parser.add_argument('--output', type=Path); args = parser.parse_args()
    if args.deploy:
        with (TARGET/'.sync.lock').open('a') as lock:
            fcntl.flock(lock, fcntl.LOCK_EX)
            rows, page = build()  # All network/validation completes before replacing any page.
            sitemap = (TARGET/'sitemap.xml').read_text()
            if 'https://chatgrowing.com/changelog/' not in sitemap:
                sitemap = sitemap.replace('</urlset>', '<url><loc>https://chatgrowing.com/changelog/</loc></url></urlset>')
            atomic(TARGET/'sitemap.xml', sitemap)
            atomic(TARGET/'index.html', page)
            print(json.dumps({'status':'published','versions':[r['version'] for r in rows]}))
    else:
        rows, page = build()
        if not args.output: parser.error('--output required without --deploy')
        args.output.write_text(page)
        print(json.dumps({'status':'built','versions':[r['version'] for r in rows]}))

if __name__ == '__main__': main()
