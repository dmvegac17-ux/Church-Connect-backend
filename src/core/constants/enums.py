from enum import Enum


class UserRole(str, Enum):
    ADMIN = "ADMIN"
    PARTICIPANT = "PARTICIPANT"
    MEMBER = "MEMBER"
