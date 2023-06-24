import common.microsoft_core as mscore

__all__ = ("Setting", "ProfileUser", "ProfileResponse")


class Setting(mscore.CamelBaseModel):
    id: str
    value: str


class ProfileUser(mscore.CamelBaseModel):
    id: str
    host_id: str
    settings: list[Setting]
    is_sponsored_user: bool


@mscore.add_decoder
class ProfileResponse(mscore.ParsableCamelModel):
    profile_users: list[ProfileUser]
