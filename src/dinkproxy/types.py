from collections.abc import Callable
from enum import Enum, auto

type DinkHandler = Callable[[dict], dict | None]


class DinkType(Enum):
    """
    Dink notification types.
    """

    CLUE = auto()
    COLLECTION = auto()
    DEATH = auto()
    LEVEL = auto()
    LOOT = auto()
    PET = auto()
    QUEST = auto()
    SLAYER = auto()
    SPEEDRUN = auto()
    KILL_COUNT = auto()
    COMBAT_ACHIEVEMENT = auto()
    ACHIEVEMENT_DIARY = auto()
    BARBARIAN_ASSAULT_GAMBLE = auto()
    PLAYER_KILL = auto()
    GROUP_STORAGE = auto()
    GRAND_EXCHANGE = auto()
    LEAGUES_AREA = auto()
    LEAGUES_MASTERY = auto()
    LEAGUES_RELIC = auto()
    LEAGUES_TASK = auto()
    LOGIN = auto()
    LOGOUT = auto()
    TOA_UNIQUE = auto()
    TRADE = auto()
    CHAT = auto()
    XP_MILESTONE = auto()
    EXTERNAL_PLUGIN = auto()
    GROUP_BANK_CONTENTS = auto()
