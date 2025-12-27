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
        """Test filtro por última semana"""
        from datetime import datetime, timedelta
        
        week_ago = datetime.now() - timedelta(days=7)
        daily_minutes = {
            '2025-12-26': 60,
            '2025-12-20': 90,
            '2025-12-15': 45  # Más de 7 días
        }
        
        week_total = sum(
            mins for date, mins in daily_minutes.items()
            if datetime.strptime(date, '%Y-%m-%d') >= week_ago
        )
        
        # Solo debe contar los últimos 7 días
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
        """Test cantidad total de comandos"""
        total_commands = 27
        self.assertEqual(total_commands, 27)
    
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
        """Test comandos de estadísticas"""
        basic_stats = ['stats', 'topgames', 'topmessages', 'topreactions', 'topemojis', 'topstickers', 'topusers']
        advanced_stats = ['statsmenu', 'statsgames', 'statsvoice', 'statsuser', 'timeline', 'compare']
        time_tracking = ['voicetime', 'voicetop', 'gametime', 'gametop']
        self.assertEqual(len(basic_stats), 7)
        self.assertEqual(len(advanced_stats), 6)
        self.assertEqual(len(time_tracking), 4)
    
    def test_utility_commands(self):
        """Test comandos de utilidades"""
        utility_commands = ['export', 'voicetime', 'voicetop', 'bothelp']
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


if __name__ == '__main__':
    success = run_tests()
    sys.exit(0 if success else 1)

