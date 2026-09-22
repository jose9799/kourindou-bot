from cogs.admin import normalize_config_key
from cogs.voice import channel_is_allowed


def test_normalize_config_key_accepts_common_aliases() -> None:
    assert normalize_config_key("voice_alloweds_channels") == "voice_allowed_channels"
    assert normalize_config_key("chat_excludeds_channels") == "chat_excluded_channels"


def test_channel_is_allowed_when_no_filters_are_set() -> None:
    assert channel_is_allowed("", "", 123456789) is True


def test_channel_is_allowed_uses_allowlist() -> None:
    assert channel_is_allowed("123,456", "", 123) is True
    assert channel_is_allowed("123,456", "", 999) is False


def test_channel_is_allowed_respects_exclusions() -> None:
    assert channel_is_allowed("", "123,456", 123) is False
    assert channel_is_allowed("", "123,456", 999) is True


def test_channel_is_allowed_allowlist_is_stricter_than_exclusions() -> None:
    assert channel_is_allowed("123,456", "999", 123) is True
    assert channel_is_allowed("123,456", "123", 123) is False
