"""El día del bot es ART, no UTC: cortes de período y buckets diarios."""

import unittest
from datetime import datetime, timedelta, timezone
from unittest.mock import patch

from core.assistant import metrics
from core import session_dto
from stats.data.filters import filter_by_period

ART = timezone(timedelta(hours=-3))
# 01:30 UTC del 14 = 22:30 ART del 13. El día UTC ya cambió; el ART no.
NOW_UTC = datetime(2026, 11, 14, 1, 30, tzinfo=timezone.utc)
NOW_ART = NOW_UTC.astimezone(ART)


def art_now():
    return NOW_ART


class MetricsPeriodTests(unittest.TestCase):
    def data(self):
        return {"users": {"1": {
            "username": "Nano",
            "games": {"CSGO": {"total_minutes": 500,
                               "daily_minutes": {"2026-11-13": 30, "2026-11-10": 20,
                                                 "2026-11-14": 90, "2026-10-01": 360}}},
            "voice": {"total_minutes": 999, "daily_minutes": {"2026-11-13": 10}},
            "messages": {"count": 3},
        }}}

    def test_today_is_the_art_day_not_the_utc_day(self):
        with patch("core.assistant.argentina_now", side_effect=art_now):
            result = metrics(self.data(), {"1": "Nano"}, "1", "me", "today")
        self.assertEqual(result["user"]["game_minutes"], 30)
        self.assertEqual(result["user"]["voice_minutes"], 10)

    def test_week_uses_the_same_art_cutoff(self):
        with patch("core.assistant.argentina_now", side_effect=art_now):
            result = metrics(self.data(), {"1": "Nano"}, "1", "me", "week")
        self.assertEqual(result["user"]["game_minutes"], 50)

    def test_all_keeps_lifetime_totals(self):
        result = metrics(self.data(), {"1": "Nano"}, "1", "me", "all")
        self.assertEqual(result["user"]["game_minutes"], 500)


class PeriodFilterTests(unittest.TestCase):
    def test_period_recomputes_totals_from_daily_minutes(self):
        data = {"users": {"1": {
            "username": "Nano",
            "games": {"CSGO": {"count": 9, "total_minutes": 500,
                               "last_played": "2026-11-13T23:00:00",
                               "daily_minutes": {"2026-11-13": 30, "2020-01-01": 470}}},
            "voice": {"total_minutes": 999,
                      "daily_minutes": {"2026-11-13": 10, "2020-01-01": 989}},
        }}}
        with patch("stats.data.filters.argentina_now", side_effect=art_now):
            result = filter_by_period(data, "today")
        user = result["users"]["1"]
        self.assertEqual(user["games"]["CSGO"]["total_minutes"], 30)
        self.assertEqual(user["games"]["CSGO"]["daily_minutes"], {"2026-11-13": 30})
        self.assertEqual(user["voice"]["total_minutes"], 10)

    def test_old_games_are_dropped(self):
        data = {"users": {"1": {"username": "Nano",
                                "games": {"Old": {"total_minutes": 60,
                                                  "daily_minutes": {"2020-01-01": 60}}},
                                "voice": {}}}}
        with patch("stats.data.filters.argentina_now", side_effect=art_now):
            result = filter_by_period(data, "today")
        self.assertEqual(result, {"users": {}})

    def test_all_is_untouched(self):
        data = {"users": {"1": {"username": "Nano"}}}
        self.assertIs(filter_by_period(data, "all"), data)


class SessionBucketTests(unittest.TestCase):
    def test_game_minutes_are_bucketed_by_art_day(self):
        with patch("core.session_dto.argentina_now", side_effect=art_now), \
                patch.object(session_dto, "stats", {"users": {}}), \
                patch.object(session_dto, "save_stats"):
            session_dto.save_game_time("1", "Nano", "CSGO", 30)
            daily = session_dto.stats["users"]["1"]["games"]["CSGO"]["daily_minutes"]
        self.assertEqual(daily, {"2026-11-13": 30})

    def test_voice_minutes_are_bucketed_by_art_day(self):
        with patch("core.session_dto.argentina_now", side_effect=art_now), \
                patch.object(session_dto, "stats", {"users": {}}), \
                patch.object(session_dto, "save_stats"):
            session_dto.save_voice_time("1", "Nano", 15)
            daily = session_dto.stats["users"]["1"]["voice"]["daily_minutes"]
        self.assertEqual(daily, {"2026-11-13": 15})


if __name__ == "__main__":
    unittest.main()
