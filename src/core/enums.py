"""Core enumerations used across the trading system."""

from enum import Enum


class Exchange(str, Enum):
    NSE = "NSE"
    NFO = "NFO"
    BSE = "BSE"
    BFO = "BFO"
    INDEX = "INDEX"


class Interval(str, Enum):
    MINUTE = "minute"
    THREE_MINUTE = "3minute"
    FIVE_MINUTE = "5minute"
    FIFTEEN_MINUTE = "15minute"
    THIRTY_MINUTE = "30minute"
    SIXTY_MINUTE = "60minute"
    DAY = "day"


class OrderSide(str, Enum):
    BUY = "BUY"
    SELL = "SELL"


class OrderType(str, Enum):
    MARKET = "MARKET"
    LIMIT = "LIMIT"
    SL = "SL"
    SLM = "SL-M"


class ProductType(str, Enum):
    MIS = "MIS"
    CNC = "CNC"
    NRML = "NRML"


class StrategyFamily(str, Enum):
    MOMENTUM_BREAKOUT = "MOMENTUM_BREAKOUT"
    MEAN_REVERSION = "MEAN_REVERSION"
    OPTION_MOMENTUM = "OPTION_MOMENTUM"
    OPTION_FADE = "OPTION_FADE"
    ORB = "ORB"
    VWAP_REVERSION = "VWAP_REVERSION"
    VOLUME_SPIKE = "VOLUME_SPIKE"
    STRADDLE_BREAKOUT = "STRADDLE_BREAKOUT"
    GAMMA_SCALP = "GAMMA_SCALP"


class Regime(str, Enum):
    TREND = "TREND"
    RANGE = "RANGE"
    VOLATILE = "VOLATILE"
    UNKNOWN = "UNKNOWN"


class TradeStatus(str, Enum):
    PENDING = "PENDING"
    OPEN = "OPEN"
    CLOSED = "CLOSED"
    CANCELLED = "CANCELLED"
    REJECTED = "REJECTED"
