from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class DeviceWrite(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)

    device_type: str = Field(min_length=1, max_length=50)
    vendor: str = Field(min_length=1, max_length=100)
    model: str = Field(min_length=1, max_length=100)
    serial_number: str = Field(min_length=1, max_length=100)
    mac_address: str | None = Field(default=None, max_length=17)
    hardware_version: str | None = Field(default=None, max_length=100)
    software_version: str | None = Field(default=None, max_length=100)


class DeviceRead(DeviceWrite):
    model_config = ConfigDict(from_attributes=True)

    id: str
    created_at: datetime
    updated_at: datetime
