from datetime import datetime
from enum import StrEnum
from typing import Optional, Type

from pydantic import BaseModel, Field


class Status(StrEnum):
    ACTIVATE = "activate"
    DEACTIVATE = "deactivate"

    @classmethod
    def _missing_(  # noqa: WPS120
        cls: Type["Status"],
        value: object,  # noqa: WPS110
    ) -> Optional["Status"]:
        if not isinstance(value, str):
            return None
        value = value.lower()  # noqa: WPS110
        for member in cls:
            if member == value:
                return member
        return None


class AlarmType(StrEnum):
    UNKNOWN = "unknown"
    AIR = "air"
    ARTILLERY = "artillery"
    URBAN_FIGHTS = "urban_fights"
    CHEMICAL = "chemical"
    NUCLEAR = "nuclear"
    INFO = "info"  # noqa: WPS110

    @classmethod
    def _missing_(  # noqa: WPS120
        cls: Type["AlarmType"],
        value: object,  # noqa: WPS110
    ) -> Optional["AlarmType"]:
        if not isinstance(value, str):
            return None
        value = value.lower()  # noqa: WPS110
        for member in cls:
            if member == value:
                return member
        return None


class Alert(BaseModel):
    status: Status = Field(alias="status")
    region_id: int = Field(alias="regionId")
    alarm_type: AlarmType = Field(alias="alarmType")
    created_at: datetime = Field(alias="createdAt")
