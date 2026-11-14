"""Señal de calidad por reacción: qué respuestas funcionaron y cuáles no.

El grupo no da feedback formal: reacciona. Un 👍 o una risa cuando la respuesta
sirvió, un 👎 o un 🤡 cuando no. Este módulo guarda **sólo agregados por
mensaje**: id del mensaje, cuántas reacciones buenas y malas, y un hash corto del
autor para no contar dos veces a la misma persona. Nunca guarda texto, nombres
ni el contenido de la reacción original.

Contrato:
- Sólo se registran ids que el bot marcó como respuesta propia (`track`).
- Un archivo corrupto carga como vacío; un fallo de escritura deja el store en
  modo lectura y no pierde lo ya cargado.
- Bounded: 400 respuestas, 40 votantes por respuesta, 24 emojis distintos.
"""

import hashlib
import json
import os
import time
from pathlib import Path

DATA_DIR = Path('/data') if Path('/data').exists() else Path('data')
MAX_ANSWERS = 400
MAX_VOTERS = 40
MAX_EMOJIS = 24
HASH_CHARS = 12

# Reacciones que el grupo usa de verdad. 😂 cuenta como positiva: se ríen
# *con* el bot; si se ríen *de* él, el 👎 o el 🤡 lo compensan.
POSITIVE = frozenset({'👍', '❤️', '❤', '😂', '🤣', '🔥', '💯', '🙌', '😎', '🫡', '👏'})
NEGATIVE = frozenset({'👎', '💩', '🤡', '🤮', '😡', '🤬', '🙄', '🥴'})


def default_path():
    override = os.getenv('FEEDBACK_PATH', '')
    return Path(override) if override else DATA_DIR / 'assistant_feedback.json'


def sentiment(emoji):
    """+1, -1 o 0 para un emoji (unicode o nombre de emoji custom)."""
    if not isinstance(emoji, str):
        return 0
    value = emoji.strip()
    if value in POSITIVE:
        return 1
    if value in NEGATIVE:
        return -1
    return 0


def _voter(user_id, salt):
    """Hash corto y estable: permite deduplicar sin guardar el id de Discord."""
    try:
        raw = (str(salt) + ':' + str(user_id)).encode('utf-8')
    except (UnicodeError, TypeError):
        return ''
    return hashlib.sha256(raw).hexdigest()[:HASH_CHARS]


def _empty():
    return {'version': 1, 'answers': {}, 'totals': {'up': 0, 'down': 0, 'answers': 0}}


class FeedbackStore:
    def __init__(self, path=None, clock=time.time, salt=None):
        self.path = Path(path) if path is not None else default_path()
        self.clock = clock
        self.salt = salt if salt is not None else os.getenv('FEEDBACK_SALT', 'boton')
        self.read_only = False
        self.data = _empty()
        self._load()

    # --- persistencia -----------------------------------------------------
    def _load(self):
        try:
            with open(self.path, encoding='utf-8') as handle:
                raw = json.load(handle)
        except (OSError, ValueError, TypeError):
            return
        if not isinstance(raw, dict):
            return
        answers = raw.get('answers')
        if not isinstance(answers, dict):
            return
        clean = {}
        for key, value in list(answers.items())[-MAX_ANSWERS:]:
            row = self._row(value)
            if row is not None and isinstance(key, str) and key.isdecimal():
                clean[key] = row
        totals = raw.get('totals') if isinstance(raw.get('totals'), dict) else {}
        self.data = {'version': 1, 'answers': clean,
                     'totals': {name: _count(totals.get(name)) for name in ('up', 'down', 'answers')}}
        if self.data['totals']['answers'] < len(clean):
            self.data['totals']['answers'] = len(clean)

    @staticmethod
    def _row(value):
        if not isinstance(value, dict):
            return None
        voters = value.get('voters')
        if not isinstance(voters, dict):
            voters = {}
        clean_voters = {key: int(vote) for key, vote in list(voters.items())[:MAX_VOTERS]
                        if isinstance(key, str) and len(key) <= HASH_CHARS
                        and vote in (1, -1)}
        return {'up': _count(value.get('up')), 'down': _count(value.get('down')),
                'ts': _count(value.get('ts')), 'voters': clean_voters}

    def _save(self):
        if self.read_only:
            return False
        temporary = str(self.path) + '.tmp'
        try:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            with open(temporary, 'w', encoding='utf-8') as handle:
                json.dump(self.data, handle, ensure_ascii=False, separators=(',', ':'))
            os.replace(temporary, self.path)
            return True
        except OSError:
            self.read_only = True
            try:
                os.unlink(temporary)
            except OSError:
                pass
            return False

    # --- escritura --------------------------------------------------------
    def track(self, message_id):
        """Marca una respuesta propia como observable. Idempotente."""
        key = _message_id(message_id)
        if key is None:
            return False
        if key in self.data['answers']:
            return True
        self.data['answers'][key] = {'up': 0, 'down': 0, 'ts': int(self.clock()), 'voters': {}}
        self.data['totals']['answers'] += 1
        while len(self.data['answers']) > MAX_ANSWERS:
            oldest = min(self.data['answers'], key=lambda item: self.data['answers'][item]['ts'])
            del self.data['answers'][oldest]
        return self._save()

    def knows(self, message_id):
        key = _message_id(message_id)
        return key is not None and key in self.data['answers']

    def record(self, message_id, emoji, user_id):
        """Suma una reacción. Devuelve 0 si no aplica, o el sentimiento aplicado."""
        key = _message_id(message_id)
        if key is None or key not in self.data['answers']:
            return 0
        weight = sentiment(emoji)
        if not weight:
            return 0
        voter = _voter(user_id, self.salt)
        if not voter:
            return 0
        row = self.data['answers'][key]
        previous = row['voters'].get(voter)
        if previous == weight:
            return 0
        # Cambiar de voto reemplaza el anterior; no infla el total.
        if previous is not None:
            row['up' if previous > 0 else 'down'] = max(0, row['up' if previous > 0 else 'down'] - 1)
            self.data['totals']['up' if previous > 0 else 'down'] = max(
                0, self.data['totals']['up' if previous > 0 else 'down'] - 1)
        elif len(row['voters']) >= MAX_VOTERS:
            return 0
        row['voters'][voter] = weight
        name = 'up' if weight > 0 else 'down'
        row[name] += 1
        self.data['totals'][name] += 1
        self._save()
        return weight

    def retract(self, message_id, emoji, user_id):
        """Quita un voto si la persona sacó su reacción. No toca otros votos."""
        key = _message_id(message_id)
        weight = sentiment(emoji)
        voter = _voter(user_id, self.salt)
        if key is None or not weight or not voter:
            return 0
        row = self.data['answers'].get(key)
        if row is None or row['voters'].get(voter) != weight:
            return 0
        del row['voters'][voter]
        name = 'up' if weight > 0 else 'down'
        row[name] = max(0, row[name] - 1)
        self.data['totals'][name] = max(0, self.data['totals'][name] - 1)
        self._save()
        return weight

    def forget(self, message_id):
        key = _message_id(message_id)
        if key is None or key not in self.data['answers']:
            return False
        row = self.data['answers'].pop(key)
        self.data['totals']['up'] = max(0, self.data['totals']['up'] - row['up'])
        self.data['totals']['down'] = max(0, self.data['totals']['down'] - row['down'])
        self.data['totals']['answers'] = max(0, self.data['totals']['answers'] - 1)
        return self._save()

    # --- lectura ----------------------------------------------------------
    def score(self, message_id):
        key = _message_id(message_id)
        row = self.data['answers'].get(key) if key else None
        if row is None:
            return None
        return row['up'] - row['down']

    def snapshot(self):
        """Agregados sin contenido: sirve para `!botonmetricas`."""
        answers = self.data['answers']
        voted = [row['up'] - row['down'] for row in answers.values()
                 if row['up'] or row['down']]
        return {
            'answers': len(answers),
            'voted': len(voted),
            'up': self.data['totals']['up'],
            'down': self.data['totals']['down'],
            'net': self.data['totals']['up'] - self.data['totals']['down'],
            'positive': sum(1 for value in voted if value > 0),
            'negative': sum(1 for value in voted if value < 0),
            'read_only': self.read_only,
            'volatile': False,
        }


def _count(value):
    if isinstance(value, bool) or not isinstance(value, int):
        return 0
    return max(0, value)


def _message_id(value):
    if isinstance(value, bool) or not isinstance(value, (int, str)):
        return None
    try:
        number = int(value)
    except (ValueError, TypeError):
        return None
    return str(number) if 0 < number < 2 ** 64 else None
