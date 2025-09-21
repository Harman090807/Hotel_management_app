# models.py
from dataclasses import dataclass, field
from typing import Optional, List, Dict

@dataclass
class Customer:
    name: str = ""
    address: str = ""
    phone: str = ""
    from_date: str = ""
    to_date: str = ""
    payment_advance: float = 0.0
    booking_id: Optional[int] = None

@dataclass
class Room:
    room_number: int
    ac: str = "N"          # 'A' or 'N'
    comfort: str = "N"     # 'S' (special) or 'N'
    size: str = "S"        # 'B' (big) or 'S' (small)
    rent: int = 0
    status: int = 0        # 0 = available, 1 = reserved
    cust: Optional[Customer] = None
