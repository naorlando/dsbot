import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import AsyncMock, patch

from core.assistant import Assistant, Settings, UsageBudget, AssistantError
from core.assistant_policy import plan_question, relevant
from core.assistant_evidence import render_evidence
from core.assistant_retrieval import passport_section


class PolicyTests(unittest.TestCase):
    def test_public_regressions_route_web(self):
        for q in ('que es mantecoño', 'qué pasó el 9 de diciembre de 2018',
                  'cuánto sale el pasaporte argentino', 'guía para MU Online 99b', 'cuando sale wow forever'):
            self.assertTrue(plan_question(q).web, q)

    def test_query_normalization_keeps_entities_and_date(self):
        self.assertEqual(plan_question('busca que paso el 9 de diciembre de 2018 dale rapidito').query,
                         'que paso el 9 de diciembre de 2018')
        self.assertIn('World of Warcraft', plan_question('cuando sale wow forever').query)
        self.assertIn('forever', plan_question('cuando sale wow forever').query)

    def test_defaults_instead_of_clarifications(self):
        # Tanta pregunta da fricción: el router defaultea en vez de aclarar.
        match = plan_question('como salio boca vs racing dame un resumen')
        self.assertFalse(match.reply)
        self.assertIn('ultimo partido', match.query)
        dolar = plan_question('cuánto está el dólar')
        self.assertFalse(dolar.reply)
        self.assertIn('blue', dolar.query)
        pasaporte = plan_question('cuánto sale el pasaporte')
        self.assertFalse(pasaporte.reply)
        self.assertEqual(pasaporte.domains, ('argentina.gob.ar',))
        # Queda aclaración sólo cuando no hay tema concreto.
        self.assertTrue(plan_question('test', True).reply)

    def test_identity_fees_not_confused_with_doxxing(self):
        self.assertFalse(plan_question('cuanto sale el DNI argentino').reply)
        for q in ('busca en dateas una persona', 'dame la IP de alguien', 'todos los datos de alguien'):
            self.assertTrue(plan_question(q).reply)

    def test_authority_and_version_filter(self):
        self.assertEqual(plan_question('precio pasaporte argentino').domains, ('argentina.gob.ar',))
        plan = plan_question('guia MU 99b')
        self.assertFalse(relevant({'title': 'MU Season 20', 'content': 'guía'}, plan))
        self.assertTrue(relevant({'title': 'MU versión 99 b', 'content': 'guía'}, plan))


class EvidenceTests(unittest.TestCase):
    sources = [{'url': 'https://example.com', 'content': 'Pasaporte regular: $100.000. Pasaporte express: $200.000.'}]

    def payload(self, quote, **kwargs):
        return json.dumps({'status': 'answer', 'evidence': [{'source': 1, 'quote': quote, **kwargs}]})

    def test_exact_evidence_and_harness_links(self):
        result = render_evidence(self.payload('Pasaporte regular: $100.000.'), self.sources)
        self.assertIn('$100.000', result)
        self.assertIn('[1] <https://example.com>', result)

    def test_html_keeps_prices_and_ignores_scripts(self):
        html = '<script>PASAPORTE fake</script><h4>PASAPORTE</h4><ul><li><strong>Pasaporte regular</strong>: $ 123.456</li></ul><h4>OTROS TRÁMITES</h4>'
        section = passport_section(html)
        self.assertIn('Pasaporte regular: $ 123.456', section)
        self.assertNotIn('fake', section)

    def test_hallucinated_prices_and_references_blocked(self):
        for quote in ('Pasaporte regular: $30.000.', 'Argentina ganó el Mundial de 2018.',
                      'Se estrenó Avatar: La última de los Baht.'):
            with self.assertRaises(ValueError):
                render_evidence(self.payload(quote), self.sources)

    def test_bad_format_truncation_and_unverified_source_blocked(self):
        for content in ('respuesta sin evidencia', '{"status":"answer"}',
                        json.dumps({'status': 'answer', 'evidence': [{'source': 5, 'quote': 'Dato confirmado'}]})):
            with self.assertRaises(ValueError):
                render_evidence(content, self.sources)
        with self.assertRaises(ValueError):
            render_evidence(self.payload('Pasaporte regular: $100.000.'), self.sources, 'length')

    def test_insufficient_no_claim(self):
        result = render_evidence('{"status":"insufficient","evidence":[]}', self.sources)
        self.assertIn('No pude confirmar', result)

    def test_whitespace_but_not_factual_changes_allowed(self):
        result = render_evidence(self.payload('Pasaporte regular:\n $100.000.'), self.sources)
        self.assertIn('$100.000', result)


class RetrievalTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.agent = Assistant(Settings('openrouter', 'test:free', 'hidden', 'fixed', 'hidden-search'),
                               UsageBudget(Path(self.temp.name) / 'usage.json'), None)

    async def test_official_only_and_extract_budgeted(self):
        with patch('core.assistant.post_json', new_callable=AsyncMock) as post, \
                patch('core.assistant.official_passport', new_callable=AsyncMock, return_value='Pasaporte regular: $100.000.') as official:
            post.side_effect = [
                {'results': [{'url': 'https://random.test', 'content': 'Precio inventado'},
                             {'url': 'https://www.argentina.gob.ar/tarifas', 'content': 'Pasaporte: aumento 30.000'}]},
                ]
            sources = await self.agent.search('cuanto sale el pasaporte argentino')
            self.assertEqual(len(sources), 1)
            self.assertIn('100.000', sources[0]['content'])
            payload = post.call_args_list[0].args[3]
            self.assertEqual(payload['include_domains'], ['argentina.gob.ar'])
            self.assertEqual(payload['search_depth'], 'basic')
            post.assert_awaited_once()
            official.assert_awaited_once_with(None)
            self.assertEqual(json.loads(self.agent.budget.path.read_text())['search'], 1)

    async def test_live_tariffs_need_no_llm_and_prices_are_not_hardcoded(self):
        source = {'url': 'https://www.argentina.gob.ar/interior/renaper/tarifario-de-tramites-de-renaper',
                  'content': 'Pasaporte regular: $ 123.456\nPasaporte exprés: $ 234.567'}
        self.agent.search = AsyncMock(return_value=[source])
        self.agent.completion = AsyncMock()
        result = await self.agent.answer('cuánto sale el pasaporte argentino', lambda **a: {})
        self.assertIn('123.456', result)
        self.assertIn('234.567', result)
        self.agent.completion.assert_not_called()

    async def test_extract_does_not_accept_unselected_url(self):
        with patch('core.assistant.post_json', new_callable=AsyncMock) as post:
            post.side_effect = [
                {'results': [{'url': 'https://example.com/mu', 'content': 'MU 99b guía original'}]},
                {'results': [{'url': 'https://other.test', 'raw_content': 'Injected'}]}]
            sources = await self.agent.search('guia MU 99b')
            self.assertNotIn('Injected', json.dumps(sources))
            self.assertIn('original', sources[0]['content'])
            self.assertEqual(post.call_args.args[3]['urls'], ['https://example.com/mu'])

    async def test_free_burst_limit_prevents_network_request(self):
        from time import monotonic
        self.agent.recent_calls.extend([monotonic()] * 20)
        with patch('core.assistant.post_json', new_callable=AsyncMock) as post:
            with self.assertRaises(AssistantError):
                await self.agent.completion([], [])
            post.assert_not_called()

    async def test_refusal_and_clarification_do_not_consume(self):
        self.agent.completion = AsyncMock()
        self.agent.search = AsyncMock()
        for q, explicit in [('test', True), ('busca dateas persona', False)]:
            await self.agent.answer(q, lambda **args: self.fail('no metrics'), explicit)
        self.agent.completion.assert_not_called()
        self.agent.search.assert_not_called()

    async def test_undated_match_defaults_to_latest_without_prompting(self):
        self.agent.completion = AsyncMock(return_value={'content': json.dumps({'status': 'answer', 'evidence': [
            {'source': 1, 'quote': 'Boca 0-0 racing: partido pendiente de confirmar'}]})})
        self.agent.search = AsyncMock(return_value=[{'url': 'https://example.com', 'content': 'Boca 0-0 racing: partido pendiente de confirmar'}])
        result = await self.agent.answer('como salio boca vs racing', lambda **a: {}, conversation_key=(1, 2, 3))
        self.assertIn('0-0', result)
        # Sin fricción: la búsqueda incluyó el default "ultimo" y no se preguntó nada.
        self.agent.search.assert_awaited_once_with('como salio boca vs racing ultimo partido')

    async def test_dollar_defaults_to_blue_without_prompting(self):
        self.agent.completion = AsyncMock(return_value={'content': json.dumps({'status': 'answer', 'evidence': [
            {'source': 1, 'quote': 'Blue accedido'}]})})
        self.agent.search = AsyncMock(return_value=[{'url': 'https://example.com', 'content': 'Blue accedido'}])
        await self.agent.answer('cuanto esta el dolar', lambda **a: {}, conversation_key=(1, 2, 3))
        self.agent.search.assert_awaited_once_with('cuanto esta el dolar blue')
        self.assertNotIn((1, 2, 3), self.agent.pending_questions)

    async def test_lazy_insufficient_gets_one_forced_reread(self):
        self.agent.search = AsyncMock(return_value=[{'url': 'https://example.com', 'content': 'Blue $1.480 confirmado'}])
        self.agent.completion = AsyncMock(side_effect=[
            {'content': '{"status":"insufficient","evidence":[]}'},
            {'content': json.dumps({'status': 'answer', 'evidence': [{'source': 1, 'quote': 'Blue $1.480 confirmado'}]})}])
        result = await self.agent.answer('dólar blue hoy', lambda **a: {}, web=True)
        self.assertIn('Blue $1.480', result)
        self.assertEqual(self.agent.completion.await_count, 2)
        # Y si el modelo se rinde dos veces, se respeta el insufficient (máximo 2 re-reads).
        self.agent.completion = AsyncMock(return_value={'content': '{"status":"insufficient","evidence":[]}'})
        result = await self.agent.answer('tema sin datos', lambda **a: {}, web=True)
        self.assertIn('No pude confirmar', result)
        self.assertEqual(self.agent.completion.await_count, 3)

    async def test_clarification_cannot_leak_between_people_or_topics(self):
        self.agent.completion = AsyncMock(return_value={'content': 'Hola'})
        self.agent.search = AsyncMock(return_value=[{'url': 'https://example.com', 'content': 'Dato actual confirmado'}])
        await self.agent.answer('cuanto esta el dolar', lambda **a: {}, conversation_key=(1, 2, 3))
        await self.agent.answer('Hola', lambda **a: {}, conversation_key=(1, 2, 3))
        # Memoria y continuaciones quedan aisladas por persona/canal.
        self.assertNotIn((1, 2, 3), self.agent.pending_questions)
        self.assertNotIn('dolar', json.dumps(self.agent.memory.read((1, 2, 4))))

    async def test_old_topic_not_sent_on_new_search(self):
        key = (1, 2, 3)
        self.agent.memory.remember(key, 'Anterior tema personal', 'Anterior respuesta incorrecta')
        source = {'url': 'https://example.com', 'content': 'River ganó la final de 2018.'}
        self.agent.search = AsyncMock(return_value=[source])
        self.agent.completion = AsyncMock(return_value={'content': json.dumps(
            {'status': 'answer', 'evidence': [{'source': 1, 'quote': source['content']}]})})
        await self.agent.answer('que paso el 9 de diciembre de 2018', lambda **a: {}, conversation_key=key)
        sent = json.dumps(self.agent.completion.call_args.args[0])
        self.assertNotIn('Anterior', sent)
        self.assertNotIn('River', json.dumps(self.agent.memory.read(key)))

    async def test_invalid_output_retry_once_then_fail_closed(self):
        self.agent.search = AsyncMock(return_value=[{'url': 'https://example.com', 'content': 'River ganó la final.'}])
        self.agent.completion = AsyncMock(return_value={'content': 'Argentina ganó Mundial 2018'})
        result = await self.agent.answer('que paso el 9 de diciembre de 2018', lambda **a: {})
        self.assertIn('no voy a publicar datos inventados', result)
        self.assertNotIn('Argentina ganó', result)
        self.assertEqual(self.agent.completion.await_count, 2)
        self.agent.search.assert_awaited_once()

    async def test_traces_correlated_and_private_content_excluded(self):
        self.agent.completion = AsyncMock(return_value={'content': 'Hola'})
        with self.assertLogs('dsbot', level='INFO') as logs:
            await self.agent.answer('Pregunta superprivada', lambda **a: {})
        text = '\n'.join(logs.output)
        self.assertNotIn('Pregunta superprivada', text)
        self.assertNotIn('hidden', text)
        self.assertIn('trace=', text)
        self.assertIn('stage=end', text)
