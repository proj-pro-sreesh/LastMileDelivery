import enum


class OrderType(str, enum.Enum):
    B2B = "B2B"
    B2C = "B2C"


class PaymentType(str, enum.Enum):
    PREPAID = "PREPAID"
    COD = "COD"


class ZoneType(str, enum.Enum):
    INTRA_ZONE = "INTRA_ZONE"
    INTER_ZONE = "INTER_ZONE"
