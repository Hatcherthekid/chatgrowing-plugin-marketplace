"""YouTube publication fields shared by review, upload, update and readback."""
from __future__ import annotations

from datetime import datetime, timezone
import re
from .material_library import MaterialError, bounded_text

FIELDS = {
    'title': ('snippet', 'title'), 'description': ('snippet', 'description'),
    'category_id': ('snippet', 'categoryId'), 'video_tags': ('snippet', 'tags'),
    'default_language': ('snippet', 'defaultLanguage'),
    'privacy': ('status', 'privacyStatus'), 'made_for_kids': ('status', 'selfDeclaredMadeForKids'),
    'contains_synthetic_media': ('status', 'containsSyntheticMedia'),
    'publish_at': ('status', 'publishAt'), 'embeddable': ('status', 'embeddable'),
    'license': ('status', 'license'), 'public_stats_viewable': ('status', 'publicStatsViewable'),
    'recording_date': ('recordingDetails', 'recordingDate'),
}
REQUIRED = {'target_id', 'title', 'description', 'privacy', 'category_id', 'made_for_kids', 'contains_synthetic_media', 'notify_subscribers'}
OPTIONAL = set(FIELDS) - REQUIRED | {'localizations', 'brand_partner', 'thumbnail_asset_id', 'captions', 'playlists'}
UNVERIFIED = {'default_audio_language', 'has_paid_product_placement'}


def timestamp(value):
    if not isinstance(value, str) or len(value) > 40 or not re.fullmatch(r'[0-9]{4}-[0-9]{2}-[0-9]{2}[Tt][0-9]{2}:[0-9]{2}:[0-9]{2}(?:\.[0-9]+)?(?:[Zz]|[+-][0-9]{2}:[0-9]{2})', value):
        raise MaterialError('youtube_datetime_invalid', 422)
    try:
        if value[-1:] not in ('Z','z') and (int(value[-5:-3]) > 23 or int(value[-2:]) > 59):
            raise ValueError()
        result = datetime.fromisoformat(value.upper().replace('Z', '+00:00'))
        if result.tzinfo is None:
            raise ValueError()
        return result.astimezone(timezone.utc)
    except (ValueError, OverflowError):
        raise MaterialError('youtube_datetime_invalid', 422) from None


def native_id(value):
    if not isinstance(value, str) or not re.fullmatch(r'[A-Za-z0-9_-]{1,128}', value):
        raise MaterialError('youtube_native_id_invalid', 422)


def language(value):
    if not isinstance(value, str) or not re.fullmatch(r'[A-Za-z]{2,3}(?:-[A-Za-z0-9]{2,8})*', value):
        raise MaterialError('youtube_language_invalid', 422)


def text_fields(title, description):
    bounded_text(title, limit=100)
    bounded_text(description, limit=5000, required=False)
    if any(c in title + description for c in '<>') or len(description.encode('utf-8')) > 5000:
        raise MaterialError('material_youtube_text_invalid', 422)


def validate_entry(entry):
    if not isinstance(entry, dict):
        raise MaterialError('material_manifest_invalid', 422)
    if set(entry) & UNVERIFIED:
        raise MaterialError('youtube_field_write_not_verified', 422)
    if not REQUIRED <= set(entry) or set(entry) - REQUIRED - OPTIONAL:
        raise MaterialError('material_manifest_invalid', 422)
    bounded_text(entry['target_id'], limit=128)
    text_fields(entry['title'], entry['description'])
    if not isinstance(entry['category_id'], str) or not re.fullmatch(r'[0-9]{1,8}', entry['category_id']) or entry['privacy'] not in ('private', 'unlisted', 'public'):
        raise MaterialError('material_manifest_invalid', 422)
    for key in ('made_for_kids', 'contains_synthetic_media', 'notify_subscribers', 'embeddable', 'public_stats_viewable'):
        if key in entry and type(entry[key]) is not bool:
            raise MaterialError('material_manifest_invalid', 422)
    if 'video_tags' in entry:
        tags = entry['video_tags']
        if not isinstance(tags, list) or len(tags) > 100:
            raise MaterialError('youtube_tags_invalid', 422)
        for tag in tags:
            bounded_text(tag, limit=500)
        if sum(len(t) + (2 if ' ' in t else 0) for t in tags) + max(0, len(tags) - 1) > 500:
            raise MaterialError('youtube_tags_invalid', 422)
    if 'default_language' in entry:
        language(entry['default_language'])
    if 'license' in entry and entry['license'] not in ('youtube', 'creativeCommon'):
        raise MaterialError('youtube_license_invalid', 422)
    for key in ('publish_at', 'recording_date'):
        if key in entry:
            timestamp(entry[key])
    if 'publish_at' in entry and entry['privacy'] != 'private':
        raise MaterialError('youtube_schedule_requires_private', 422)
    if 'localizations' in entry:
        values = entry['localizations']
        if 'default_language' not in entry or not isinstance(values, dict) or len(values) > 50:
            raise MaterialError('youtube_localizations_invalid', 422)
        for lang, value in values.items():
            language(lang)
            if not isinstance(value, dict) or set(value) != {'title', 'description'}:
                raise MaterialError('youtube_localizations_invalid', 422)
            text_fields(value['title'], value['description'])
    if 'brand_partner' in entry:
        brand = entry['brand_partner']
        # Canonical channel ID avoids comparing a write-only handle with returned IDs.
        if not isinstance(brand, dict) or set(brand) != {'channel_id'}:
            raise MaterialError('youtube_brand_partner_invalid', 422)
        native_id(brand['channel_id'])
    if 'thumbnail_asset_id' in entry:
        native_id(entry['thumbnail_asset_id'])
    for key in ('captions', 'playlists'):
        if key not in entry:
            continue
        if not isinstance(entry[key], list) or len(entry[key]) > 20:
            raise MaterialError('youtube_attachment_list_invalid', 422)
        identities = []
        for value in entry[key]:
            required = {'asset_id', 'language', 'name', 'is_draft'} if key == 'captions' else {'playlist_id'}
            allowed = required if key == 'captions' else required | {'position'}
            if not isinstance(value, dict) or not required <= set(value) or set(value) - allowed:
                raise MaterialError('youtube_attachment_invalid', 422)
            if key == 'captions':
                native_id(value['asset_id']); language(value['language'])
                bounded_text(value['name'], limit=150, required=False)
                if type(value['is_draft']) is not bool:
                    raise MaterialError('youtube_caption_invalid', 422)
                identities.append((value['language'], value['name']))
            else:
                native_id(value['playlist_id'])
                if 'position' in value and (type(value['position']) is not int or not 0 <= value['position'] <= 10000):
                    raise MaterialError('youtube_playlist_position_invalid', 422)
                identities.append(value['playlist_id'])
        if len(set(identities)) != len(identities):
            raise MaterialError('youtube_attachment_duplicate', 422)


def metadata(entry):
    result = {}
    for key, (part, native) in FIELDS.items():
        if key in entry:
            result.setdefault(part, {})[native] = entry[key]
    if 'localizations' in entry:
        result['localizations'] = entry['localizations']
    if 'brand_partner' in entry:
        result['brandPartner'] = {'channelId': entry['brand_partner']['channel_id']}
    return result


def verification(video, entry):
    if not isinstance(video, dict):
        raise MaterialError("youtube_video_response_invalid", 502)
    missing, mismatch = [], []
    for part, values in metadata(entry).items():
        observed = video.get(part, {})
        if not isinstance(observed, dict):
            raise MaterialError('youtube_video_response_invalid', 502)
        if part=='localizations':
            if observed!=values: mismatch.append('localizations')
            continue
        for key, expected in values.items():
            path = part + '.' + key
            if key not in observed:
                # An explicitly empty tags list is canonically omitted by YouTube.
                if path == 'snippet.tags' and expected == []:
                    continue
                missing.append(path)
            elif key in ('publishAt', 'recordingDate'):
                try:
                    if timestamp(observed[key]) != timestamp(expected):
                        mismatch.append(path)
                except MaterialError:
                    mismatch.append(path)
            elif observed[key] != expected:
                mismatch.append(path)
    return {'missing': missing, 'mismatch': mismatch}


def capabilities():
    return {'upload_fields': sorted(REQUIRED | OPTIONAL), 'unverified_write_fields': sorted(UNVERIFIED),
            'ai_disclosure': 'realistic_altered_or_synthetic_content',
            'operations': ['update', 'delete', 'thumbnail', 'caption', 'playlist_add'],
            'unsupported_studio_controls': ['comments_enabled', 'automatic_chapters', 'end_screens', 'cards', 'monetization', 'force_shorts'],
            'limits': {'title_characters': 100, 'description_utf8_bytes': 5000, 'tags_characters_including_separators_and_quotes': 500, 'thumbnail_bytes': 2 * 1024 * 1024}}
