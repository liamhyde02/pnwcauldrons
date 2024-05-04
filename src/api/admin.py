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
    processed_reset_sql = "TRUNCATE processed RESTART IDENTITY CASCADE; INSERT INTO processed (order_id, type) VALUES (-1, 'reset') RETURNING id"
    carts_sql = "TRUNCATE carts RESTART IDENTITY CASCADE;"
    starting_gold_sql = "INSERT INTO gold_ledger (processed_id, gold) VALUES (:processed_id, 100)"
    starting_capacity_sql = "INSERT INTO global_plan (processed_id, potion_capacity_units, ml_capacity_units) VALUES (:processed_id, 1, 1)"
    with db.engine.begin() as connection:
        processed_id = connection.execute(sqlalchemy.text(processed_reset_sql)).scalar_one()
        connection.execute(sqlalchemy.text(carts_sql))
        connection.execute(sqlalchemy.text(starting_gold_sql),
                           [{"processed_id": processed_id}])
        connection.execute(sqlalchemy.text(starting_capacity_sql),
                           [{"processed_id": processed_id}])
    return "OK"

