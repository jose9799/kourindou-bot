"""Environment configuration and balance defaults.

Every tunable gameplay value lives here. Values listed in SETTING_DEFAULTS can be
overridden per guild through the `guild_config` table.
"""

import os
import sys
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

BASE_DIR = Path(__file__).resolve().parent


def _require(name: str) -> str:
    value = os.getenv(name, "").strip()
    if not value:
        sys.exit(f"Missing required environment variable: {name}. Copy .env.example to .env.")
    return value


def _optional_int(name: str) -> int | None:
    raw = os.getenv(name, "").strip()
    if not raw:
        return None
    if not raw.isdigit():
        sys.exit(f"Environment variable {name} must be a numeric id, got: {raw!r}")
    return int(raw)


DISCORD_TOKEN = _require("DISCORD_TOKEN")
DATABASE_PATH = BASE_DIR / os.getenv("DATABASE_PATH", "database/kourindou.db")
SCHEMA_PATH = BASE_DIR / "database" / "schema.sql"
COMMAND_PREFIX = os.getenv("COMMAND_PREFIX", "!").strip() or "!"
DEV_GUILD_ID = _optional_int("DEV_GUILD_ID")
LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO").upper()
LOG_DIR = BASE_DIR / "logs"

CURRENCY = "🌸"
CURRENCY_NAME = "Puntos de Fe"
EMBED_COLOR = 0xE05C8A
EMBED_COLOR_ERROR = 0xB03A3A
EMBED_COLOR_SUCCESS = 0x4E9A5B

COGS = ("cogs.general", "cogs.economy", "cogs.voice", "cogs.shop", "cogs.games", "cogs.utils")

# Per-guild overridable settings. The type of the default also defines the type
# the admin command will coerce an override to.
SETTING_DEFAULTS: dict[str, int] = {
    "daily_base_reward": 100,
    "daily_cooldown_seconds": 22 * 3600,
    "daily_streak_window_seconds": 48 * 3600,
    "daily_streak_bonus_percent": 10,
    "daily_streak_bonus_cap_percent": 100,
    "chat_reward_min": 5,
    "chat_reward_max": 15,
    "chat_cooldown_seconds": 60,
    "chat_min_length": 3,
    "voice_faith_per_minute": 2,
    "voice_min_humans": 2,
    "transfer_min_amount": 1,
    "transfer_fee_percent": 0,
    "transfer_min_account_age_seconds": 24 * 3600,
    "bet_min": 10,
    "bet_max": 5000,
}

# Fixed operational values, not worth exposing to guild admins.
# The game cooldown is fixed because command decorators are evaluated before any
# guild lookup can happen, so a per-guild override would silently do nothing.
GAME_COOLDOWN_SECONDS = 10
VOICE_SETTLE_INTERVAL_MINUTES = 5
SQUAD_LIFETIME_SECONDS = 12 * 3600
SHOP_VIEW_TIMEOUT = 120
LEADERBOARD_LIMIT = 10
EXCLUDED_CHANNELS_KEY = "chat_excluded_channels"
