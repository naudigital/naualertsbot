from typing import TYPE_CHECKING

import pytz
import yaml

if TYPE_CHECKING:
    from airalertbot.models import Alert


texts: dict[str, dict[str, str]]

with open("assets/texts.yaml") as texts_file:
    texts = yaml.safe_load(texts_file)


def get_text(model: "Alert", previous_model: "Alert | None") -> str:
    """Get text for alert.

    Args:
        model: Alert model.
        previous_model: Previous alert model.

    Returns:
        Text for alert.
    """
    # convert datetime to UTC+3 timezone
    utcmoment_naive = model.created_at
    utcmoment = utcmoment_naive.replace(tzinfo=pytz.utc)
    local_datetime = utcmoment.astimezone(pytz.timezone("Europe/Kiev"))

    duration = "00:00:00"
    alarm_status = model.status.value
    if alarm_status == "deactivate" and previous_model is not None:
        alarm_status = "deactivate_with_duration"
        duration_timedelta = model.created_at - previous_model.created_at
        duration = str(duration_timedelta)

    text = texts.get(model.alarm_type.value, {}).get(
        alarm_status,
        None,
    )
    if text is None:
        text = texts["unknown"][alarm_status]

    return text.format(
        time=local_datetime.strftime("%H:%M:%S"),
        duration=duration,
    )
