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
    global_inventory_sql = "SELECT SUM(gold) FROM gold_ledger"
    potion_quantity_sql = "SELECT COALESCE(SUM(quantity), 0) FROM potions"
    barrels_sql = "SELECT COALESCE(SUM(potion_ml), 0) FROM barrels"
    with db.engine.begin() as connection:
        gold = connection.execute(sqlalchemy.text(global_inventory_sql)).scalar_one()
        num_potions = connection.execute(sqlalchemy.text(potion_quantity_sql)).scalar_one()
        num_ml = connection.execute(sqlalchemy.text(barrels_sql)).scalar_one()
        print(f"num_potions: {num_potions} num_ml: {num_ml} gold: {gold}")   

        return [
                {
                    "number_of_potions": num_potions,
                    "ml_in_barrels": num_ml,
                    "gold": gold,
                }
            ]

# Gets called once a day
@router.post("/plan")
def get_capacity_plan():
    """ 
    Start with 1 capacity for 50 potions and 1 capacity for 10000 ml of potion. Each additional 
    capacity unit costs 1000 gold.
    """
    gold_sql = "SELECT SUM(gold) FROM gold_ledger"
    inventory_sql = "SELECT * FROM global_inventory"
    with db.engine.begin() as connection:
        gold = connection.execute(sqlalchemy.text(gold_sql)).scalar_one()
        row_inventory = connection.execute(sqlalchemy.text(inventory_sql)).fetchone()._asdict()
        
        max_gold_purchase = gold // 1000
        potion_capacity_plan = row_inventory["potion_capacity_plan"]
        potion_capacity_purchase = min(max_gold_purchase, potion_capacity_plan)
        max_gold_purchase -= potion_capacity_purchase
        ml_capacity_plan = row_inventory["ml_capacity_plan"]
        ml_capacity_purchase = min(max_gold_purchase, ml_capacity_plan)
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
    capacity_insert_sql = "INSERT into global_plan (order_id, potion_capacity_units, ml_capacity_units) VALUES (:order_id, :potion_capacity, :ml_capacity)"
    gold_sql = "INSERT INTO gold_ledger (order_id, gold) VALUES (:order_id, :gold)"
    with db.engine.begin() as connection:   
        id = connection.execute(sqlalchemy.text(processed_entry_sql), 
                                [{"order_id": order_id}]).scalar_one()
        connection.execute(sqlalchemy.text(capacity_insert_sql), 
                           [{"order_id": id,
                             "potion_capacity": capacity_purchase.potion_capacity, 
                             "ml_capacity": capacity_purchase.ml_capacity}])
        connection.execute(sqlalchemy.text(gold_sql),
                           [{"order_id": id, 
                          "gold": -1000 * (capacity_purchase.potion_capacity + capacity_purchase.ml_capacity)}])
    return "OK"