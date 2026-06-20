from typing import List, Optional
from datetime import datetime
from pydantic import BaseModel


class ClientCreate(BaseModel):
    full_name: str
    phone: str


class ClientOut(BaseModel):
    id: int
    full_name: str
    phone: str
    created_at: datetime

    class Config:
        from_attributes = True


class ServiceCreate(BaseModel):
    name: str
    price: float
    category: str


class ServiceOut(BaseModel):
    id: int
    name: str
    price: float
    category: str
    created_at: datetime

    class Config:
        from_attributes = True


class OrderItemIn(BaseModel):
    service_id: int
    quantity: int = 1
    price: float


class OrderCreate(BaseModel):
    client_id: int
    order_type: str
    complaint: Optional[str] = None
    modeler: Optional[str] = None
    address: Optional[str] = None
    pickup_time: Optional[str] = None
    note: Optional[str] = None
    items: List[OrderItemIn]


class OrderUpdate(BaseModel):
    status: Optional[str] = None
    complaint: Optional[str] = None
    work_done: Optional[str] = None
    parts_replaced: Optional[str] = None
    modeler: Optional[str] = None
    address: Optional[str] = None
    pickup_time: Optional[str] = None
    note: Optional[str] = None
    items: Optional[List[OrderItemIn]] = None


class OrderItemOut(BaseModel):
    id: int
    service_id: int
    service_name: str
    quantity: int
    price: float

    class Config:
        from_attributes = True


class OrderOut(BaseModel):
    id: int
    client_id: int
    client_name: str
    order_type: str
    status: str
    complaint: Optional[str]
    work_done: Optional[str]
    parts_replaced: Optional[str]
    modeler: Optional[str]
    address: Optional[str]
    pickup_time: Optional[str]
    total_price: float
    note: Optional[str]
    created_at: datetime
    items: List[OrderItemOut]

    class Config:
        from_attributes = True
