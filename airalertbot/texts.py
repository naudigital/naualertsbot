from typing import TYPE_CHECKING, Literal

import pytz
import yaml

if TYPE_CHECKING:
    from airalertbot.models import Alert


texts: dict[str, dict[Literal["activate"] | Literal["deactivate"], str]]

with open("assets/texts.yaml") as texts_file:
    texts = yaml.safe_load(texts_file)


def get_text(model: "Alert") -> str:
    """Get text for alert.

    Args:
        model: Alert model.

    Returns:
        Text for alert.
    """
    # convert datetime to UTC+3 timezone
    utcmoment_naive = model.created_at
    utcmoment = utcmoment_naive.replace(tzinfo=pytz.utc)
    local_datetime = utcmoment.astimezone(pytz.timezone("Europe/Kiev"))

    text = texts.get(model.alarm_type.value, {}).get(
        model.status.value,
        None,
    )
    if text is None:
        text = texts["unknown"][model.status.value]

    return text.format(
        time=local_datetime.strftime("%H:%M:%S"),
    )
