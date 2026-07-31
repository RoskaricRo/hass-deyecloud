"""Pure data helpers for the DeyeCloud integration.

Ported from heavenknows1978/hass-deyecloud and adapted to this integration's
coordinator-based architecture. Kept dependency-free (no Home Assistant or
aiohttp imports) so it can be unit tested in isolation.
"""

_DAILY_ZERO_RECORD_KEYS = (
    "generationValue",
    "consumptionValue",
    "gridValue",
    "purchaseValue",
    "chargeValue",
    "dischargeValue",
)

_FLOAT_EPSILON = 0.001


def batched_device_serials(device_serials: list[str]) -> list[list[str]]:
    """Split serials into the maximum batch accepted by /device/latest."""
    return [
        device_serials[offset : offset + 10]
        for offset in range(0, len(device_serials), 10)
    ]


def empty_daily_record(day: str) -> dict:
    """Return an integration-generated zero daily record.

    Marked with "_deyecloud_placeholder" so callers can tell a real
    zero-production day (e.g. an overcast day) apart from a value we
    synthesized ourselves while waiting for DeyeCloud to catch up.
    """
    record = {
        "date": day,
        "_deyecloud_placeholder": True,
    }
    for key in _DAILY_ZERO_RECORD_KEYS:
        record[key] = 0.0
    return record


def _numeric_value(record: dict | None, key: str) -> float | None:
    """Return a numeric value from a daily/monthly record if possible."""
    if not record:
        return None
    try:
        value = record.get(key)
        if value is None or value == "":
            return None
        return float(value)
    except (TypeError, ValueError):
        return None


def records_look_like_same_daily_bucket(
    record: dict | None,
    reference: dict | None,
) -> bool:
    """Detect a daily record that is likely copied from the reference day."""
    if not record or not reference:
        return False

    matched_non_zero_values = 0
    reference_non_zero_keys = 0
    for key in _DAILY_ZERO_RECORD_KEYS:
        current = _numeric_value(record, key)
        previous = _numeric_value(reference, key)
        if previous is not None and previous > _FLOAT_EPSILON:
            reference_non_zero_keys += 1
        if current is None or previous is None:
            continue

        # The cloud can serve a slightly older snapshot of yesterday rather
        # than an exact copy, so allow the same 2% drift seen in issue logs.
        tolerance = max(_FLOAT_EPSILON, previous * 0.02)
        if previous > _FLOAT_EPSILON and abs(current - previous) <= tolerance:
            matched_non_zero_values += 1

    if reference_non_zero_keys == 0:
        return False

    required_matches = min(2, reference_non_zero_keys)
    return matched_non_zero_values >= required_matches


def should_reject_stale_today(
    record: dict | None,
    yesterday: dict | None,
    cached_today: dict | None,
    *,
    in_midnight_guard: bool,
) -> bool:
    """Return whether a Today candidate is demonstrably yesterday's bucket.

    Unlike a fixed post-midnight time window alone, this also keeps
    rejecting stale data for as long as the cached "today" value is itself
    still a placeholder we generated — so if DeyeCloud takes longer than the
    guard window to publish real data, we don't prematurely accept a stale
    copy of yesterday just because the clock window closed.
    """
    guarding_placeholder = bool(
        cached_today and cached_today.get("_deyecloud_placeholder")
    )
    return (
        (in_midnight_guard or guarding_placeholder)
        and records_look_like_same_daily_bucket(record, yesterday)
    )
