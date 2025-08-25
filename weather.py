from __future__ import annotations

import datetime as dt
from typing import Dict, Any

import requests


MOSCOW_LATITUDE = 55.7558
MOSCOW_LONGITUDE = 37.6176


def _map_weather_code_to_description(code: int) -> str:
    """Return a short Russian description for Open-Meteo weather code.

    Mapping based on https://open-meteo.com/en/docs#latitude=52.52&longitude=13.41&hourly=temperature_2m
    """
    mapping: Dict[int, str] = {
        0: "Ясно",
        1: "В основном ясно",
        2: "Переменная облачность",
        3: "Пасмурно",
        45: "Туман",
        48: "Инейный туман",
        51: "Морось слабая",
        53: "Морось умеренная",
        55: "Морось сильная",
        56: "Ледяная морось слабая",
        57: "Ледяная морось сильная",
        61: "Дождь слабый",
        63: "Дождь умеренный",
        65: "Дождь сильный",
        66: "Ледяной дождь слабый",
        67: "Ледяной дождь сильный",
        71: "Снег слабый",
        73: "Снег умеренный",
        75: "Снег сильный",
        77: "Снежные зерна",
        80: "Ливни слабые",
        81: "Ливни умеренные",
        82: "Ливни сильные",
        85: "Снегопад слабый",
        86: "Снегопад сильный",
        95: "Гроза",
        96: "Гроза с градом",
        99: "Гроза с сильным градом",
    }
    return mapping.get(code, f"Код погоды {code}")


def _format_temp(value: float | None) -> str:
    if value is None:
        return "—"
    return f"{round(value):+d}°C"  # sign shows +/


def fetch_moscow_weather() -> Dict[str, Any]:
    """Fetch current and daily weather for Moscow from Open-Meteo.

    Returns a dict with keys: current_temp_c, wind_speed_ms, weather_code, daily_min_c,
    daily_max_c, precipitation_mm, description.
    """
    url = (
        "https://api.open-meteo.com/v1/forecast"
        f"?latitude={MOSCOW_LATITUDE}&longitude={MOSCOW_LONGITUDE}"
        "&current=temperature_2m,wind_speed_10m,weather_code"
        "&daily=temperature_2m_max,temperature_2m_min,precipitation_sum,weather_code"
        "&timezone=Europe%2FMoscow"
    )
    response = requests.get(url, timeout=15)
    response.raise_for_status()
    data = response.json()

    current = data.get("current", {})
    daily = data.get("daily", {})

    # Determine index for today's daily values using today's date string in local tz
    today_str = dt.datetime.now(dt.timezone.utc).astimezone(dt.timezone(dt.timedelta(hours=3))).date().isoformat()
    dates = daily.get("time", [])
    try:
        today_index = dates.index(today_str)
    except ValueError:
        today_index = 0

    weather_code_current = int(current.get("weather_code")) if current.get("weather_code") is not None else None
    description = _map_weather_code_to_description(weather_code_current) if weather_code_current is not None else "—"

    return {
        "current_temp_c": current.get("temperature_2m"),
        "wind_speed_ms": current.get("wind_speed_10m"),
        "weather_code": weather_code_current,
        "daily_min_c": (daily.get("temperature_2m_min") or [None])[today_index],
        "daily_max_c": (daily.get("temperature_2m_max") or [None])[today_index],
        "precipitation_mm": (daily.get("precipitation_sum") or [None])[today_index],
        "description": description,
    }


def build_moscow_weather_message() -> str:
    w = fetch_moscow_weather()
    temp_now = _format_temp(w.get("current_temp_c"))
    wind = w.get("wind_speed_ms")
    wind_text = f"{round(wind)} м/с" if isinstance(wind, (int, float)) else "—"
    tmin = _format_temp(w.get("daily_min_c"))
    tmax = _format_temp(w.get("daily_max_c"))
    precip = w.get("precipitation_mm")
    precip_text = f"{precip:.1f} мм" if isinstance(precip, (int, float)) else "—"
    desc = w.get("description") or "—"

    return (
        "Погода в Москве:\n"
        f"Сейчас: {temp_now}, ветер {wind_text}, {desc}.\n"
        f"Сегодня: от {tmin} до {tmax}, осадки за день: {precip_text}."
    )

