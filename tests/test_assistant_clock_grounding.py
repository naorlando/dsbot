"""Offline clock, common footer, and structural grounding-boundary regressions."""
import copy
import json
import unittest
from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock, patch
from zoneinfo import ZoneInfoNotFoundError

from core.assistant_clock import clock_context
from core.assistant_evidence import evidence_failure, render_evidence, web_footer
from core.assistant_tools import GroundError, _grounding_sources, google_ground


NOW = datetime(2026, 11, 1, 1, 2, 3, tzinfo=timezone.utc)
TEXT = 'El dólar cerró a $1.234,50 el miércoles. La variación fue de 2%.'


def source(uri='https://example.com/report'):
    return {'web': {'uri': uri, 'title': 'Informe público'}}


def support(text, start=0, end=None, indices=None, part=0):
    end = len(text) if end is None else end
    return {'segment': {'partIndex': part, 'startIndex': len(text[:start].encode('utf-8')),
                        'endIndex': len(text[:end].encode('utf-8')), 'text': text[start:end]},
            'groundingChunkIndices': [0] if indices is None else indices}


def metadata(text=TEXT):
    return {'groundingChunks': [source()], 'groundingSupports': [support(text)]}


def validate(text=TEXT, meta=None, parts=None):
    return _grounding_sources([{'text': text}] if parts is None else parts, text,
                              metadata(text) if meta is None else meta, NOW.isoformat())


class ClockTests(unittest.TestCase):
    def test_spanish_argentina_day_rollover_and_utc(self):
        text = clock_context(NOW)
        self.assertIn('America/Argentina/Buenos_Aires', text)
        self.assertIn('sábado 31 de octubre de 2026', text)
        self.assertIn('2026-10-31T22:02:03-03:00', text)
        self.assertIn('UTC: 2026-11-01T01:02:03+00:00', text)

    def test_windows_missing_tzdata_uses_fixed_offset_not_host_zone(self):
        with patch('core.assistant_clock.ZoneInfo', side_effect=ZoneInfoNotFoundError) as zone:
            self.assertEqual(clock_context(NOW), clock_context(NOW.replace(tzinfo=None)))
            text = clock_context(NOW)
        zone.assert_called_with('America/Argentina/Buenos_Aires')
        self.assertIn('2026-10-31T22:02:03-03:00', text)

    def test_aware_input_is_an_instant_and_zoneinfo_is_used(self):
        with patch('core.assistant_clock.ZoneInfo', return_value=timezone(timedelta(hours=-3))) as zone:
            self.assertEqual(clock_context(NOW), clock_context(NOW.astimezone(timezone(timedelta(hours=5)))))
        self.assertEqual(zone.call_count, 2)

    def test_live_clock_is_read_at_call_time(self):
        with patch('core.assistant_clock.datetime') as clock:
            clock.now.return_value = NOW
            self.assertIn('2026-11-01T01:02:03+00:00', clock_context())
        clock.now.assert_called_once_with(timezone.utc)


class FooterTests(unittest.TestCase):
    def test_shared_footer_distinguishes_modes_and_uses_utc_retrieval(self):
        local = NOW.astimezone(timezone(timedelta(hours=-3)))
        for kind, description in [('grounded', 'respuesta anclada'), ('literal', 'citas literales'),
                                  ('unconfirmed', 'sin confirmación')]:
            result = web_footer([(1, 'https://example.com')], kind, local)
            self.assertTrue(result.startswith('\n\nFuentes consultadas'))
            self.assertIn(description, result)
            self.assertIn('Recuperadas: 2026-11-01 01:02:03 UTC', result)
            self.assertIn('[1] <https://example.com>', result)
        self.assertNotIn('citas literales', web_footer([(1, 'https://example.com')], 'grounded', NOW))

    def test_literal_and_failure_renderers_share_footer(self):
        sources = [{'url': 'https://example.com', 'content': TEXT, 'title': 'Informe'}]
        payload = json.dumps({'status': 'answer', 'evidence': [{'source': 1, 'passage': 1}]})
        self.assertTrue(render_evidence(payload, sources, now=NOW).endswith(
            web_footer([(1, sources[0]['url'])], 'literal', NOW)))
        self.assertTrue(evidence_failure(sources, now=NOW).endswith(
            web_footer([('Informe', sources[0]['url'])], 'unconfirmed', NOW)))

    def test_display_budget_includes_timestamp_and_labels_exact_boundary(self):
        sources = [{'url': f'https://example.com/{i}/' + 'x' * 80,
                    'content': str(i) + ' ' + 'a' * 448} for i in range(3)]
        payload = json.dumps({'status': 'answer', 'evidence': [
            {'source': i, 'passage': 1} for i in range(1, 4)]})
        baseline = render_evidence(payload, sources, now=NOW)
        self.assertLess(len(baseline), 1990)
        sources[0]['url'] += 'x' * (1990 - len(baseline))
        self.assertEqual(len(render_evidence(payload, sources, now=NOW)), 1990)
        sources[0]['url'] += 'x'
        with self.assertRaisesRegex(ValueError, 'display_limit'):
            render_evidence(payload, sources, now=NOW)

    def test_failure_with_maximal_urls_and_titles_stays_bounded(self):
        sources = [{'url': f'https://example.com/{i}/' + 'x' * 477, 'title': 'T' * 120}
                   for i in range(3)]
        result = evidence_failure(sources, now=NOW)
        self.assertLessEqual(len(result), 1990)
        self.assertEqual(result.count('<https://'), 3)
        self.assertIn('sin confirmación', result)

    def test_footer_rejects_unsafe_input_and_oversize(self):
        for links, kind in [([(1, 'http://localhost')], 'grounded'),
                            ([('@everyone', 'https://example.com')], 'unconfirmed'),
                            ([(True, 'https://example.com')], 'literal'),
                            ([(1, 'https://example.com')], 'truth-verified')]:
            with self.subTest(links=links, kind=kind), self.assertRaises(ValueError):
                web_footer(links, kind, NOW)
        urls = [(i + 1, 'https://example.com/' + 'x' * 480) for i in range(5)]
        with self.assertRaisesRegex(ValueError, 'display_limit'):
            web_footer(urls, 'grounded', NOW)


class GroundSupportTests(unittest.TestCase):
    def test_complete_utf8_attribution_not_literal_source_quotation(self):
        text, sources = validate()
        self.assertEqual(text, TEXT)
        self.assertEqual(sources[0]['content'], TEXT)
        self.assertEqual(sources[0]['retrieved_at'], NOW.isoformat())

    def test_multiple_supports_cover_all_prose(self):
        split = TEXT.index(' La variación')
        meta = metadata()
        meta['groundingChunks'].append(source('https://second.example/report'))
        meta['groundingSupports'] = [support(TEXT, 0, split), support(TEXT, split + 1, indices=[1])]
        _, sources = validate(meta=meta)
        self.assertEqual(len(sources), 2)
        self.assertIn('La variación', sources[1]['content'])

    def test_missing_empty_malformed_or_partial_supports_fail_closed(self):
        variants = [None, [], {}, 'not supports', [None], [{}],
                    [{'segment': None, 'groundingChunkIndices': [0]}],
                    [support(TEXT, 0, TEXT.index(' La variación'))],
                    [support(TEXT, TEXT.index('La variación'))]]
        for supports in variants:
            meta = metadata()
            meta['groundingSupports'] = supports
            with self.subTest(supports=supports), self.assertRaises(GroundError):
                validate(meta=meta)
        meta = metadata()
        del meta['groundingSupports']
        with self.assertRaises(GroundError):
            validate(meta=meta)

    def test_supported_prefix_suffix_and_numbers_cannot_hide_unsupported_claims(self):
        for text, start, end in [('Precio: 1234.', 0, 9),
                                 ('NO ' + TEXT, 3, None), (TEXT + ' Otra afirmación.', 0, len(TEXT)),
                                 ('-1234', 1, None), ('>1234', 1, None), ('1.234', 0, 1),
                                 ('1*234', 2, None), (TEXT + '#', 0, len(TEXT))]:
            meta = {'groundingChunks': [source()], 'groundingSupports': [support(text, start, end)]}
            with self.subTest(text=text), self.assertRaises(GroundError):
                validate(text, meta)

    def test_forged_text_normalization_and_wrong_offsets_are_rejected(self):
        variants = [{'text': TEXT.replace('1.234,50', '9.999,00')},
                    {'text': TEXT.replace('dólar', 'do\u0301lar')},
                    {'text': TEXT.replace(' cerró', '  cerró')},
                    {'startIndex': 1}, {'endIndex': len(TEXT)},
                    {'startIndex': -1}, {'endIndex': 100_000}, {'endIndex': True},
                    {'startIndex': '0'}, {'endIndex': 0}, {'partIndex': True}, {'partIndex': 2}]
        for changes in variants:
            meta = metadata()
            meta['groundingSupports'][0]['segment'].update(changes)
            with self.subTest(changes=changes), self.assertRaises(GroundError):
                validate(meta=meta)

    def test_utf8_boundaries_and_nonzero_offsets(self):
        text = '**' + TEXT + '**'
        meta = {'groundingChunks': [source()], 'groundingSupports': [support(text, 2, len(text) - 2)]}
        self.assertEqual(validate(text, meta)[0], text)
        # Offset in the middle of the two-byte ó must never be rounded/repaired.
        meta['groundingSupports'][0]['segment']['startIndex'] = len('**El d'.encode()) + 1
        with self.assertRaises(GroundError):
            validate(text, meta)

    def test_text_only_requires_unique_exact_match_and_complete_coverage(self):
        meta = metadata()
        meta['groundingSupports'][0]['segment'] = {'text': TEXT}
        self.assertEqual(validate(meta=meta)[0], TEXT)
        repeated = TEXT + '\n' + TEXT
        with self.assertRaises(GroundError):
            validate(repeated, meta)
        meta['groundingSupports'][0]['segment']['text'] = 'forged'
        with self.assertRaises(GroundError):
            validate(meta=meta)

    def test_omitted_zero_start_offset_is_valid(self):
        meta = metadata()
        del meta['groundingSupports'][0]['segment']['startIndex']
        self.assertEqual(validate(meta=meta)[0], TEXT)

    def test_malformed_indices_and_unsafe_sources_are_rejected(self):
        for indices in [None, [], '0', [True], [-1], [1], [0.0], [0, 1]]:
            meta = metadata()
            meta['groundingSupports'][0]['groundingChunkIndices'] = indices
            with self.subTest(indices=indices), self.assertRaises(GroundError):
                validate(meta=meta)
        for uri in ['file:///tmp/report', 'http://127.0.0.1/report', 'https://facebook.com./report',
                    'https://example.com/?token=private', 'https://user:pass@example.com']:
            meta = metadata()
            meta['groundingChunks'] = [source(uri)]
            with self.subTest(uri=uri), self.assertRaises(GroundError):
                validate(meta=meta)

    def test_unused_chunks_are_skipped_and_markers_renumbered(self):
        text = TEXT + ' [2]'
        meta = {'groundingChunks': [source('http://localhost/'), source('https://second.example'),
                                   source('https://unused.example')],
                'groundingSupports': [support(text, 0, len(TEXT), indices=[1])]}
        answer, sources = validate(text, meta)
        self.assertEqual(answer, TEXT + ' [1]')
        self.assertEqual([s['url'] for s in sources], ['https://second.example'])
        meta['groundingSupports'][0]['groundingChunkIndices'] = [0, 1]
        with self.assertRaises(GroundError):
            validate(text, meta)

    def test_attributed_bracketed_numbers_are_not_rewritten_as_citations(self):
        text = 'La lista publicada contiene [2] y [1, 2].'
        meta = {'groundingChunks': [source('https://unused.example'), source()],
                'groundingSupports': [support(text, indices=[1])]}
        self.assertEqual(validate(text, meta)[0], text)

    def test_formatting_separators_allowed_but_citations_need_valid_indices(self):
        text = '# **' + TEXT + '**\n\n---\n[1]'
        meta = {'groundingChunks': [source()], 'groundingSupports': [support(text, 4, 4 + len(TEXT))]}
        self.assertEqual(validate(text, meta)[0], text)
        with self.assertRaises(GroundError):
            validate(text.replace('[1]', '[99]'), meta)
        with self.assertRaises(GroundError):
            validate('*** [1]', {'groundingChunks': [source()],
                                 'groundingSupports': [support('*** [1]', 0, 3)]})

    def test_part_offsets_and_thoughts_are_separate(self):
        first, second = TEXT.split(' La variación')
        second = ' La variación' + second
        parts = [{'thought': True, 'text': 'private'}, {'text': first}, {'text': second}]
        meta = {'groundingChunks': [source()],
                'groundingSupports': [support(first, part=1), support(second, part=2)]}
        self.assertEqual(validate(TEXT, meta, parts)[0], TEXT)
        meta['groundingSupports'][0]['segment']['partIndex'] = 0
        with self.assertRaises(GroundError):
            validate(TEXT, meta, parts)

    def test_malformed_support_cannot_hide_behind_valid_support(self):
        meta = metadata()
        meta['groundingSupports'].append({'segment': {'text': 'not in the answer'},
                                          'groundingChunkIndices': [0]})
        with self.assertRaises(GroundError):
            validate(meta=meta)


class GroundIntegrationTests(unittest.IsolatedAsyncioTestCase):
    async def test_public_call_uses_clock_and_rejects_incomplete_metadata(self):
        payload = {'candidates': [{'content': {'parts': [{'text': TEXT}]},
                                   'groundingMetadata': metadata()}]}
        response = AsyncMock()
        response.status = 200
        response.content_length = None
        response.content = None
        response.read.return_value = json.dumps(payload).encode()
        response.__aenter__.return_value = response
        session = unittest.mock.Mock()
        session.post.return_value = response
        with patch('core.assistant_tools._utc_now', return_value=NOW):
            text, _ = await google_ground(session, 'offline-key', 'consulta pública', 'model')
        self.assertEqual(text, TEXT)
        prompt = session.post.call_args.kwargs['json']['contents'][0]['parts'][0]['text']
        self.assertIn(clock_context(NOW), prompt)
        bad = copy.deepcopy(payload)
        bad['candidates'][0]['groundingMetadata']['groundingSupports'][0]['segment'] = {
            'text': TEXT[:20], 'startIndex': 0, 'endIndex': len(TEXT[:20].encode())}
        response.read.return_value = json.dumps(bad).encode()
        with self.assertRaises(GroundError):
            await google_ground(session, 'offline-key', 'consulta pública', 'model')

    async def test_answer_size_is_never_silently_truncated(self):
        text = 'á' * 1901
        payload = {'candidates': [{'content': {'parts': [{'text': text}]},
                                   'groundingMetadata': metadata(text)}]}
        response = AsyncMock()
        response.status, response.content, response.content_length = 200, None, None
        response.read.return_value = json.dumps(payload).encode()
        response.__aenter__.return_value = response
        session = unittest.mock.Mock()
        session.post.return_value = response
        with self.assertRaises(GroundError):
            await google_ground(session, 'offline-key', 'consulta', 'model')
