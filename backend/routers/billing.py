from fastapi import APIRouter
from database import get_billing_summary, list_billing_history, list_billing_transactions

router = APIRouter()

@router.get("/billing")
def get_billing():
    return get_billing_summary()

@router.get("/billing/history")
def get_billing_history():
    return list_billing_history()

@router.get("/billing/transactions")
def get_billing_transactions():
    return list_billing_transactions()
