import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from core.updates import format_latest_update_for_deploy, load_update_sections


class UpdatesTests(unittest.TestCase):
    def test_deploy_notice_uses_newest_section_and_respects_limit(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'UPDATES.md'
            path.write_text(
                '# Updates\n\n## 2026-10-01 · Nuevo deploy\n\n'
                '- Asistente opcional, desactivado.\n- No redeploy duplicado.\n- Tercer detalle.\n\n'
                '## 2026-06-10 · Emuladores detectados\n\n- Novedad anterior.\n', encoding='utf-8')
            with patch('core.updates._default_updates_path', return_value=path):
                message = format_latest_update_for_deploy(max_items=2)
                self.assertIn('Nuevo deploy', message)
                self.assertIn('desactivado', message)
                self.assertNotIn('Emuladores detectados', message)
                self.assertNotIn('Tercer detalle', message)
                self.assertEqual(len(load_update_sections(limit=2)), 2)

    def test_missing_changelog_does_not_break_startup(self):
        with tempfile.TemporaryDirectory() as directory:
            with patch('core.updates._default_updates_path', return_value=Path(directory) / 'missing.md'):
                self.assertIsNone(format_latest_update_for_deploy())


if __name__ == '__main__':
    unittest.main()
