from datetime import date, datetime, timezone
from unittest.mock import MagicMock, patch

import requests
from django.core.cache import cache
from django.test import SimpleTestCase, override_settings

from routing.services.weather import (
    ForecastRangeError,
    HourlyWeather,
    OpenMeteoClient,
    WeatherRateLimitError,
    WeatherUnavailableError,
    weather_at,
)

START, END = date(2026, 11, 20), date(2026, 11, 20)
HOUR0 = int(datetime(2026, 11, 20, 0, 0, tzinfo=timezone.utc).timestamp())


def fake_get(wind=10.0, rain=0.0):
    """requests.get replacement that answers every requested location with 3 hours of data."""

    def get(url, params, timeout):
        count = len(params["latitude"].split(","))
        item = {
            "hourly": {
                "time": [HOUR0, HOUR0 + 3600, HOUR0 + 7200],
                "wind_speed_10m": [wind, wind + 1, None],
                "precipitation": [rain, rain, rain],
            }
        }
        response = MagicMock(status_code=200)
        response.json.return_value = [item] * count if count > 1 else item
        return response

    return get


@override_settings(WEATHER_BASE_URL="https://wx.test/v1/forecast")
class OpenMeteoClientTests(SimpleTestCase):
    def setUp(self):
        cache.clear()

    @patch("routing.services.weather.requests.get", side_effect=fake_get(wind=12.0, rain=0.2))
    def test_parses_hourly_series_and_skips_null_hours(self, get):
        [series] = OpenMeteoClient().forecast([(32.78, -96.8)], START, END)
        self.assertEqual(series[HOUR0], HourlyWeather(12.0, 0.2))
        self.assertEqual(series[HOUR0 + 3600], HourlyWeather(13.0, 0.2))
        self.assertNotIn(HOUR0 + 7200, series)  # null wind -> hour dropped

    @patch("routing.services.weather.requests.get", side_effect=fake_get())
    def test_requests_use_mph_inches_utc_and_the_date_range(self, get):
        OpenMeteoClient().forecast([(32.78, -96.8)], START, END)
        url = get.call_args.args[0]
        params = get.call_args.kwargs["params"]
        self.assertEqual(url, "https://wx.test/v1/forecast")
        self.assertEqual(params["wind_speed_unit"], "mph")
        self.assertEqual(params["precipitation_unit"], "inch")
        self.assertEqual(params["timezone"], "UTC")
        self.assertEqual(params["timeformat"], "unixtime")
        self.assertEqual((params["start_date"], params["end_date"]), ("2026-11-20", "2026-11-20"))
        self.assertEqual(params["hourly"], "wind_speed_10m,precipitation")

    @patch("routing.services.weather.requests.get", side_effect=fake_get())
    def test_points_are_batched_and_deduplicated(self, get):
        points = [(10 + i * 0.1, -90.0) for i in range(120)]
        result = OpenMeteoClient().forecast(points + points[:10], START, END)
        self.assertEqual(len(result), 130)  # one series per requested point, in order
        self.assertEqual(get.call_count, 3)  # 120 unique points / 50 per request
        sizes = sorted(len(c.kwargs["params"]["latitude"].split(",")) for c in get.call_args_list)
        self.assertEqual(sizes, [20, 50, 50])

    @patch("routing.services.weather.requests.get", side_effect=fake_get())
    def test_nearby_points_share_a_rounded_location(self, get):
        OpenMeteoClient().forecast([(32.781, -96.801), (32.784, -96.804)], START, END)
        self.assertEqual(len(get.call_args.kwargs["params"]["latitude"].split(",")), 1)

    @patch("routing.services.weather.requests.get", side_effect=fake_get())
    def test_results_are_cached(self, get):
        client = OpenMeteoClient()
        client.forecast([(32.78, -96.8)], START, END)
        client.forecast([(32.78, -96.8)], START, END)
        self.assertEqual(get.call_count, 1)
        client.forecast([(32.78, -96.8)], START, date(2026, 11, 21))  # different range -> new request
        self.assertEqual(get.call_count, 2)

    @patch("routing.services.weather.requests.get")
    def test_out_of_range_dates_raise_forecast_range_error(self, get):
        get.return_value = MagicMock(status_code=400)
        get.return_value.json.return_value = {"error": True, "reason": "start_date is out of allowed range"}
        with self.assertRaisesMessage(ForecastRangeError, "start_date is out of allowed range"):
            OpenMeteoClient().forecast([(1.0, 1.0)], START, END)

    @patch("routing.services.weather.requests.get")
    def test_server_errors_and_network_failures_raise_unavailable(self, get):
        get.return_value = MagicMock(status_code=503)
        with self.assertRaises(WeatherUnavailableError):
            OpenMeteoClient().forecast([(1.0, 1.0)], START, END)
        get.side_effect = requests.ConnectionError("boom")
        with self.assertRaises(WeatherUnavailableError):
            OpenMeteoClient().forecast([(2.0, 2.0)], START, END)

    @patch("routing.services.weather.requests.get")
    def test_rate_limit_raises_a_specific_error(self, get):
        get.return_value = MagicMock(status_code=429)
        with self.assertRaisesMessage(WeatherRateLimitError, "rate limit"):
            OpenMeteoClient().forecast([(1.0, 1.0)], START, END)
        self.assertTrue(issubclass(WeatherRateLimitError, WeatherUnavailableError))

    @patch("routing.services.weather.requests.get")
    def test_wrong_number_of_locations_raises(self, get):
        response = MagicMock(status_code=200)
        response.json.return_value = [{"hourly": {"time": [], "wind_speed_10m": [], "precipitation": []}}]
        get.return_value = response
        with self.assertRaises(WeatherUnavailableError):
            OpenMeteoClient().forecast([(1.0, 1.0), (2.0, 2.0)], START, END)


class WeatherAtTests(SimpleTestCase):
    SERIES = {HOUR0 + i * 3600: HourlyWeather(float(i), 0.0) for i in range(5)}

    def at(self, hour, minute):
        return weather_at(self.SERIES, datetime(2026, 11, 20, hour, minute, tzinfo=timezone.utc)).wind_mph

    def test_picks_the_nearest_hour(self):
        self.assertEqual(self.at(1, 0), 1.0)
        self.assertEqual(self.at(1, 29), 1.0)
        self.assertEqual(self.at(1, 30), 2.0)
        self.assertEqual(self.at(1, 59), 2.0)

    def test_accepts_non_utc_aware_datetimes(self):
        from datetime import timedelta

        plus_five = timezone(timedelta(hours=5))
        when = datetime(2026, 11, 20, 7, 0, tzinfo=plus_five)  # = 02:00 UTC
        self.assertEqual(weather_at(self.SERIES, when).wind_mph, 2.0)

    def test_missing_hour_raises(self):
        with self.assertRaises(WeatherUnavailableError):
            self.at(20, 0)
