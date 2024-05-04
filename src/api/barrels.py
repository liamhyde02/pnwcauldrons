from fastapi import APIRouter, Depends
from pydantic import BaseModel
from src.api import auth
import sqlalchemy
from src import database as db
from src.api.helpers import potion_type_tostr
router = APIRouter(
    prefix="/barrels",
    tags=["barrels"],
    dependencies=[Depends(auth.get_api_key)],
)

class Barrel(BaseModel):
    sku: str

    ml_per_barrel: int
    potion_type: list[int]
    price: int

    quantity: int

@router.post("/deliver/{order_id}")
def post_deliver_barrels(barrels_delivered: list[Barrel], order_id: int):
    """ """
    print(f"barrels delivered: {barrels_delivered} order_id: {order_id}")
    processed_entry_sql = "INSERT INTO processed (order_id, type) VALUES (:order_id, 'barrels') RETURNING id"
    barrel_insert_sql = "INSERT INTO barrel_ledger (processed_id, barrel_type, potion_ml) VALUES (:processed_id, :barrel_type, :potion_ml)"
    gold_ledger_sql = "INSERT INTO gold_ledger (processed_id, gold) VALUES (:processed_id, :gold)"
    with db.engine.begin() as connection:
        processed_id = connection.execute(sqlalchemy.text(processed_entry_sql),
                           [{"order_id": order_id}]).scalar_one()
        for barrel in barrels_delivered:
            for _ in range(barrel.quantity):
                connection.execute(sqlalchemy.text(barrel_insert_sql), [{"processed_id": processed_id, 
                                                                         "barrel_type": potion_type_tostr(barrel.potion_type), 
                                                                         "potion_ml": barrel.ml_per_barrel}])
            connection.execute(sqlalchemy.text(gold_ledger_sql), 
                               [{"processed_id": processed_id, 
                                 "gold": -barrel.price * barrel.quantity}])
    return "OK"

# Gets called once a day
@router.post("/plan")
def get_wholesale_purchase_plan(wholesale_catalog: list[Barrel]):
    """ """
    print(wholesale_catalog)
    max_ml_sql = "SELECT SUM(ml_capacity_units) FROM global_plan"
    ml_gold_sql = "SELECT ml, gold from inventory "
    global_inventory_sql = "SELECT small_ml_threshold, medium_ml_threshold, large_ml_threshold FROM global_inventory"
    barrel_ml_sql = "SELECT COALESCE(SUM(potion_ml), 0) FROM barrel_ledger WHERE barrel_type = :barrel_type"

    with db.engine.begin() as connection:
        # Initialize globals
        max_ml = connection.execute(sqlalchemy.text(max_ml_sql)).scalar_one() * 10000
        ml, running_total = connection.execute(sqlalchemy.text(ml_gold_sql)).fetchone()
        available_ml = max_ml - ml
        small_ml_threshold, medium_ml_threshold, large_ml_threshold = connection.execute(sqlalchemy.text(global_inventory_sql)).fetchone()
        wholesale_catalog.sort(key=lambda x: x.ml_per_barrel/x.price, reverse=True)
        # Initialize loop variables
        barrel_plan = []
        barrel_type_set = set()
        for barrel in wholesale_catalog:
            # Determine the threshold for the barrel
            if barrel.sku.__contains__("SMALL"):
                ml_threshold = small_ml_threshold
            elif barrel.sku.__contains__("MEDIUM"):
                ml_threshold = medium_ml_threshold
            elif barrel.sku.__contains__("LARGE"):
                ml_threshold = large_ml_threshold
            elif barrel.sku.__contains__("MINI"):
                ml_threshold = 0
            print(f"barrel: {barrel.sku} ml_threshold: {ml_threshold}")
            if potion_type_tostr(barrel.potion_type) not in barrel_type_set:
                # Get the current ml for the barrel type
                barrel_ml = connection.execute(sqlalchemy.text(barrel_ml_sql), 
                                            [{"barrel_type": potion_type_tostr(barrel.potion_type)}]).scalar_one()
                # Calculate the quantity of barrels to buy
                max_buy_gold = running_total // barrel.price
                max_buy_ml = available_ml // barrel.ml_per_barrel
                max_buy_ml_threshold = (ml_threshold - barrel_ml) // barrel.ml_per_barrel
                quantity = min(max_buy_gold, max_buy_ml, max_buy_ml_threshold, barrel.quantity)
                if quantity > 0:
                    barrel_plan.append(
                        {
                            "sku": barrel.sku,
                            "quantity": quantity
                        }
                    )
                    running_total -= barrel.price * quantity
                    available_ml -= barrel.ml_per_barrel * quantity
                    barrel_type_set.add(potion_type_tostr(barrel.potion_type))

        print(f"barrel purchase plan: {barrel_plan}, running_total: {running_total}")
        return barrel_plan