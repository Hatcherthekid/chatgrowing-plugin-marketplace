import unittest
from unittest.mock import patch
import sync


def release(version, date='2026-09-20T03:00:00Z', **extra):
    return dict(tag_name='v'+version,published_at=date,name='Version '+version,body='- change',html_url=f'https://github.com/{sync.REPO}/releases/tag/v{version}',**extra)

class HistoryTests(unittest.TestCase):
    def test_all_versions_sort_and_release_replaces_legacy(self):
        history=[dict(version='0.4.3',date='2026-09-15T00:00:00Z',title='Old',body='old',url='https://example.com',kind='marketplace')]
        rows=sync.combine([release('0.4.4'),release('0.4.3','2026-09-16T00:00:00Z'),release('0.4.5',draft=True),release('0.5.0',prerelease=True)],history)
        self.assertEqual([r['version'] for r in rows],['0.4.4','0.4.3'])
        page=sync.render(rows,'<!-- RELEASE_HISTORY -->')
        self.assertEqual(page.count('data-version='),2)
        self.assertIn('href="#v0.4.3"',page)
        self.assertEqual(page.count('<header class="release-meta"><time '),2)
        self.assertNotIn('<article class="release" id="v0.4.4" data-version="0.4.4"><aside>',page)
    def test_pagination_is_not_latest_only(self):
        batches=iter([[release('0.4.4')]*100,[release('0.4.3')]])
        self.assertEqual(len(sync.releases(lambda _:next(batches))),101)
    def test_untrusted_release_body_is_escaped(self):
        page=sync.markdown('<script>alert(1)</script>\n\n[bad](javascript:alert)\n\n[ok](https://example.com)')
        self.assertNotIn('<script>',page); self.assertNotIn('href="javascript:',page)
        self.assertIn('href="https://example.com"',page)
    def test_network_error_is_not_empty_history(self):
        with self.assertRaises(OSError): sync.releases(lambda _:(_ for _ in ()).throw(OSError('offline')))
    def test_invalid_release_link_and_duplicate_fail(self):
        r=release('0.4.4'); r['html_url']='https://evil.example'
        with self.assertRaises(ValueError): sync.combine([r],[])
        with self.assertRaises(ValueError): sync.combine([release('0.4.4')]*2,[])
    def test_missing_history_does_not_erase_existing_page(self):
        with self.assertRaises(ValueError): sync.render([], '<!-- RELEASE_HISTORY -->')

class ArchiveTests(unittest.TestCase):
    def test_complete_original_archive_survives_new_release(self):
        import json
        history=json.loads((sync.BASE/'history.json').read_text())
        expected={'0.1.0','0.1.2','0.1.3','0.1.4','0.1.5','0.1.6','0.1.7','0.1.8','0.1.9','0.2.0','0.2.1','0.2.2','0.2.3','0.3.0'}
        self.assertTrue(expected.issubset({r['version'] for r in history}))
        rows=sync.combine([release('0.4.4')],history)
        self.assertEqual(len(rows),21)
        page=sync.render(rows,(sync.BASE/'template.html').read_text())
        for version in expected:
            self.assertIn('data-version="'+version+'"',page)
        initial=next(r for r in history if r['version']=='0.1.0')
        self.assertEqual(sum(line.startswith('- ') for line in initial['body'].splitlines()),18)
        self.assertIn('Archived · Unpublished candidate',page)
        self.assertIn('id="v0-1-0"',page)

if __name__=='__main__': unittest.main()
