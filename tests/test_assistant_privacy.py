"""Synthetic local-only privacy fixtures; never inspect environment secrets."""

import json
from datetime import datetime, timezone
from types import SimpleNamespace

import pytest

from core.assistant_privacy import MAX_PRIVATE_CHARS, has_private_data, scrub_private
from core.assistant_history import _row_from
from core.banter_ledger import BanterLedger
from core.channel_curator import ChannelCurator


PRIVATE = [
    'sk-or-v1-fixture123456789', 'tvly-dev-fixture123456789',
    'gsk_fixture123456789', 'AIza' + 'a1' * 18,
    'A' * 24 + '.' + 'B' * 6 + '.' + 'C' * 30,
    'mfa.' + 'D' * 30, 'E9_' * 15,
    'password="fixture pass"', 'DISCORD_TOKEN=fixture',
    'api_key: fixture', 'AWS_SECRET_ACCESS_KEY=fixture',
    'Bearer syntheticfixture', 'github_pat_fixture123456789',
    'Authorization: Bearer private_auth', 'Authorization: Basic private_auth',
    '-----BEGIN PRIVATE KEY-----\nfixture\n-----END PRIVATE KEY-----',
    'ana.fixture+test@example.invalid',
    '+54 9 11 5555-1234', '(011) 4321-5678', '555-123-4567',
    'teléfono: 5551234', 'phone: 5551234567',
    'DNI: 12.345.678', 'mi DNI es 12345678', 'D.N.I. 12345678Z',
    'Mi dirección es Calle Falsa 123, piso 4, depto B',
    'domicilio: Av. Siempre Viva 742', 'vivo en Calle Inventada 456',
    'home address: 123 Fiction Lane, apartment 2',
    'I live at 123 Fiction Lane', 'dirección particular: Calle Falsa 123',
    'dirección: Calle Falsa 123',
]


@pytest.mark.parametrize('value', PRIVATE)
def test_recognises_and_scrubs_private_data(value):
    original = 'Apuesto por rojo; ' + value + '; seguimos la ronda'
    assert has_private_data(original)
    clean = scrub_private(original)
    assert value not in clean
    assert 'Apuesto por rojo' in clean
    assert not has_private_data(clean)
    assert scrub_private(clean) == clean
    assert len(clean) <= MAX_PRIVATE_CHARS


@pytest.mark.parametrize('value', [
    'Apuesto 20 pesos por rojo', 'precio $12345678', 'precio 12.345,67 pesos',
    '2026-10-29 12:30', 'marcador 12-34', 'round 12345678901234567890123456789',
    'factura 12345678', 'Calle Falsa 123', 'vivo en Buenos Aires',
    'la dirección del torneo es el norte', 'id 1234567890123456789',
    'palabra ' + 'a' * 500, 'x' * MAX_PRIVATE_CHARS,
], ids=lambda value: value[:60])
def test_not_a_general_number_address_or_trait_classifier(value):
    assert not has_private_data(value)
    assert scrub_private(value) == value


def test_bounds_are_fail_closed_and_inspection_precedes_truncation():
    for value in ('x' * (MAX_PRIVATE_CHARS + 1),
                  'x' * MAX_PRIVATE_CHARS + ' email: fixture@example.invalid',
                  'password=' + 'x' * (MAX_PRIVATE_CHARS + 1)):
        assert has_private_data(value)
        assert len(scrub_private(value)) < 100
        assert 'x' not in scrub_private(value)
    for value in (None, 123, {}, []):
        assert not has_private_data(value)
        assert scrub_private(value) == ''


def test_unicode_normalization_and_invisible_formatting():
    for value in ('ana@exam\u200bple.invalid', 'pass\u200bword=fixture',
                  'ＤＮＩ：１２３４５６７８'):
        assert has_private_data(value)
        assert not has_private_data(scrub_private(value))


@pytest.mark.parametrize('scheme', ['Bearer', 'Basic', 'bAsIc', 'bEaReR'])
@pytest.mark.parametrize('header', ['Authorization: {scheme} private_auth',
                                   'Authorization={scheme} private_auth',
                                   '"Authorization": "{scheme} private_auth"',
                                   'Authorization: {scheme} "private_auth fixture"'])
def test_authorization_scheme_never_leaves_the_payload_behind(scheme, header):
    value = header.format(scheme=scheme)
    assert has_private_data(value)
    clean = scrub_private(value)
    assert 'private_auth' not in clean
    assert scheme not in clean
    # Also preserve history's stronger, historical secret scrubbing and marker.
    message = SimpleNamespace(author=SimpleNamespace(display_name=value, bot=False),
                              created_at=datetime(2026, 10, 29, tzinfo=timezone.utc),
                              content='Apuesto por rojo; ' + value)
    row = _row_from(message)
    for field in ('autor', 'texto'):
        assert 'private_auth' not in row[field]
        assert '[secreto]' in row[field]


def test_history_scrubs_private_data_without_changing_public_shape():
    message = SimpleNamespace(
        id=1234567890123456789, channel=SimpleNamespace(id=987654321098765432),
        author=SimpleNamespace(display_name='ana@example.invalid', bot=False),
        created_at=datetime(2026, 10, 29, tzinfo=timezone.utc),
        content='Apuesto por rojo; DNI: 12.345.678; tel: 5551234')
    row = _row_from(message)
    assert set(row) == {'fecha', 'autor', 'texto'}
    assert not has_private_data(json.dumps(row, ensure_ascii=False))
    assert '1234567890123456789' not in json.dumps(row)


@pytest.mark.parametrize('value', PRIVATE)
@pytest.mark.parametrize('field', ['fecha', 'autor', 'texto'])
def test_curator_observation_rejects_all_private_fields(tmp_path, value, field):
    curator = ChannelCurator(tmp_path / 'curator.json', clock=lambda: 1000)
    row = {'fecha': '2026-10-29 12:30', 'autor': 'Ana', 'texto': 'Apuesto por rojo'}
    row[field] = value
    assert not curator.observe(row)
    assert not curator._pending
    assert curator.pending_count == 0


@pytest.mark.parametrize('value', PRIVATE)
@pytest.mark.parametrize('field', ['user', 'what', 'label'])
def test_ledger_rejects_private_fields_on_add_and_load(tmp_path, value, field):
    path = tmp_path / 'banter.json'
    ledger = BanterLedger(path, clock=lambda: 1000)
    entry = {'user': 'Ana', 'what': 'apostó por rojo', 'label': 'apuesta'}
    entry[field] = value
    assert ledger.add(**entry) is None
    assert ledger.recall() == []
    path.write_text(json.dumps({'version': 2, 'entries': [dict(entry, ts=1000)]}), encoding='utf-8')
    loaded = BanterLedger(path, clock=lambda: 1000)
    assert loaded.recall() == []
    assert json.loads(path.read_text(encoding='utf-8'))['entries'] == []


@pytest.mark.parametrize('what', [
    'Ana es irresponsable', 'siempre apuesta', 'Ana nunca aprende',
    'religión de Ana: privada', 'Ana tiene diabetes', 'su género es privado',
    'perfil de personalidad: impulsiva', 'Ana is gay', 'soy impulsiva', 'I am reckless',
])
def test_ledger_never_retains_profiles(tmp_path, what):
    path = tmp_path / 'banter.json'
    ledger = BanterLedger(path, clock=lambda: 1000)
    assert ledger.add('Ana', what) is None
    path.write_text(json.dumps({'version': 2, 'entries': [
        {'user': 'Ana', 'what': what, 'label': 'chiste', 'ts': 1000}]}), encoding='utf-8')
    assert BanterLedger(path, clock=lambda: 1000).recall() == []


def test_private_tail_beyond_storage_field_cap_is_still_rejected(tmp_path):
    ledger = BanterLedger(tmp_path / 'banter.json', clock=lambda: 1000)
    assert ledger.add('Ana', 'palabras ' * 100 + 'dni: 12345678') is None
    curator = ChannelCurator(tmp_path / 'curator.json', clock=lambda: 1000)
    assert not curator.observe({'fecha': 'hoy', 'autor': 'Ana',
                                'texto': 'palabras ' * 200 + 'ana@example.invalid'})
