import unittest
from datetime import datetime

from core.assistant_data import query_stats


class DataLoader(unittest.TestCase):
    def setUp(self):
        self.now = datetime(2026, 10, 25, 12, 0, 0)
        self.member = {"1": "Wire", "2": "Pino", "3": "Botito"}
        self.data = {"users": {
            "1": {"username": "raw_wire", "games": {"LoL": {"total_minutes": 120, "daily_minutes": {"2026-10-25": 60, "2026-10-24": 30}}},
                  "voice": {"count": 4, "total_minutes": 90, "daily_minutes": {"2026-10-25": 45}},
                  "messages": {"count": 30, "characters": 900, "secret": "PRIVATE"},
                  "reactions": {"total": 7}, "stickers": {"total": 2},
                  "daily_connections": {"total": 40, "by_date": {"2026-10-25": 4},
                                        "personal_record": {"count": 12, "date": "2026-09-01"}}},
            "2": {"games": {"LoL": {"total_minutes": 900}}, "messages": {"count": 5}},
            "999": {"games": {"Hidden": {"total_minutes": 5000}}}}}

    def test_list_games_only_members_clamped_names(self):
        result = query_stats(self.data, self.member, {"action": "list_games"}, now=self.now)
        names = json_safe = str(result)
        self.assertNotIn("Hidden", str(result))
        self.assertNotIn("raw_wire", str(result))
        self.assertEqual(result["games"][0], {"game": "LoL", "minutes": 1020.0})

    def test_game_detail_unique_match_and_series(self):
        result = query_stats(self.data, self.member, {"action": "game_detail", "game": "lol"}, now=self.now)
        self.assertEqual(result["game"], "LoL")
        self.assertEqual(result["players"][0]["member"], "Pino")
        days = {row["date"]: row["minutes"] for row in result["days"]}
        self.assertEqual(len(days), 14)
        self.assertEqual(days["2026-10-25"], 60.0)
        self.assertEqual(days["2026-10-18"], 0.0)

    def test_ambiguous_or_unknown_names_rejected(self):
        self.data["users"]["2"]["games"]["loT"] = {"total_minutes": 1}
        with self.assertRaises(ValueError):
            query_stats(self.data, self.member, {"action": "game_detail", "game": "lo"}, now=self.now)
        with self.assertRaises(ValueError):
            query_stats(self.data, self.member, {"action": "game_detail", "game": "inexistente"}, now=self.now)

    def test_user_detail_aggregates_without_private_fields(self):
        result = query_stats(self.data, self.member, {"action": "user_detail", "user": "wire"}, now=self.now)
        dump = str(result)
        self.assertIn("LoL", dump)
        self.assertNotIn("PRIVATE", dump)
        self.assertNotIn("secret", dump)
        self.assertEqual(result["voice_connections"], 4)
        self.assertEqual(result["messages_lifetime"], 30)
        self.assertEqual(result["connections_record"], {"count": 12, "date": "2026-09-01"})

    def test_day_summary_single_day_only(self):
        result = query_stats(self.data, self.member, {"action": "day_summary", "date": "2026-10-25"}, now=self.now)
        rows = {(row["member"], row["game"]): row["minutes"] for row in result["activity"]}
        self.assertEqual(rows[("Wire", "LoL")], 60.0)
        self.assertEqual(rows[("Wire", "(voz)")], 45.0)
        self.assertEqual(result["connections"], [{"member": "Wire", "connections": 4}])
        # A day outside the window must not leak lifetime totals.
        empty = query_stats(self.data, self.member, {"action": "day_summary", "date": "2026-10-20"}, now=self.now)
        self.assertEqual(empty["activity"], "Nada registrado ese día.")

    def test_invalid_arguments_rejected(self):
        for args in ({"action": "drop"},
                     {"action": "list_games", "extra": "x"},
                     {"action": "day_summary"},  # missing date
                     {"action": "day_summary", "date": "25-10-2026"},
                     {"action": "day_summary", "date": "2026-13-40"},
                     {"action": "game_detail", "game": "LoL", "user": "Wire"},
                     {"action": "user_detail", "user": "Wire", "game": "LoL"},
                     {"action": "user_detail", "user": "x" * 90},
                     {"action": "list_games", "date": "2026-10-25"}):
            with self.assertRaises(ValueError):
                query_stats(self.data, self.member, args, now=self.now)


if __name__ == "__main__":
    unittest.main()
