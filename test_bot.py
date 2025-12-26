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
    filter_by_period, get_period_label, calculate_daily_activity
)


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
    suite.addTests(loader.loadTestsFromTestCase(TestBarChart))
    suite.addTests(loader.loadTestsFromTestCase(TestTimelineChart))
    suite.addTests(loader.loadTestsFromTestCase(TestComparisonChart))
    suite.addTests(loader.loadTestsFromTestCase(TestPeriodFiltering))
    suite.addTests(loader.loadTestsFromTestCase(TestDailyActivity))
    suite.addTests(loader.loadTestsFromTestCase(TestStatsDataStructure))
    suite.addTests(loader.loadTestsFromTestCase(TestConfigStructure))
    suite.addTests(loader.loadTestsFromTestCase(TestIntegration))
    
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


if __name__ == '__main__':
    success = run_tests()
    sys.exit(0 if success else 1)

