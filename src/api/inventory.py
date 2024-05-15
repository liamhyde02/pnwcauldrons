from fastapi import APIRouter, Depends
from pydantic import BaseModel
from src.api import auth
import math
from src import database as db
import sqlalchemy

router = APIRouter(
    prefix="/inventory",
    tags=["inventory"],
    dependencies=[Depends(auth.get_api_key)],
)

@router.get("/audit")
def get_inventory():
    """ """
    get_inventory_sql = "SELECT gold, ml, potions FROM inventory"
    inventory_log_sql = "INSERT INTO inventory_log (gold, ml, potions) SELECT gold, ml, potions FROM inventory"
    with db.engine.begin() as connection:
        gold, ml, potions = connection.execute(sqlalchemy.text(get_inventory_sql)).fetchone()
        connection.execute(sqlalchemy.text(inventory_log_sql))
        print(f"num_potions: {potions} num_ml: {ml} gold: {gold}")   

        return [
                {
                    "number_of_potions": potions,
                    "ml_in_barrels": ml,
                    "gold": gold,
                }
            ]
def calculate_capacity_purchase(available_capacity_purchases: int):
    ml_capacity_purchase = available_capacity_purchases // 3
    potion_capacity_purchase = available_capacity_purchases - ml_capacity_purchase
    return ml_capacity_purchase, potion_capacity_purchase

# Gets called once a day
@router.post("/plan")
def get_capacity_plan():
    """ 
    Start with 1 capacity for 50 potions and 1 capacity for 10000 ml of potion. Each additional 
    capacity unit costs 1000 gold.
    """
    inventory_sql = "SELECT gold, ml_capacity, potion_capacity FROM inventory"
    with db.engine.begin() as connection:
        gold, ml_capacity, potion_capacity = connection.execute(sqlalchemy.text(inventory_sql)).fetchone()
    disposable_gold = int(gold * 0.7)
    ml_capacity_purchase, potion_capacity_purchase = calculate_capacity_purchase(disposable_gold // 1000)
    print(f"potion_capacity_purchase: {potion_capacity_purchase} ml_capacity_purchase: {ml_capacity_purchase}")
    return {
        "potion_capacity": potion_capacity_purchase,
        "ml_capacity": ml_capacity_purchase,
    }

class CapacityPurchase(BaseModel):
    potion_capacity: int
    ml_capacity: int

# Gets called once a day
@router.post("/deliver/{order_id}")
def deliver_capacity_plan(capacity_purchase : CapacityPurchase, order_id: int):
    """ 
    Start with 1 capacity for 50 potions and 1 capacity for 10000 ml of potion. Each additional 
    capacity unit costs 1000 gold.
    """
    print(f"order_id: {order_id} potion_capacity: {capacity_purchase.potion_capacity} ml_capacity: {capacity_purchase.ml_capacity}")
    processed_entry_sql = "INSERT INTO processed (order_id, type) VALUES (:order_id, 'capacity') RETURNING id"
    capacity_insert_sql = "INSERT into global_plan (processed_id, potion_capacity_units, ml_capacity_units) VALUES (:processed_id, :potion_capacity, :ml_capacity)"
    gold_sql = "INSERT INTO gold_ledger (processed_id, gold) VALUES (:processed_id, :gold)"
    with db.engine.begin() as connection:   
        processed_id = connection.execute(sqlalchemy.text(processed_entry_sql), 
                                [{"order_id": order_id}]).scalar_one()
        connection.execute(sqlalchemy.text(capacity_insert_sql), 
                           [{"processed_id": processed_id,
                             "potion_capacity": capacity_purchase.potion_capacity, 
                             "ml_capacity": capacity_purchase.ml_capacity}])
        connection.execute(sqlalchemy.text(gold_sql),
                           [{"processed_id": processed_id, 
                          "gold": -1000 * (capacity_purchase.potion_capacity + capacity_purchase.ml_capacity)}])
    return "OK"