"""
Tests básicos para el comando !wrapped
"""

import unittest
from unittest.mock import MagicMock, patch, mock_open
import json
from datetime import datetime


class TestWrappedCalculations(unittest.TestCase):
    """Tests para los cálculos del wrapped"""
    
    def setUp(self):
        """Setup común"""
        self.mock_stats = {
            'users': {
                '123': {
                    'username': 'TestUser',
                    'games': {
                        'League of Legends': {
                            'count': 50,
                            'total_minutes': 3000,
                            'daily_minutes': {
                                '2025-01-15': 120,
                                '2025-01-16': 180,
                                '2025-01-17': 90,
                                '2025-02-10': 150
                            }
                        },
                        'Valorant': {
                            'count': 30,
                            'total_minutes': 1800,
                            'daily_minutes': {
                                '2025-03-05': 90,
                                '2025-03-06': 60
                            }
                        }
                    },
                    'voice': {
                        'count': 25,
                        'total_minutes': 1500,
                        'daily_minutes': {
                            '2025-04-01': 60,
                            '2025-04-02': 90
                        }
                    },
                    'messages': {'count': 500, 'characters': 12000},
                    'reactions': {'total': 150, 'by_emoji': {'👍': 50, '❤️': 30}},
                    'stickers': {'total': 20, 'by_name': {'funny': 10}}
                }
            },
            'parties': {
                'history': [
                    {
                        'game': 'League of Legends',
                        'start': '2025-05-10T20:00:00',
                        'end': '2025-05-10T22:00:00',
                        'duration': 120,
                        'players': ['123', '456']
                    },
                    {
                        'game': 'Valorant',
                        'start': '2025-06-15T19:00:00',
                        'end': '2025-06-15T21:00:00',
                        'duration': 120,
                        'players': ['123', '789']
                    }
                ]
            }
        }
    
    def test_calculate_gaming_stats(self):
        """Test cálculo de stats de gaming"""
        from stats.commands.wrapped import _calculate_gaming_stats
        
        user_data = self.mock_stats['users']['123']
        stats = _calculate_gaming_stats(user_data, 2025)
        
        self.assertIsNotNone(stats)
        self.assertIn('total_hours', stats)
        self.assertIn('top_game', stats)
        self.assertIn('unique_games', stats)
        self.assertEqual(stats['unique_games'], 2)
    
    def test_calculate_voice_stats(self):
        """Test cálculo de stats de voice"""
        from stats.commands.wrapped import _calculate_voice_stats
        
        user_data = self.mock_stats['users']['123']
        stats = _calculate_voice_stats(user_data, 2025)
        
        self.assertIsNotNone(stats)
        self.assertIn('total_hours', stats)
        self.assertIn('sessions', stats)
    
    def test_calculate_party_stats(self):
        """Test cálculo de stats de parties"""
        from stats.commands.wrapped import _calculate_party_stats
        
        stats = _calculate_party_stats(self.mock_stats, '123', 2025)
        
        self.assertIsNotNone(stats)
        self.assertEqual(stats['total_parties'], 2)
        self.assertIn('top_game', stats)
    
    def test_calculate_social_stats(self):
        """Test cálculo de stats sociales"""
        from stats.commands.wrapped import _calculate_social_stats
        
        user_data = self.mock_stats['users']['123']
        stats = _calculate_social_stats(user_data)
        
        self.assertIsNotNone(stats)
        self.assertEqual(stats['messages'], 500)
        self.assertEqual(stats['reactions'], 150)
    
    def test_detect_personality(self):
        """Test detector de personalidad"""
        from stats.commands.wrapped import _detect_personality
        
        user_data = self.mock_stats['users']['123']
        gaming_stats = {'avg_session': 3.5, 'unique_games': 2, 'longest_streak': 3}
        party_stats = {'total_parties': 2}
        
        personality = _detect_personality(user_data, gaming_stats, party_stats)
        
        self.assertIsInstance(personality, list)
        self.assertGreater(len(personality), 0)
    
    def test_calculate_longest_streak(self):
        """Test cálculo de racha más larga"""
        from stats.commands.wrapped import _calculate_longest_streak
        
        games_filtered = {
            'Game1': {
                'daily_minutes': {
                    '2025-01-15': 120,
                    '2025-01-16': 90,
                    '2025-01-17': 60
                }
            }
        }
        
        streak = _calculate_longest_streak(games_filtered)
        self.assertEqual(streak, 3)
    
    def test_calculate_rankings(self):
        """Test cálculo de rankings"""
        from stats.commands.wrapped import _calculate_rankings
        
        rankings = _calculate_rankings(self.mock_stats, '123')
        
        self.assertIsNotNone(rankings)
        self.assertIn('gaming', rankings)
        self.assertIn('social', rankings)
        self.assertIn('parties', rankings)
    
    def test_generate_wrapped_embed(self):
        """Test generación del embed completo"""
        from stats.commands.wrapped import generate_wrapped_embed
        
        embed = generate_wrapped_embed(self.mock_stats, '123', 'TestUser', 2025)
        
        self.assertIsNotNone(embed)
        self.assertIn('TestUser', embed.title)
        self.assertGreater(len(embed.fields), 0)


class TestWrappedFiltering(unittest.TestCase):
    """Tests para filtrado por año"""
    
    def test_year_filtering(self):
        """Test que solo se incluyan datos del año correcto"""
        from stats.commands.wrapped import _calculate_gaming_stats
        
        user_data = {
            'games': {
                'Game1': {
                    'count': 10,
                    'total_minutes': 600,
                    'daily_minutes': {
                        '2024-12-31': 60,  # Año anterior
                        '2025-01-01': 120,  # Año objetivo
                        '2025-06-15': 180,  # Año objetivo
                        '2026-01-01': 90   # Año siguiente
                    }
                }
            }
        }
        
        stats = _calculate_gaming_stats(user_data, 2025)
        
        # Solo debería contar 120 + 180 = 300 minutos = 5 horas
        self.assertEqual(stats['total_hours'], 5.0)


class TestWrappedEdgeCases(unittest.TestCase):
    """Tests para casos límite"""
    
    def test_empty_data(self):
        """Test con datos vacíos"""
        from stats.commands.wrapped import _calculate_gaming_stats
        
        user_data = {'games': {}}
        stats = _calculate_gaming_stats(user_data, 2025)
        
        self.assertIsNone(stats)
    
    def test_no_year_data(self):
        """Test cuando no hay datos para el año especificado"""
        from stats.commands.wrapped import _calculate_gaming_stats
        
        user_data = {
            'games': {
                'Game1': {
                    'count': 10,
                    'total_minutes': 600,
                    'daily_minutes': {
                        '2024-01-01': 600  # Solo datos de 2024
                    }
                }
            }
        }
        
        stats = _calculate_gaming_stats(user_data, 2025)
        self.assertIsNone(stats)


if __name__ == '__main__':
    # Ejecutar tests
    unittest.main(verbosity=2)

