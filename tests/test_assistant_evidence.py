import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import AsyncMock, patch

from core.assistant import Assistant, Settings, UsageBudget, AssistantError
from core.assistant_policy import plan_question, relevant
from core.assistant_evidence import render_evidence


def tool_call(name, arguments=None):
    return {"content": None, "tool_calls": [{"id": "c1", "type": "function", "function": {
        "name": name, "arguments": json.dumps(arguments if arguments is not None else {})}}]}


class PolicyTests(unittest.TestCase):
    def test_query_normalization_keeps_entities_and_date(self):
        self.assertEqual(plan_question('busca que paso el 9 de diciembre de 2018 dale rapidito').query,
                         'que paso el 9 de diciembre de 2018')

    def test_identity_fees_not_confused_with_doxxing(self):
        self.assertFalse(plan_question('cuanto sale el DNI argentino').reply)
        for q in ('busca en dateas una persona', 'dame la IP de alguien', 'todos los datos de alguien'):
            self.assertTrue(plan_question(q).reply)

    def test_relevant_is_neutral_everything_passes(self):
        plan = plan_question('cuanto esta el dolar')
        self.assertTrue(relevant({'title': 'Cualquier cosa', 'content': 'x'}, plan))


class EvidenceTests(unittest.TestCase):
    sources = [{'url': 'https://example.com', 'content': 'Pasaporte regular: $100.000. Pasaporte express: $200.000.'}]

    def payload(self, quote, **kwargs):
        return json.dumps({'status': 'answer', 'evidence': [{'source': 1, 'quote': quote, **kwargs}]})

    def test_exact_evidence_and_harness_links(self):
        result = render_evidence(self.payload('Pasaporte regular: $100.000.'), self.sources)
        self.assertIn('$100.000', result)
        self.assertIn('[1] <https://example.com>', result)

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

    async def test_search_returns_sanitized_sources_without_extra_calls(self):
        with patch('core.assistant.post_json', new_callable=AsyncMock) as post:
            post.return_value = {'results': [
                {'url': 'file:///etc/passwd'},
                {'url': 'https://example.com/mu', 'content': 'MU 99b guía original'},
                {'url': 'https://facebook.com/injected', 'content': 'red social bloqueada'}]}
            sources = await self.agent.search('guia MU 99b')
            payload = post.call_args.args[3]
            self.assertEqual(payload['query'], 'guia MU 99b')
            self.assertEqual(payload['search_depth'], 'basic')
            self.assertEqual([s['url'] for s in sources], ['https://example.com/mu'])
            post.assert_awaited_once()
            # The budget is charged by web_research, not by a direct search call.
            self.assertFalse((self.agent.budget.path).exists())

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
        await self.agent.answer('busca dateas persona', lambda **args: self.fail('no metrics'))
        self.agent.completion.assert_not_called()
        self.agent.search.assert_not_called()

    async def test_insufficient_validated_in_web_flow_after_stale_dollar_memory(self):
        self.agent.completion = AsyncMock(return_value={'content': json.dumps({'status': 'answer', 'evidence': [
            {'source': 1, 'quote': 'Dato actual confirmado'}]})})
        self.agent.search = AsyncMock(return_value=[{'url': 'https://example.com', 'content': 'Dato actual confirmado'}])
        result = await self.agent.answer('cuanto esta el dolar', lambda **a: {}, conversation_key=(1, 2, 3))
        self.assertIn('Dato actual confirmado', result)
        # La memoria queda aislada por persona/canal: otra persona no ve nada.
        self.assertEqual(self.agent.memory.read((1, 2, 4)), [])

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

    async def test_memory_stays_local_and_never_reaches_the_search(self):
        key = (1, 2, 3)
        self.agent.memory.remember(key, 'Anterior tema personal', 'Anterior respuesta incorrecta')
        source = {'url': 'https://example.com', 'content': 'River ganó la final de 2018.'}
        self.agent.search = AsyncMock(return_value=[source])
        self.agent.completion = AsyncMock(side_effect=[
            tool_call('search_web', {}),
            {'content': json.dumps({'status': 'answer', 'evidence': [
                {'source': 1, 'quote': 'River ganó la final de 2018.'}]})}])
        await self.agent.answer('que paso el 9 de diciembre de 2018', lambda **a: {}, conversation_key=key)
        # El agente tiene memoria en su contexto, pero la búsqueda es autosuficiente:
        # el tema privado entra como cita a ninguna URL.
        self.agent.search.assert_awaited_once_with('que paso el 9 de diciembre de 2018')
        # El claim web tampoco se recicla en memoria.
        self.assertNotIn('River', json.dumps(self.agent.memory.read(key)))

    async def test_invalid_output_retry_once_then_fail_closed(self):
        self.agent.search = AsyncMock(return_value=[{'url': 'https://example.com', 'content': 'River ganó la final.'}])
        self.agent.completion = AsyncMock(side_effect=[
            tool_call('search_web', {}),
            {'content': 'Argentina ganó Mundial 2018'},
            {'content': 'Argentina ganó Mundial 2018'}])
        result = await self.agent.answer('que paso el 9 de diciembre de 2018', lambda **a: {})
        self.assertIn('no voy a publicar datos inventados', result)
        self.assertNotIn('Argentina ganó', result)
        self.assertEqual(self.agent.completion.await_count, 3)
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
