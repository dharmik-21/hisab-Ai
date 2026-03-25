from sqlalchemy import Column, Integer, String, Float, Date, ForeignKey
from sqlalchemy.orm import relationship   # ✅ ADD THIS
from database import Base
from datetime import date


class Invoice(Base):
    __tablename__ = "invoices"

    id = Column(Integer, primary_key=True, index=True)
    subtotal = Column(Float)
    gst = Column(Float)
    cgst = Column(Float)
    sgst = Column(Float)
    total = Column(Float)
    date = Column(Date, default=date.today)

    items = relationship("Item", back_populates="invoice")  # ✅ ADD


class Item(Base):
    __tablename__ = "items"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(100))
    price = Column(Float)

    invoice_id = Column(Integer, ForeignKey("invoices.id"))

    invoice = relationship("Invoice", back_populates="items")  # ✅ ADD