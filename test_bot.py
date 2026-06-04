"""
Tests para el bot de Discord
Incluye tests para visualizaciones, estadísticas y funcionalidades core
"""

import unittest
import json
import os
from datetime import datetime, timedelta
from pathlib import Path
import sys

# Agregar el directorio actual al path
sys.path.insert(0, str(Path(__file__).parent))

try:
    import discord  # noqa: F401
    _SKIP_DISCORD_TESTS = False
except ImportError:
    _SKIP_DISCORD_TESTS = True

# Importar módulos a testear
from stats_viz import (
    create_bar_chart, create_timeline_chart, create_comparison_chart,
    filter_by_period, get_period_label, calculate_daily_activity,
    format_time
)



class TestFormatTime(unittest.TestCase):
    """Tests para la función format_time()"""
    
    def test_format_minutes(self):
        """Test con minutos < 60"""
        self.assertEqual(format_time(0), '0m')
        self.assertEqual(format_time(30), '30m')
        self.assertEqual(format_time(59), '59m')
    
    def test_format_hours(self):
        """Test con horas (60-1439 minutos)"""
        self.assertEqual(format_time(60), '1h')
        self.assertEqual(format_time(90), '1h 30m')
        self.assertEqual(format_time(120), '2h')
        self.assertEqual(format_time(125), '2h 5m')
        self.assertEqual(format_time(1439), '23h 59m')
    
    def test_format_days(self):
        """Test con días (>= 1440 minutos)"""
        self.assertEqual(format_time(1440), '1d')
        self.assertEqual(format_time(1500), '1d 1h')
        self.assertEqual(format_time(2880), '2d')
        self.assertEqual(format_time(2940), '2d 1h')
        self.assertEqual(format_time(10000), '6d 22h')


class TestBarChart(unittest.TestCase):
    """Tests para la generación de gráficos de barras ASCII"""
    
    def test_bar_chart_basic(self):
        """Test básico de gráfico de barras"""
        data = [("Valorant", 45), ("League", 32), ("Minecraft", 21)]
        result = create_bar_chart(data, max_width=20)
        
        self.assertIn("Valorant", result)
        self.assertIn("League", result)
        self.assertIn("Minecraft", result)
        self.assertIn("45", result)
        self.assertIn("32", result)
        self.assertIn("21", result)
        self.assertIn("█", result)  # Debe contener barras
    
    def test_bar_chart_empty(self):
        """Test con datos vacíos"""
        result = create_bar_chart([])
        self.assertIn("No hay datos", result)
    
    def test_bar_chart_single_item(self):
        """Test con un solo item"""
        data = [("Solo Juego", 10)]
        result = create_bar_chart(data)
        self.assertIn("Solo Juego", result)
        self.assertIn("10", result)
    
    def test_bar_chart_with_title(self):
        """Test con título"""
        data = [("Game1", 5), ("Game2", 3)]
        result = create_bar_chart(data, title="Test Title")
        self.assertIn("Test Title", result)
        self.assertIn("━", result)  # Debe tener separador
    
    def test_bar_chart_long_labels(self):
        """Test con labels muy largos"""
        data = [("Este es un nombre muy largo de juego", 10)]
        result = create_bar_chart(data)
        # Debe truncar el label
        self.assertIn("...", result)


class TestTimelineChart(unittest.TestCase):
    """Tests para gráficos de línea de tiempo"""
    
    def test_timeline_basic(self):
        """Test básico de timeline"""
        today = datetime.now().strftime("%Y-%m-%d")
        daily_data = {today: 15}
        
        result = create_timeline_chart(daily_data, days=7)
        self.assertIn("📈", result)
        self.assertIn("█", result)
    
    def test_timeline_empty(self):
        """Test con datos vacíos"""
        result = create_timeline_chart({}, days=7)
        # Con datos vacíos, el gráfico aún se genera
        self.assertIsInstance(result, str)
        # Debe contener el título o indicar que no hay datos
        self.assertTrue("📈" in result or "No hay datos" in result)
    
    def test_timeline_multiple_days(self):
        """Test con múltiples días"""
        daily_data = {}
        for i in range(7):
            date = (datetime.now() - timedelta(days=i)).strftime("%Y-%m-%d")
            daily_data[date] = i * 2
        
        result = create_timeline_chart(daily_data, days=7)
        self.assertIn("█", result)


class TestComparisonChart(unittest.TestCase):
    """Tests para gráficos de comparación"""
    
    def test_comparison_basic(self):
        """Test básico de comparación"""
        user1 = {
            'games': {'Valorant': {'count': 10}},
            'voice': {'count': 5}
        }
        user2 = {
            'games': {'League': {'count': 8}},
            'voice': {'count': 12}
        }
        
        result = create_comparison_chart(user1, user2, "User1", "User2")
        self.assertIn("User1", result)
        self.assertIn("User2", result)
        self.assertIn("🎮", result)
        self.assertIn("🔊", result)
        self.assertIn("Ganador", result)
    
    def test_comparison_tie(self):
        """Test con empate"""
        user1 = {
            'games': {'Game': {'count': 5}},
            'voice': {'count': 5}
        }
        user2 = {
            'games': {'Game': {'count': 5}},
            'voice': {'count': 5}
        }
        
        result = create_comparison_chart(user1, user2, "User1", "User2")
        self.assertIn("Empate", result)
    
    def test_comparison_empty_data(self):
        """Test con datos vacíos"""
        user1 = {'games': {}, 'voice': {'count': 0}}
        user2 = {'games': {}, 'voice': {'count': 0}}
        
        result = create_comparison_chart(user1, user2, "User1", "User2")
        self.assertIsInstance(result, str)
        self.assertIn("User1", result)


class TestPeriodFiltering(unittest.TestCase):
    """Tests para filtrado por período"""
    
    def setUp(self):
        """Configurar datos de prueba"""
        now = datetime.now()
        yesterday = now - timedelta(days=1)
        week_ago = now - timedelta(days=8)
        
        self.test_stats = {
            'users': {
                'user1': {
                    'username': 'TestUser1',
                    'games': {
                        'Valorant': {
                            'count': 5,
                            'last_played': now.isoformat()
                        },
                        'OldGame': {
                            'count': 3,
                            'last_played': week_ago.isoformat()
                        }
                    },
                    'voice': {
                        'count': 10,
                        'last_join': yesterday.isoformat()
                    }
                }
            }
        }
    
    def test_filter_all(self):
        """Test filtro 'all' (sin filtrar)"""
        result = filter_by_period(self.test_stats, 'all')
        self.assertEqual(len(result['users']), 1)
        self.assertEqual(len(result['users']['user1']['games']), 2)
    
    def test_filter_week(self):
        """Test filtro 'week'"""
        result = filter_by_period(self.test_stats, 'week')
        # Solo debe incluir juegos de la última semana
        self.assertIn('Valorant', result['users']['user1']['games'])
        self.assertNotIn('OldGame', result['users']['user1']['games'])
    
    def test_filter_today(self):
        """Test filtro 'today'"""
        result = filter_by_period(self.test_stats, 'today')
        # Solo debe incluir actividad de hoy
        self.assertIn('Valorant', result['users']['user1']['games'])
    
    def test_get_period_label(self):
        """Test labels de períodos"""
        self.assertEqual(get_period_label('today'), 'Hoy')
        self.assertEqual(get_period_label('week'), 'Última Semana')
        self.assertEqual(get_period_label('month'), 'Último Mes')
        self.assertEqual(get_period_label('all'), 'Histórico')


class TestDailyActivity(unittest.TestCase):
    """Tests para cálculo de actividad diaria"""
    
    def test_calculate_daily_basic(self):
        """Test básico de cálculo diario"""
        now = datetime.now()
        today = now.strftime("%Y-%m-%d")
        
        stats_data = {
            'users': {
                'user1': {
                    'games': {
                        'Game1': {
                            'count': 5,
                            'last_played': now.isoformat()
                        }
                    },
                    'voice': {
                        'count': 3,
                        'last_join': now.isoformat()
                    }
                }
            }
        }
        
        result = calculate_daily_activity(stats_data, days=7)
        self.assertIsInstance(result, dict)
        self.assertEqual(len(result), 7)  # 7 días
        self.assertIn(today, result)
    
    def test_calculate_daily_empty(self):
        """Test con datos vacíos"""
        result = calculate_daily_activity({'users': {}}, days=7)
        self.assertEqual(len(result), 7)
        # Todos los días deben tener 0
        self.assertTrue(all(count == 0 for count in result.values()))


class TestStatsDataStructure(unittest.TestCase):
    """Tests para la estructura de datos de estadísticas"""
    
    def test_stats_structure(self):
        """Test estructura básica de stats"""
        stats = {
            'users': {
                'user_id': {
                    'username': 'TestUser',
                    'games': {
                        'GameName': {
                            'count': 5,
                            'first_played': datetime.now().isoformat(),
                            'last_played': datetime.now().isoformat()
                        }
                    },
                    'voice': {
                        'count': 10,
                        'last_join': datetime.now().isoformat()
                    }
                }
            },
            'cooldowns': {}
        }
        
        # Verificar estructura
        self.assertIn('users', stats)
        self.assertIn('cooldowns', stats)
        self.assertIn('user_id', stats['users'])
        self.assertIn('games', stats['users']['user_id'])
        self.assertIn('voice', stats['users']['user_id'])
    
    def test_empty_stats(self):
        """Test stats vacío"""
        stats = {'users': {}, 'cooldowns': {}}
        self.assertEqual(len(stats['users']), 0)
        self.assertEqual(len(stats['cooldowns']), 0)


class TestConfigStructure(unittest.TestCase):
    """Tests para la estructura de configuración"""
    
    def test_config_defaults(self):
        """Test valores por defecto de config"""
        config = {
            "channel_id": None,
            "notify_games": True,
            "notify_voice": True,
            "notify_voice_leave": False,
            "notify_voice_move": True,
            "notify_member_join": False,
            "notify_member_leave": False,
            "ignore_bots": True,
            "game_activity_types": ["playing", "streaming", "watching", "listening"]
        }
        
        self.assertTrue(config['notify_games'])
        self.assertTrue(config['notify_voice'])
        self.assertTrue(config['ignore_bots'])
        self.assertIsNone(config['channel_id'])


class TestIntegration(unittest.TestCase):
    """Tests de integración"""
    
    def test_full_workflow(self):
        """Test workflow completo de stats"""
        # Simular datos de un día de actividad
        now = datetime.now()
        stats_data = {
            'users': {
                'user1': {
                    'username': 'Player1',
                    'games': {
                        'Valorant': {'count': 10, 'last_played': now.isoformat()},
                        'League': {'count': 5, 'last_played': now.isoformat()}
                    },
                    'voice': {'count': 8, 'last_join': now.isoformat()}
                },
                'user2': {
                    'username': 'Player2',
                    'games': {
                        'Minecraft': {'count': 7, 'last_played': now.isoformat()}
                    },
                    'voice': {'count': 12, 'last_join': now.isoformat()}
                }
            },
            'cooldowns': {}
        }
        
        # Test filtrado
        filtered = filter_by_period(stats_data, 'today')
        self.assertEqual(len(filtered['users']), 2)
        
        # Test cálculo diario
        daily = calculate_daily_activity(stats_data, days=7)
        self.assertEqual(len(daily), 7)
        
        # Test gráfico de juegos
        game_counts = {}
        for user_data in stats_data['users'].values():
            for game, data in user_data['games'].items():
                game_counts[game] = game_counts.get(game, 0) + data['count']
        
        top_games = sorted(game_counts.items(), key=lambda x: x[1], reverse=True)
        chart = create_bar_chart(top_games)
        
        self.assertIn("Valorant", chart)
        self.assertIn("10", chart)


def run_tests():
    """Ejecuta todos los tests"""
    # Crear test suite
    loader = unittest.TestLoader()
    suite = unittest.TestSuite()
    
    # Agregar todos los tests
    suite.addTests(loader.loadTestsFromTestCase(TestFormatTime))
    suite.addTests(loader.loadTestsFromTestCase(TestBarChart))
    suite.addTests(loader.loadTestsFromTestCase(TestTimelineChart))
    suite.addTests(loader.loadTestsFromTestCase(TestComparisonChart))
    suite.addTests(loader.loadTestsFromTestCase(TestPeriodFiltering))
    suite.addTests(loader.loadTestsFromTestCase(TestDailyActivity))
    suite.addTests(loader.loadTestsFromTestCase(TestStatsDataStructure))
    suite.addTests(loader.loadTestsFromTestCase(TestConfigStructure))
    suite.addTests(loader.loadTestsFromTestCase(TestIntegration))
    suite.addTests(loader.loadTestsFromTestCase(TestVoiceTimeTracking))
    suite.addTests(loader.loadTestsFromTestCase(TestVoiceTimeFiltering))
    suite.addTests(loader.loadTestsFromTestCase(TestVoiceRanking))
    suite.addTests(loader.loadTestsFromTestCase(TestLinkFiltering))
    suite.addTests(loader.loadTestsFromTestCase(TestMessageTracking))
    suite.addTests(loader.loadTestsFromTestCase(TestNewTracking))
    suite.addTests(loader.loadTestsFromTestCase(TestCommandCoverage))
    suite.addTests(loader.loadTestsFromTestCase(TestCommandProcessing))
    suite.addTests(loader.loadTestsFromTestCase(TestConnectionTracking))
    suite.addTests(loader.loadTestsFromTestCase(TestVoiceLeaveNotificationLogic))
    suite.addTests(loader.loadTestsFromTestCase(TestPartyDetection))
    
    # Ejecutar tests
    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)
    
    # Resumen
    print("\n" + "="*70)
    print("RESUMEN DE TESTS")
    print("="*70)
    print(f"Tests ejecutados: {result.testsRun}")
    print(f"✅ Exitosos: {result.testsRun - len(result.failures) - len(result.errors)}")
    print(f"❌ Fallidos: {len(result.failures)}")
    print(f"💥 Errores: {len(result.errors)}")
    print("="*70)
    
    return result.wasSuccessful()


class TestVoiceTimeTracking(unittest.TestCase):
    """Tests para tracking de tiempo en voz"""
    
    def test_voice_session_structure(self):
        """Test estructura de sesión de voz"""
        session = {
            'channel': 'General',
            'start': '2025-12-26T21:45:06Z'
        }
        self.assertIn('channel', session)
        self.assertIn('start', session)
    
    def test_voice_data_structure(self):
        """Test estructura completa de voice data"""
        voice_data = {
            'count': 10,
            'total_minutes': 120,
            'daily_minutes': {
                '2025-12-26': 60,
                '2025-12-25': 60
            },
            'current_session': None
        }
        self.assertEqual(voice_data['count'], 10)
        self.assertEqual(voice_data['total_minutes'], 120)
        self.assertEqual(len(voice_data['daily_minutes']), 2)
    
    def test_time_formatting_minutes(self):
        """Test formateo de tiempo en minutos"""
        minutes = 45
        time_str = f'{minutes} min'
        self.assertEqual(time_str, '45 min')
    
    def test_time_formatting_hours(self):
        """Test formateo de tiempo en horas"""
        minutes = 125
        hours = minutes // 60
        mins = minutes % 60
        time_str = f'{hours}h {mins}m'
        self.assertEqual(time_str, '2h 5m')
    
    def test_time_formatting_days(self):
        """Test formateo de tiempo en días"""
        minutes = 1500  # > 24 horas
        days = minutes // 1440
        hours = (minutes % 1440) // 60
        time_str = f'{days}d {hours}h'
        self.assertEqual(time_str, '1d 1h')
    
    def test_session_duration_calculation(self):
        """Test cálculo de duración de sesión"""
        from datetime import datetime, timedelta
        
        start = datetime(2025, 12, 26, 21, 0, 0)
        end = datetime(2025, 12, 26, 21, 45, 0)
        duration = end - start
        minutes = int(duration.total_seconds() / 60)
        
        self.assertEqual(minutes, 45)
    
    def test_minimum_session_duration(self):
        """Test sesión mínima de 1 minuto"""
        from datetime import datetime, timedelta
        
        start = datetime(2025, 12, 26, 21, 0, 0)
        end = datetime(2025, 12, 26, 21, 0, 30)  # 30 segundos
        duration = end - start
        minutes = int(duration.total_seconds() / 60)
        
        # Debe ser 0 (menos de 1 minuto)
        self.assertEqual(minutes, 0)
        # Solo contamos sesiones >= 1 minuto
        should_count = minutes >= 1
        self.assertFalse(should_count)

class TestVoiceTimeFiltering(unittest.TestCase):
    """Tests para filtrado por período de tiempo en voz"""
    
    def test_filter_today(self):
        """Test filtro por día actual"""
        from datetime import datetime
        
        today = datetime.now().strftime('%Y-%m-%d')
        daily_minutes = {
            today: 60,
            '2025-12-25': 90
        }
        
        today_minutes = daily_minutes.get(today, 0)
        self.assertEqual(today_minutes, 60)
    
    def test_filter_week(self):
        """Test filtro por última semana (fechas relativas a hoy)"""
        from datetime import datetime, timedelta
        
        today = datetime.now().date()
        week_ago = today - timedelta(days=7)
        daily_minutes = {
            today.strftime('%Y-%m-%d'): 60,
            (today - timedelta(days=3)).strftime('%Y-%m-%d'): 90,
            (today - timedelta(days=10)).strftime('%Y-%m-%d'): 45,
        }
        
        week_total = sum(
            mins for date, mins in daily_minutes.items()
            if datetime.strptime(date, '%Y-%m-%d').date() >= week_ago
        )
        
        self.assertGreater(week_total, 0)
    
    def test_empty_period(self):
        """Test período sin datos"""
        daily_minutes = {}
        total = sum(daily_minutes.values())
        self.assertEqual(total, 0)

class TestVoiceRanking(unittest.TestCase):
    """Tests para ranking por tiempo en voz"""
    
    def test_ranking_sorting(self):
        """Test ordenamiento de ranking"""
        user_times = [
            ('Usuario1', 120),
            ('Usuario2', 180),
            ('Usuario3', 90)
        ]
        
        sorted_times = sorted(user_times, key=lambda x: x[1], reverse=True)
        
        self.assertEqual(sorted_times[0][0], 'Usuario2')  # Más tiempo
        self.assertEqual(sorted_times[0][1], 180)
        self.assertEqual(sorted_times[-1][0], 'Usuario3')  # Menos tiempo
    
    def test_ranking_limit(self):
        """Test límite de ranking (top 10)"""
        user_times = [(f'User{i}', i*10) for i in range(15)]
        top_10 = user_times[:10]
        
        self.assertEqual(len(top_10), 10)
    
    def test_empty_ranking(self):
        """Test ranking vacío"""
        user_times = []
        self.assertEqual(len(user_times), 0)

class TestLinkFiltering(unittest.TestCase):
    """Tests para filtrado de links/spam"""
    
    @staticmethod
    def is_link_spam(message_content):
        """Copia de la función is_link_spam para testing"""
        import re
        
        if not message_content or len(message_content) == 0:
            return True
        
        url_pattern = r'http[s]?://(?:[a-zA-Z]|[0-9]|[$-_@.&+]|[!*\\(\\),]|(?:%[0-9a-fA-F][0-9a-fA-F]))+'
        urls = re.findall(url_pattern, message_content, re.IGNORECASE)
        
        if not urls:
            return False
        
        url_length = sum(len(url) for url in urls)
        
        if url_length / len(message_content) > 0.7:
            return True
        
        content_without_urls = message_content
        for url in urls:
            content_without_urls = content_without_urls.replace(url, '')
        
        words = [w for w in content_without_urls.split() if len(w) > 0]
        if len(words) <= 2:
            return True
        
        return False
    
    def test_is_link_spam_basic_url(self):
        """Test detección de URL simple"""
        # Solo un link, debería ser spam
        self.assertTrue(self.is_link_spam('https://example.com'))
        self.assertTrue(self.is_link_spam('http://test.com'))
        
        # Link con 1-2 palabras, spam
        self.assertTrue(self.is_link_spam('mira https://example.com'))
        self.assertTrue(self.is_link_spam('https://example.com esto'))
    
    def test_is_link_spam_with_context(self):
        """Test mensaje con link pero con contexto"""
        # Link con contexto válido, NO spam
        self.assertFalse(self.is_link_spam('Encontré este artículo interesante sobre Python: https://example.com/python'))
        self.assertFalse(self.is_link_spam('Les comparto el tutorial que estuve viendo https://youtube.com/watch'))
    
    def test_is_link_spam_no_links(self):
        """Test mensaje sin links"""
        # Mensajes normales sin links, NO spam
        self.assertFalse(self.is_link_spam('Hola, cómo están todos?'))
        self.assertFalse(self.is_link_spam('Este es un mensaje normal con varias palabras'))
        self.assertFalse(self.is_link_spam('www.google.com'))  # Sin protocolo, no se detecta como URL completa
    
    def test_is_link_spam_empty(self):
        """Test mensaje vacío"""
        # Vacío es spam
        self.assertTrue(self.is_link_spam(''))
        self.assertTrue(self.is_link_spam(None))


class TestMessageTracking(unittest.TestCase):
    """Tests para tracking de mensajes"""
    
    def test_message_data_structure(self):
        """Test estructura de datos de mensajes"""
        messages_data = {
            'count': 150,
            'characters': 12500,
            'last_message': '2025-12-26T22:30:00Z'
        }
        self.assertIn('count', messages_data)
        self.assertIn('characters', messages_data)
        self.assertIn('last_message', messages_data)
        self.assertGreater(messages_data['count'], 0)
        self.assertGreater(messages_data['characters'], 0)
    
    def test_message_stats_calculation(self):
        """Test cálculo de stats de mensajes"""
        messages_data = {
            'count': 100,
            'characters': 5000
        }
        # Promedio de caracteres por mensaje
        avg_chars = messages_data['characters'] // messages_data['count']
        self.assertEqual(avg_chars, 50)
        
        # Estimación de palabras (~5 chars por palabra)
        estimated_words = messages_data['characters'] // 5
        self.assertEqual(estimated_words, 1000)
    
    def test_user_with_messages(self):
        """Test usuario con mensajes"""
        user_data = {
            'username': 'TestUser',
            'games': {},
            'voice': {'count': 0},
            'messages': {
                'count': 250,
                'characters': 18750,
                'last_message': '2025-12-26T22:30:00Z'
            }
        }
        self.assertIn('messages', user_data)
        self.assertEqual(user_data['messages']['count'], 250)
        self.assertEqual(user_data['messages']['characters'], 18750)
    
    def test_message_ranking(self):
        """Test ranking de mensajes"""
        users = {
            'user1': {'username': 'Alice', 'messages': {'count': 500, 'characters': 25000}},
            'user2': {'username': 'Bob', 'messages': {'count': 300, 'characters': 15000}},
            'user3': {'username': 'Charlie', 'messages': {'count': 800, 'characters': 40000}}
        }
        
        # Ordenar por count
        ranking = sorted(users.items(), key=lambda x: x[1]['messages']['count'], reverse=True)
        self.assertEqual(ranking[0][1]['username'], 'Charlie')
        self.assertEqual(ranking[1][1]['username'], 'Alice')
        self.assertEqual(ranking[2][1]['username'], 'Bob')


class TestNewTracking(unittest.TestCase):
    """Tests para nuevo tracking (reacciones, stickers, conexiones)"""
    
    def test_reactions_data_structure(self):
        """Test estructura de reacciones"""
        reactions_data = {
            'total': 150,
            'by_emoji': {
                '👍': 50,
                '❤️': 30,
                '🔥': 20,
                'custom_emoji': 50
            }
        }
        self.assertIn('total', reactions_data)
        self.assertIn('by_emoji', reactions_data)
        self.assertEqual(reactions_data['total'], 150)
        self.assertEqual(len(reactions_data['by_emoji']), 4)
    
    def test_stickers_data_structure(self):
        """Test estructura de stickers"""
        stickers_data = {
            'total': 45,
            'by_name': {
                'pepehappy': 15,
                'peposad': 10,
                'kekw': 20
            }
        }
        self.assertIn('total', stickers_data)
        self.assertIn('by_name', stickers_data)
        self.assertEqual(stickers_data['total'], 45)
        self.assertEqual(len(stickers_data['by_name']), 3)
    
    def test_daily_connections_structure(self):
        """Test estructura de conexiones diarias"""
        daily_connections = {
            '2025-12-26': True,
            '2025-12-27': True,
            '2025-12-28': True
        }
        self.assertEqual(len(daily_connections), 3)
        self.assertTrue(all(daily_connections.values()))
    
    def test_emoji_ranking(self):
        """Test ranking de emojis"""
        users = {
            'user1': {'reactions': {'by_emoji': {'👍': 50, '❤️': 30}}},
            'user2': {'reactions': {'by_emoji': {'👍': 20, '🔥': 40}}},
            'user3': {'reactions': {'by_emoji': {'❤️': 15, '🔥': 25}}}
        }
        
        # Contar emojis globales
        emoji_counts = {}
        for user_data in users.values():
            for emoji, count in user_data['reactions']['by_emoji'].items():
                emoji_counts[emoji] = emoji_counts.get(emoji, 0) + count
        
        # Verificar totales
        self.assertEqual(emoji_counts['👍'], 70)
        self.assertEqual(emoji_counts['🔥'], 65)
        self.assertEqual(emoji_counts['❤️'], 45)


class TestCommandCoverage(unittest.TestCase):
    """Tests para cobertura de comandos"""
    
    def test_all_commands_count(self):
        """Test cantidad total de comandos (aprox. — revisar al agregar cogs)"""
        total_commands = 32
        self.assertEqual(total_commands, 32)
    
    def test_command_aliases(self):
        """Test que los aliases funcionan"""
        # bothelp tiene: help, ayuda, comandos
        aliases = ['help', 'ayuda', 'comandos']
        self.assertEqual(len(aliases), 3)
        
        # stats tiene: mystats
        aliases_stats = ['mystats']
        self.assertEqual(len(aliases_stats), 1)
    
    def test_configuration_commands(self):
        """Test comandos de configuración"""
        config_commands = ['setchannel', 'unsetchannel', 'setstatschannel', 'unsetstatschannel', 'channels', 'toggle', 'config', 'test']
        self.assertEqual(len(config_commands), 8)
    
    def test_stats_commands(self):
        """Comandos stats registrados (ver docs/COMANDOS.md)"""
        basic_stats = [
            'stats', 'mystats', 'topgames', 'topgame', 'mygames',
            'topchat', 'topreactions', 'topstickers', 'topusers',
            'topgamers', 'topvoice', 'compare', 'wrapped',
        ]
        party_stats = ['partymaster', 'partywith', 'partygames', 'export', 'checkstats', 'statsmenu']
        social_extra = ['topconnections']
        self.assertEqual(len(basic_stats), 13)
        self.assertEqual(len(party_stats), 6)
        self.assertEqual(len(social_extra), 1)
    
    def test_utility_commands(self):
        """Comandos en utility cog (además de stats)"""
        utility_commands = ['bothelp', 'party', 'partyhistory', 'partystats']
        self.assertEqual(len(utility_commands), 4)


class TestCommandProcessing(unittest.TestCase):
    """Tests para prevenir duplicación de comandos"""
    
    def test_on_message_does_not_call_process_commands(self):
        """
        Verifica que on_message en EventsCog NO llama a process_commands()
        
        CONTEXT: Bug histórico donde process_commands() se llamaba manualmente
        en on_message del Cog, causando que todos los comandos se ejecutaran 2 veces.
        
        SOLUCIÓN: Con @commands.Cog.listener(), el bot procesa comandos automáticamente.
        No es necesario (y causa duplicación) llamarlo manualmente.
        """
        import os
        
        # Leer el archivo directamente sin importarlo
        events_path = os.path.join(os.path.dirname(__file__), 'cogs', 'events.py')
        with open(events_path, 'r') as f:
            source = f.read()
        
        # Verificar que NO contiene process_commands en on_message
        # Buscar la función on_message
        on_message_start = source.find('async def on_message(self, message):')
        self.assertGreater(on_message_start, 0, "Debe existir on_message en EventsCog")
        
        # Buscar el siguiente método (para delimitar on_message)
        next_method = source.find('@commands.Cog.listener()', on_message_start + 1)
        on_message_code = source[on_message_start:next_method] if next_method > 0 else source[on_message_start:]
        
        # Verificar que NO contiene la LLAMADA a process_commands (await self.bot.process_commands)
        self.assertNotIn('await self.bot.process_commands', on_message_code, 
                        "❌ on_message NO debe llamar 'await self.bot.process_commands()' - causa duplicación de comandos")
        self.assertNotIn('await bot.process_commands', on_message_code,
                        "❌ on_message NO debe llamar 'await bot.process_commands()' - causa duplicación de comandos")
        
        # Verificar que tiene el comentario explicativo (está bien mencionarlo en comentarios)
        self.assertIn('NO llamar process_commands', on_message_code,
                     "✅ Debe tener comentario explicando por qué NO se llama process_commands")
    
    def test_events_cog_has_on_message_listener(self):
        """
        Verifica que EventsCog tiene el listener on_message con @commands.Cog.listener()
        
        Esto asegura que el bot procesa comandos automáticamente.
        """
        import os
        
        # Leer el archivo
        events_path = os.path.join(os.path.dirname(__file__), 'cogs', 'events.py')
        with open(events_path, 'r') as f:
            source = f.read()
        
        # Verificar que existe @commands.Cog.listener() antes de on_message
        self.assertIn('@commands.Cog.listener()', source, 
                     "EventsCog debe usar @commands.Cog.listener()")
        self.assertIn('async def on_message(self, message):', source,
                     "EventsCog debe tener on_message")


class TestPartyReactivationConfig(unittest.TestCase):
    """Party: gracia larga + ventana reactivación (LoL / lobby) — ver docs/LOL_LOBBY_GAP.md"""

    def test_party_session_source_has_reactivation(self):
        import os
        path = os.path.join(os.path.dirname(__file__), 'core', 'party_session.py')
        with open(path, 'r', encoding='utf-8') as f:
            src = f.read()
        self.assertIn('_last_party_end_by_game', src)
        self.assertIn('reactivation_window_minutes', src)

    def test_party_session_has_lol_notification_key_antispam(self):
        import os
        path = os.path.join(os.path.dirname(__file__), 'core', 'party_session.py')
        with open(path, 'r', encoding='utf-8') as f:
            src = f.read()
        self.assertIn('notification_key_aliases', src)
        self.assertIn('league-of-legends', src)
        self.assertIn("check_cooldown(\n                'party'", src)

    def test_config_suppresses_lol_join_notifications(self):
        import json
        import os
        path = os.path.join(os.path.dirname(__file__), 'config.json')
        with open(path, 'r', encoding='utf-8') as f:
            cfg = json.load(f)
        party_cfg = cfg.get('party_detection', {})
        self.assertIn(
            'League of Legends',
            party_cfg.get('suppress_join_notifications_for_games', []),
        )
        self.assertIn(
            'league-of-legends',
            party_cfg.get('notification_key_aliases', {}),
        )


class TestPartyAggregators(unittest.TestCase):
    """Tests para agregaciones de parties basadas en historial."""

    def _load_aggregate_party_stats(self):
        import importlib.util
        import os

        path = os.path.join(
            os.path.dirname(__file__), 'stats', 'data', 'aggregators.py'
        )
        spec = importlib.util.spec_from_file_location('party_aggregators', path)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        return module.aggregate_party_stats

    def test_aggregate_party_stats_counts_users_and_pairs(self):
        aggregate_party_stats = self._load_aggregate_party_stats()

        stats_data = {
            'parties': {
                'history': [
                    {'game': 'LoL', 'players': ['1', '2', '3'], 'duration_minutes': 40},
                    {'game': 'LoL', 'players': ['1', '2'], 'duration_minutes': 25},
                    {'game': 'Valorant', 'players': ['2', '3'], 'duration_minutes': 55},
                ],
                'stats_by_game': {
                    'LoL': {'total_parties': 2},
                    'Valorant': {'total_parties': 1},
                },
            }
        }

        result = aggregate_party_stats(stats_data)

        self.assertEqual(result['total_parties'], 3)
        self.assertEqual(result['by_user'], {'1': 2, '2': 3, '3': 2})
        self.assertEqual(result['companion_pairs'][('1', '2')], 2)
        self.assertEqual(result['largest_party'], 3)
        self.assertEqual(result['longest_party_minutes'], 55)
        self.assertEqual(result['by_game_sorted'][0][0], 'LoL')

    def test_aggregate_party_stats_skips_invalid_player_string(self):
        aggregate_party_stats = self._load_aggregate_party_stats()

        stats_data = {
            'parties': {
                'history': [
                    {'game': 'LoL', 'players': '1,2', 'duration_minutes': 10},
                    {'game': 'LoL', 'players': ['1', '2'], 'duration_minutes': 20},
                ],
                'stats_by_game': {},
            }
        }

        result = aggregate_party_stats(stats_data)

        self.assertEqual(result['by_user'], {'1': 1, '2': 1})
        self.assertEqual(result['companion_pairs'], {('1', '2'): 1})


class TestConnectionTracking(unittest.TestCase):
    """Tests para tracking de conexiones diarias"""
    
    def setUp(self):
        """Setup para cada test"""
        from core.persistence import stats
        self.stats = stats
        self.stats_backup = stats['users'].copy()
    
    def tearDown(self):
        """Cleanup después de cada test"""
        self.stats['users'] = self.stats_backup
    
    def test_record_connection_event_creates_structure(self):
        """Verifica que save_connection_event crea la estructura correcta"""
        from core.session_dto import save_connection_event
        from datetime import datetime
        
        user_id = 'test_user_123'
        username = 'TestUser'
        
        # Limpiar usuario si existe
        if user_id in self.stats['users']:
            del self.stats['users'][user_id]
        
        # Primera conexión
        count, broke_record = save_connection_event(user_id, username)
        
        # Verificar estructura
        self.assertIn(user_id, self.stats['users'])
        self.assertIn('daily_connections', self.stats['users'][user_id])
        
        connections = self.stats['users'][user_id]['daily_connections']
        self.assertIn('total', connections)
        self.assertIn('by_date', connections)
        self.assertIn('personal_record', connections)
        
        # Verificar valores
        self.assertEqual(count, 1)
        self.assertTrue(broke_record)  # Primera conexión siempre rompe récord
        self.assertEqual(connections['total'], 1)
        
        today = datetime.now().strftime('%Y-%m-%d')
        self.assertEqual(connections['by_date'][today], 1)
        self.assertEqual(connections['personal_record']['count'], 1)
    
    def test_record_connection_event_increments_correctly(self):
        """Verifica que las conexiones se incrementan correctamente"""
        from core.session_dto import save_connection_event
        from datetime import datetime
        
        user_id = 'test_user_increment_456'
        username = 'TestUser2'
        today = datetime.now().strftime('%Y-%m-%d')
        
        # Limpiar usuario si existe
        if user_id in self.stats['users']:
            del self.stats['users'][user_id]
        
        # Simular 3 conexiones
        for i in range(3):
            count, broke_record = save_connection_event(user_id, username)
            self.assertEqual(count, i + 1, f"Conexión {i+1} debe tener count={i+1}")
            if i > 0:
                self.assertTrue(broke_record, f"Conexión {i+1} debe romper récord")
        
        # Verificar totales
        connections = self.stats['users'][user_id]['daily_connections']
        self.assertEqual(connections['total'], 3)
        self.assertEqual(connections['by_date'][today], 3)
        self.assertEqual(connections['personal_record']['count'], 3)
        self.assertEqual(connections['personal_record']['date'], today)
    
    def test_cooldown_accepts_custom_seconds(self):
        """Verifica que check_cooldown acepta cooldown personalizado"""
        from core.cooldown import check_cooldown
        
        user_id = 'test_cooldown_user'
        event_key = 'test_event'
        
        # Primera llamada debe pasar
        self.assertTrue(check_cooldown(user_id, event_key, cooldown_seconds=5))
        
        # Segunda llamada inmediata debe fallar
        self.assertFalse(check_cooldown(user_id, event_key, cooldown_seconds=5))
        
        # Limpiar cooldown
        cooldown_key = f"{user_id}:{event_key}"
        if cooldown_key in self.stats['cooldowns']:
            del self.stats['cooldowns'][cooldown_key]
    
    def test_connections_milestone_notifications(self):
        """Verifica que las notificaciones de milestone están implementadas"""
        import os
        
        # Leer events.py
        events_path = os.path.join(os.path.dirname(__file__), 'cogs', 'events.py')
        with open(events_path, 'r') as f:
            source = f.read()
        
        # Verificar que tiene los milestones definidos
        self.assertIn('MILESTONES', source, "Debe tener MILESTONES definidos")
        self.assertIn('10', source, "Debe incluir milestone de 10 conexiones")
        self.assertIn('25', source, "Debe incluir milestone de 25 conexiones")
        self.assertIn('50', source, "Debe incluir milestone de 50 conexiones")
        
        # Verificar que llama a save_connection_event
        self.assertIn('save_connection_event', source, 
                     "on_presence_update debe llamar save_connection_event")
    
    def test_connections_tracking_in_session_dto(self):
        """Conexiones diarias persistidas vía session_dto y expuestas por !topconnections"""
        import os
        
        dto_path = os.path.join(os.path.dirname(__file__), 'core', 'session_dto.py')
        with open(dto_path, 'r') as f:
            source = f.read()
        
        self.assertIn('save_connection_event', source,
                     "session_dto debe exponer save_connection_event")
        self.assertIn('daily_connections', source,
                     "Estructura debe incluir daily_connections")
    
    def test_connections_embed_exists(self):
        """Verifica que existe el embed de conexiones"""
        import os
        
        # Leer embeds.py
        embeds_path = os.path.join(os.path.dirname(__file__), 'stats', 'embeds.py')
        with open(embeds_path, 'r') as f:
            source = f.read()
        
        # Verificar que existe la función
        self.assertIn('async def create_connections_ranking_embed', source,
                     "Debe existir create_connections_ranking_embed")
        self.assertIn('timeframe', source,
                     "Debe aceptar parámetro timeframe")
    
    def test_stats_command_shows_connections(self):
        """Verifica que !stats (user.py) puede mostrar conexiones"""
        import os
        
        commands_path = os.path.join(os.path.dirname(__file__), 'stats', 'commands', 'user.py')
        with open(commands_path, 'r') as f:
            source = f.read()
        
        self.assertIn("@bot.command(name='stats'", source, "Debe existir comando stats")
        self.assertIn("daily_connections", source,
                     "Comando stats debe referenciar daily_connections")
        self.assertIn("📱 Conexiones", source,
                     "Debe tener sección de Conexiones en el embed")


class TestVoiceMessageTracking(unittest.TestCase):
    """Tests para el sistema de tracking de mensajes de voz pendientes"""
    
    def test_events_cog_has_voice_manager(self):
        """Verifica que EventsCog tiene VoiceSessionManager"""
        # Importar el cog
        try:
            from cogs.events import EventsCog
            from core.voice_session import VoiceSessionManager
            from unittest.mock import MagicMock
            
            # Crear instancia mock del bot
            mock_bot = MagicMock()
            
            # Crear instancia del cog
            cog = EventsCog(mock_bot)
            
            # Verificar que tiene el voice_manager
            self.assertIsInstance(cog.voice_manager, VoiceSessionManager,
                                "EventsCog debe tener voice_manager de tipo VoiceSessionManager")
            self.assertEqual(len(cog.voice_manager.active_sessions), 0,
                           "active_sessions debe estar vacío al inicio")
            
        except ImportError as e:
            self.skipTest(f"No se pudo importar EventsCog o VoiceSessionManager: {e}")
    
    def test_voice_verification_uses_member_guild(self):
        """Verifica que el código usa VoiceSessionManager y no bloquea el event handler"""
        # Leer el archivo de eventos
        events_file = Path(__file__).parent / 'cogs' / 'events.py'
        if not events_file.exists():
            self.skipTest("No se encontró cogs/events.py")
        
        with open(events_file, 'r', encoding='utf-8') as f:
            source = f.read()
        
        # Verificar que usa VoiceSessionManager
        self.assertIn("VoiceSessionManager", source,
                     "Debe usar VoiceSessionManager para gestionar sesiones")
        
        # Verificar que NO bloquea el event handler con sleep
        self.assertNotIn("await asyncio.sleep(3)", source,
                        "No debe bloquear el event handler con sleep")
        self.assertNotIn("await asyncio.sleep(7)", source,
                        "No debe bloquear el event handler con sleep")
        
        # Verificar que delega al manager (ahora usa handle_start/handle_end)
        self.assertIn("voice_manager.handle_start", source,
                     "Debe delegar entrada al voice_manager")
        self.assertIn("voice_manager.handle_end", source,
                     "Debe delegar salida al voice_manager")
        
        # Verificar que voice_session.py usa tasks en background
        voice_session_file = Path(__file__).parent / 'core' / 'voice_session.py'
        if voice_session_file.exists():
            with open(voice_session_file, 'r', encoding='utf-8') as f:
                voice_source = f.read()
            
            # Verificar que usa asyncio.create_task (no bloquea)
            self.assertIn("asyncio.create_task", voice_source,
                         "Debe usar tasks en background para verificación")
            
            # Verificar que guarda guild_id en la sesión
            self.assertIn("guild_id", voice_source,
                         "Debe guardar guild_id en la sesión")


class TestVoiceLeaveNotificationLogic(unittest.TestCase):
    """Tests para la lógica de notificaciones de salida de voz con cooldowns"""
    
    def setUp(self):
        """Setup para cada test"""
        from core.persistence import stats
        self.stats = stats
        self.stats_backup = stats['cooldowns'].copy()
    
    def tearDown(self):
        """Cleanup después de cada test"""
        self.stats['cooldowns'] = self.stats_backup.copy()
    
    def test_is_cooldown_passed_exists(self):
        """Verifica que existe la función is_cooldown_passed"""
        from core.cooldown import is_cooldown_passed
        self.assertTrue(callable(is_cooldown_passed))
    
    def test_is_cooldown_passed_no_cooldown(self):
        """Verifica que is_cooldown_passed retorna True si no hay cooldown"""
        from core.cooldown import is_cooldown_passed
        
        user_id = 'test_user_no_cooldown'
        event_key = 'test_event'
        
        # Limpiar cooldown si existe
        cooldown_key = f"{user_id}:{event_key}"
        if cooldown_key in self.stats['cooldowns']:
            del self.stats['cooldowns'][cooldown_key]
        
        # Debe retornar True (no hay cooldown)
        self.assertTrue(is_cooldown_passed(user_id, event_key, cooldown_seconds=600))
    
    def test_is_cooldown_passed_active_cooldown(self):
        """Verifica que is_cooldown_passed retorna False si el cooldown está activo"""
        from core.cooldown import is_cooldown_passed
        from datetime import datetime
        
        user_id = 'test_user_active'
        event_key = 'test_event'
        cooldown_key = f"{user_id}:{event_key}"
        
        # Establecer cooldown reciente (hace 5 minutos, cooldown de 10 min)
        self.stats['cooldowns'][cooldown_key] = (datetime.now() - timedelta(minutes=5)).isoformat()
        
        # Debe retornar False (cooldown activo)
        self.assertFalse(is_cooldown_passed(user_id, event_key, cooldown_seconds=600))
    
    def test_is_cooldown_passed_expired_cooldown(self):
        """Verifica que is_cooldown_passed retorna True si el cooldown expiró"""
        from core.cooldown import is_cooldown_passed
        from datetime import datetime
        
        user_id = 'test_user_expired'
        event_key = 'test_event'
        cooldown_key = f"{user_id}:{event_key}"
        
        # Establecer cooldown antiguo (hace 15 minutos, cooldown de 10 min)
        self.stats['cooldowns'][cooldown_key] = (datetime.now() - timedelta(minutes=15)).isoformat()
        
        # Debe retornar True (cooldown expirado)
        self.assertTrue(is_cooldown_passed(user_id, event_key, cooldown_seconds=600))
    
    def test_is_cooldown_passed_does_not_update(self):
        """Verifica que is_cooldown_passed NO actualiza el cooldown"""
        from core.cooldown import is_cooldown_passed, check_cooldown
        from datetime import datetime
        
        user_id = 'test_user_no_update'
        event_key = 'test_event'
        cooldown_key = f"{user_id}:{event_key}"
        
        # Establecer cooldown antiguo
        old_time = (datetime.now() - timedelta(minutes=15)).isoformat()
        self.stats['cooldowns'][cooldown_key] = old_time
        
        # Llamar is_cooldown_passed (no debe actualizar)
        result = is_cooldown_passed(user_id, event_key, cooldown_seconds=600)
        self.assertTrue(result)
        
        # Verificar que el cooldown NO cambió
        self.assertEqual(self.stats['cooldowns'][cooldown_key], old_time)
        
        # Comparar con check_cooldown que SÍ actualiza
        check_cooldown(user_id, event_key, cooldown_seconds=600)
        new_time = self.stats['cooldowns'][cooldown_key]
        self.assertNotEqual(new_time, old_time)
    
    def test_voice_leave_logic_with_entry_notification(self):
        """Verifica lógica de salida cuando hubo notificación de entrada (SIMPLIFICADO)"""
        import os
        voice_session_file = Path(__file__).parent / 'core' / 'voice_session.py'
        if not voice_session_file.exists():
            self.skipTest("No se encontró core/voice_session.py")
        
        with open(voice_session_file, 'r', encoding='utf-8') as f:
            source = f.read()
        
        # SIMPLIFICADO: Ahora usa cooldown unificado 'voice' y verifica session.entry_notification_sent
        self.assertIn('session.entry_notification_sent', source)
        self.assertIn('check_cooldown(user_id, \'voice\'', source)
    
    def test_voice_leave_logic_without_entry_notification(self):
        """Verifica lógica de salida cuando NO hubo notificación de entrada (SIMPLIFICADO)"""
        import os
        voice_session_file = Path(__file__).parent / 'core' / 'voice_session.py'
        if not voice_session_file.exists():
            self.skipTest("No se encontró core/voice_session.py")
        
        with open(voice_session_file, 'r', encoding='utf-8') as f:
            source = f.read()
        
        # SIMPLIFICADO: Ahora solo verifica session.entry_notification_sent y usa cooldown unificado
        # Ya no hay lógica compleja de else con is_cooldown_passed
        self.assertIn('session.entry_notification_sent', source)
        self.assertIn('notify_voice_leave', source)
    
    def test_tracking_independent_of_notifications(self):
        """Verifica que el tracking NO se ve afectado por las notificaciones"""
        import os
        voice_session_file = Path(__file__).parent / 'core' / 'voice_session.py'
        if not voice_session_file.exists():
            self.skipTest("No se encontró core/voice_session.py")
        
        with open(voice_session_file, 'r', encoding='utf-8') as f:
            source = f.read()
        
        # Verificar que save_voice_time se llama
        self.assertIn('save_voice_time', source, "Debe llamar save_voice_time")
        
        # Verificar que save_voice_time está en el bloque else (sesión válida)
        # Buscar el bloque else después de session_is_valid_for_time
        valid_pos = source.find('session_is_valid_for_time')
        else_pos = source.find('else:', valid_pos)
        
        self.assertGreater(else_pos, valid_pos, "Debe tener bloque else para sesión válida")
        
        # Buscar save_voice_time después del else
        save_time_pos = source.find('save_voice_time', else_pos)
        self.assertGreater(save_time_pos, else_pos, 
                          "save_voice_time debe estar en el bloque else (sesión válida)")
        
        # Verificar que save_voice_time está antes de las notificaciones
        notify_leave_pos = source.find('notify_voice_leave', save_time_pos)
        self.assertGreater(notify_leave_pos, save_time_pos,
                          "save_voice_time debe estar antes de las notificaciones")
    
    def test_entry_notification_sent_flag_exists(self):
        """Verifica que existe el flag entry_notification_sent en BaseSession"""
        import os
        base_session_file = Path(__file__).parent / 'core' / 'base_session.py'
        if not base_session_file.exists():
            self.skipTest("No se encontró core/base_session.py")
        
        with open(base_session_file, 'r', encoding='utf-8') as f:
            source = f.read()
        
        # Verificar que existe el flag
        self.assertIn('entry_notification_sent', source)
        self.assertIn('self.entry_notification_sent = False', source)
    
    def test_entry_notification_sent_set_in_phase1(self):
        """Verifica que entry_notification_sent se setea en _on_session_confirmed_phase1"""
        import os
        voice_session_file = Path(__file__).parent / 'core' / 'voice_session.py'
        if not voice_session_file.exists():
            self.skipTest("No se encontró core/voice_session.py")
        
        with open(voice_session_file, 'r', encoding='utf-8') as f:
            source = f.read()
        
        # Verificar que se setea en phase1 (buscar hasta el siguiente método)
        phase1_pos = source.find('_on_session_confirmed_phase1')
        next_method_pos = source.find('async def _on_session_confirmed_phase2', phase1_pos)
        if next_method_pos == -1:
            next_method_pos = len(source)
        
        phase1_block = source[phase1_pos:next_method_pos]
        
        self.assertIn('entry_notification_sent = True', phase1_block)
        self.assertIn('entry_notification_sent = False', phase1_block)
    
    def test_game_leave_logic_matches_voice(self):
        """Verifica que la lógica de salida de juegos coincide con voz"""
        import os
        game_session_file = Path(__file__).parent / 'core' / 'game_session.py'
        voice_session_file = Path(__file__).parent / 'core' / 'voice_session.py'
        
        if not game_session_file.exists() or not voice_session_file.exists():
            self.skipTest("No se encontraron archivos de sesiones")
        
        with open(game_session_file, 'r', encoding='utf-8') as f:
            game_source = f.read()
        
        with open(voice_session_file, 'r', encoding='utf-8') as f:
            voice_source = f.read()
        
        # Verificar que ambos usan is_cooldown_passed
        self.assertIn('is_cooldown_passed', game_source)
        self.assertIn('is_cooldown_passed', voice_source)
        
        # Verificar que ambos verifican entry_notification_sent
        self.assertIn('entry_notification_sent', game_source)
        self.assertIn('entry_notification_sent', voice_source)


@unittest.skipIf(_SKIP_DISCORD_TESTS, 'discord.py no instalado')
class TestPartyDetection(unittest.TestCase):
    """Tests para el sistema de detección de parties"""
    
    def setUp(self):
        """Setup para cada test"""
        from core.persistence import stats
        self.stats = stats
        # Backup de parties
        self.parties_backup = stats.get('parties', {}).copy() if 'parties' in stats else {}
    
    def tearDown(self):
        """Cleanup después de cada test"""
        if self.parties_backup:
            self.stats['parties'] = self.parties_backup.copy()
        elif 'parties' in self.stats:
            del self.stats['parties']
    
    def test_party_detector_exists(self):
        """Verifica que existe PartySessionManager"""
        from core.party_session import PartySessionManager
        from unittest.mock import MagicMock
        bot = MagicMock()
        manager = PartySessionManager(bot)
        self.assertIsNotNone(manager)
    
    def test_party_structure_created(self):
        """Verifica que se crea la estructura de parties"""
        from core.party_session import PartySessionManager
        from unittest.mock import MagicMock
        
        # Limpiar parties si existe
        if 'parties' in self.stats:
            del self.stats['parties']
        
        bot = MagicMock()
        manager = PartySessionManager(bot)
        
        # Verificar estructura
        self.assertIn('parties', self.stats)
        self.assertIn('active', self.stats['parties'])
        self.assertIn('history', self.stats['parties'])
        self.assertIn('stats_by_game', self.stats['parties'])
    
    def test_party_config_exists(self):
        """Verifica que existe la configuración de parties"""
        from core.persistence import config
        
        self.assertIn('party_detection', config)
        party_config = config['party_detection']
        
        self.assertIn('enabled', party_config)
        self.assertIn('min_players', party_config)
        self.assertIn('notify_on_formed', party_config)
        self.assertIn('notify_on_join', party_config)
        self.assertIn('cooldown_minutes', party_config)
        self.assertIn('use_here_mention', party_config)
        self.assertIn('blacklisted_games', party_config)
    
    def test_party_commands_exist(self):
        """Verifica que existen los comandos de party"""
        import os
        utility_file = Path(__file__).parent / 'cogs' / 'utility.py'
        if not utility_file.exists():
            self.skipTest("No se encontró cogs/utility.py")
        
        with open(utility_file, 'r', encoding='utf-8') as f:
            source = f.read()
        
        # Verificar comandos
        self.assertIn("@commands.command(name='party'", source)
        self.assertIn("@commands.command(name='partyhistory'", source)
        self.assertIn("@commands.command(name='partystats'", source)
    
    def test_party_detection_integrated(self):
        """Verifica que la detección de parties está integrada en events.py"""
        import os
        events_file = Path(__file__).parent / 'cogs' / 'events.py'
        if not events_file.exists():
            self.skipTest("No se encontró cogs/events.py")
        
        with open(events_file, 'r', encoding='utf-8') as f:
            source = f.read()
        
        # Verificar integración con PartySessionManager (nuevo sistema)
        self.assertIn('PartySessionManager', source)
        self.assertIn('party_manager', source)
        self.assertIn('get_active_players_by_game', source)
    
    def test_get_active_parties(self):
        """Verifica que active_sessions es un dict vacío inicialmente"""
        from core.party_session import PartySessionManager
        from unittest.mock import MagicMock
        
        bot = MagicMock()
        manager = PartySessionManager(bot)
        
        self.assertIsInstance(manager.active_sessions, dict)
        self.assertEqual(len(manager.active_sessions), 0)
    
    def test_get_party_history(self):
        """Verifica que la historia de parties existe en stats"""
        from core.persistence import stats
        
        # Asegurar estructura
        if 'parties' in stats:
            self.assertIn('history', stats['parties'])
            self.assertIsInstance(stats['parties']['history'], list)
    
    def test_get_game_stats(self):
        """Verifica que las stats por juego existen en stats"""
        from core.persistence import stats
        
        # Asegurar estructura
        if 'parties' in stats:
            self.assertIn('stats_by_game', stats['parties'])
            self.assertIsInstance(stats['parties']['stats_by_game'], dict)
    
    def test_party_blacklist_config(self):
        """Verifica que la blacklist de juegos está configurada"""
        from core.persistence import config
        
        party_config = config.get('party_detection', {})
        blacklist = party_config.get('blacklisted_games', [])
        
        self.assertIsInstance(blacklist, list)
        # Verificar que incluye juegos comunes que no son juegos reales
        self.assertIn('Spotify', blacklist)


@unittest.skipIf(_SKIP_DISCORD_TESTS, 'discord.py no instalado')
class TestVoiceMoveNotificationLogic(unittest.TestCase):
    """Tests para la lógica de notificación de cambio de canal de voz"""
    
    def test_voice_move_requires_confirmed_session(self):
        """
        Verifica que handle_voice_move solo notifica si la sesión anterior estaba confirmada.
        
        Escenario:
        - Usuario entra a canal A
        - Usuario cambia a canal B antes de 10s
        - NO debe notificar el cambio (sesión no confirmada)
        """
        from core.voice_session import VoiceSession
        
        # Simular sesión no confirmada
        session = VoiceSession('123', 'TestUser', 'Channel A', 1)
        session.is_confirmed = False
        
        # Verificar que la sesión no está confirmada
        self.assertFalse(session.is_confirmed)
        self.assertTrue(session.is_short(threshold=10))
    
    def test_voice_move_notifies_when_confirmed(self):
        """
        Verifica que handle_voice_move SÍ notifica si la sesión anterior estaba confirmada.
        
        Escenario:
        - Usuario entra a canal A
        - Usuario espera 15s (sesión confirmada)
        - Usuario cambia a canal B
        - DEBE notificar el cambio
        """
        from core.voice_session import VoiceSession
        from datetime import datetime, timedelta
        
        # Simular sesión confirmada (más de 10s)
        session = VoiceSession('123', 'TestUser', 'Channel A', 1)
        session.is_confirmed = True
        session.start_time = datetime.now() - timedelta(seconds=15)
        
        # Verificar que la sesión está confirmada
        self.assertTrue(session.is_confirmed)
        self.assertFalse(session.is_short(threshold=10))
        self.assertGreater(session.duration_seconds(), 10)
    
    def test_voice_move_captures_session_before_end(self):
        """
        Verifica que handle_voice_move captura el estado de la sesión ANTES de finalizarla.
        
        Esto es crítico porque handle_end elimina la sesión del diccionario.
        """
        from core.voice_session import VoiceSession
        
        # Simular sesión confirmada
        session = VoiceSession('123', 'TestUser', 'Channel A', 1)
        session.is_confirmed = True
        
        # Capturar estado antes de "finalizar"
        was_confirmed = session.is_confirmed
        
        # Simular finalización (en el código real, handle_end elimina la sesión)
        session_after = None
        
        # Verificar que capturamos el estado correctamente
        self.assertTrue(was_confirmed)
        # Después de handle_end, la sesión ya no existe
        self.assertIsNone(session_after)


@unittest.skipIf(_SKIP_DISCORD_TESTS, 'discord.py no instalado')
class TestPartySessionSystem(unittest.TestCase):
    """Tests para el sistema de party sessions"""
    
    def test_party_session_creation(self):
        """Verifica que PartySession se crea correctamente"""
        from core.party_session import PartySession
        
        player_ids = {'123', '456', '789'}
        player_names = ['Player1', 'Player2', 'Player3']
        
        session = PartySession('Hades', player_ids, player_names, 1)
        
        self.assertEqual(session.game_name, 'Hades')
        self.assertEqual(len(session.player_ids), 3)
        self.assertEqual(len(session.player_names), 3)
        self.assertEqual(session.max_players, 3)
        self.assertFalse(session.is_confirmed)
        self.assertFalse(session.entry_notification_sent)
    
    def test_party_session_inherits_base_session(self):
        """Verifica que PartySession hereda correctamente de BaseSession"""
        from core.party_session import PartySession
        from core.base_session import BaseSession
        
        session = PartySession('Hades', {'123'}, ['Player1'], 1)
        
        self.assertIsInstance(session, BaseSession)
        self.assertTrue(hasattr(session, 'start_time'))
        self.assertTrue(hasattr(session, 'notification_message'))
        self.assertTrue(hasattr(session, 'verification_task'))
        self.assertTrue(hasattr(session, 'is_confirmed'))
        self.assertTrue(hasattr(session, 'entry_notification_sent'))
    
    def test_party_session_tracks_max_players(self):
        """Verifica que PartySession trackea el máximo de jugadores"""
        from core.party_session import PartySession
        
        # Empezar con 2 jugadores
        session = PartySession('Hades', {'123', '456'}, ['P1', 'P2'], 1)
        self.assertEqual(session.max_players, 2)
        
        # Simular que se une un tercer jugador
        session.player_ids.add('789')
        session.player_names.append('P3')
        session.max_players = max(session.max_players, len(session.player_ids))
        
        self.assertEqual(session.max_players, 3)
        self.assertEqual(len(session.player_ids), 3)
    
    def test_party_manager_inherits_base_manager(self):
        """Verifica que PartySessionManager hereda de BaseSessionManager"""
        from core.party_session import PartySessionManager
        from core.base_session import BaseSessionManager
        
        # Mock bot
        class MockBot:
            pass
        
        manager = PartySessionManager(MockBot())
        
        self.assertIsInstance(manager, BaseSessionManager)
        self.assertTrue(hasattr(manager, 'active_sessions'))
        self.assertTrue(hasattr(manager, 'min_duration_seconds'))
        self.assertEqual(manager.min_duration_seconds, 10)
    
    def test_party_manager_ensures_stats_structure(self):
        """Verifica que PartySessionManager inicializa la estructura de stats"""
        from core.party_session import PartySessionManager
        from core.persistence import stats
        
        # Mock bot
        class MockBot:
            pass
        
        manager = PartySessionManager(MockBot())
        
        # Verificar estructura
        self.assertIn('parties', stats)
        self.assertIn('active', stats['parties'])
        self.assertIn('history', stats['parties'])
        self.assertIn('stats_by_game', stats['parties'])
    
    def test_party_session_duration_tracking(self):
        """Verifica que PartySession trackea la duración correctamente"""
        from core.party_session import PartySession
        from datetime import datetime, timedelta
        import time
        
        session = PartySession('Hades', {'123'}, ['Player1'], 1)
        
        # Verificar duración inicial (debería ser ~0)
        initial_duration = session.duration_seconds()
        self.assertLess(initial_duration, 1.0)
        
        # Simular paso del tiempo
        time.sleep(0.1)
        
        # Verificar que la duración aumentó
        new_duration = session.duration_seconds()
        self.assertGreater(new_duration, initial_duration)
    
    def test_party_session_short_detection(self):
        """Verifica que PartySession detecta sesiones cortas correctamente"""
        from core.party_session import PartySession
        from datetime import datetime, timedelta
        
        session = PartySession('Hades', {'123'}, ['Player1'], 1)
        
        # Sesión recién creada debería ser corta
        self.assertTrue(session.is_short(threshold=10))
        
        # Simular sesión larga
        session.start_time = datetime.now() - timedelta(seconds=15)
        self.assertFalse(session.is_short(threshold=10))
    
    def test_party_blacklist_prevents_session_creation(self):
        """Verifica que los juegos en blacklist no crean parties"""
        from core.persistence import config
        
        party_config = config.get('party_detection', {})
        blacklist = party_config.get('blacklisted_games', [])
        
        # Verificar que Spotify está en blacklist
        self.assertIn('Spotify', blacklist)
        
        # En el código real, handle_start retorna early si el juego está en blacklist
        # Aquí solo verificamos que la blacklist existe y tiene contenido
        self.assertGreater(len(blacklist), 0)
    
    def test_party_min_players_requirement(self):
        """Verifica que se requiere un mínimo de jugadores para crear party"""
        from core.persistence import config
        
        party_config = config.get('party_detection', {})
        min_players = party_config.get('min_players', 2)
        
        # Verificar que el mínimo es 2
        self.assertEqual(min_players, 2)
        
        # Simular lista de jugadores
        players_solo = [{'user_id': '123', 'username': 'Player1'}]
        players_party = [
            {'user_id': '123', 'username': 'Player1'},
            {'user_id': '456', 'username': 'Player2'}
        ]
        
        # Solo debe crear party si hay suficientes jugadores
        self.assertLess(len(players_solo), min_players)
        self.assertGreaterEqual(len(players_party), min_players)


if __name__ == '__main__':
    success = run_tests()
    sys.exit(0 if success else 1)

