from typing import TYPE_CHECKING

import pytz
import yaml
from datetime import datetime

if TYPE_CHECKING:
    from naualertsbot.models import Alert


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
        duration = str(duration_timedelta).split(".")[0]

    now = datetime.now(pytz.timezone("Europe/Kiev"))
    if 7 <= now.hour <= 16:
        text_type = "educational"
    else:
        text_type = "campus"

    text = texts.get(model.alarm_type.value, {}).get(
        alarm_status,
        None,
    )
    if text is None:
        text = texts["unknown"][alarm_status]

    additional_text = texts.get("additional_info", {}).get(text_type, None)
    if additional_text is not None:
        text += "\n\n" + additional_text

    return text.format(
        time=local_datetime.strftime("%H:%M:%S"),
        duration=duration,
    )


def get_raw_text(key: str) -> str:
    """Get raw text.

    Args:
        key: Text key.

    Returns:
        Raw text.
    """
    parts = key.split(".")
    text = texts
    for part in parts:
        if not isinstance(text, dict):  # type: ignore
            raise KeyError(f"Text with key {key} not found.")
        text = text[part]
    if not isinstance(text, str):
        raise KeyError(f"Text with key {key} not found.")
    return text
