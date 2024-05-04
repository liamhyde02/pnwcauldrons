from fastapi import APIRouter, Depends, Request
from pydantic import BaseModel
from src.api import auth
import sqlalchemy
from src import database as db

router = APIRouter(
    prefix="/admin",
    tags=["admin"],
    dependencies=[Depends(auth.get_api_key)],
)

@router.post("/reset")
def reset():
    """
    Reset the game state. Gold goes to 100, all potions are removed from
    inventory, and all barrels are removed from inventory. Carts are all reset.
    """
    processed_reset_sql = "DELETE FROM processed"
    potion_reset_sql = "DELETE FROM potion_ledger"
    barrel_reset_sql = "DELETE FROM barrel_ledger"
    gold_reset_sql = "DELETE FROM gold_ledger"
    carts_sql = f"DELETE FROM carts"
    cart_items_sql = f"DELETE FROM cart_items"
    starting_gold_sql = "INSERT INTO gold_ledger (processed_id, gold) VALUES (:processed_id, 100)"
    capacity_reset_sql = "DELETE FROM global_plan"
    starting_capacity_sql = "INSERT INTO global_plan (processed_id, potion_capacity_units, ml_capacity_units) VALUES (:processed_id, 1, 1)"
    processed_entry_sql = "INSERT INTO processed (order_id, type) VALUES (:order_id, 'reset') RETURNING id"
    with db.engine.begin() as connection:
        connection.execute(sqlalchemy.text(processed_reset_sql))
        connection.execute(sqlalchemy.text(potion_reset_sql))
        connection.execute(sqlalchemy.text(barrel_reset_sql))
        connection.execute(sqlalchemy.text(gold_reset_sql))
        connection.execute(sqlalchemy.text(carts_sql))
        connection.execute(sqlalchemy.text(cart_items_sql))
        processed_id = connection.execute(sqlalchemy.text(processed_entry_sql), [{"order_id": -1}]).scalar_one()
        connection.execute(sqlalchemy.text(starting_gold_sql),
                           [{"processed_id": processed_id}])
        connection.execute(sqlalchemy.text(capacity_reset_sql))
        connection.execute(sqlalchemy.text(starting_capacity_sql),
                           [{"processed_id": processed_id}])
    return "OK"

