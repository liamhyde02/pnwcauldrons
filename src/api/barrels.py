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
    inventory_sql = "SELECT ml, gold, ml_capacity from inventory "
    barrel_ml_sql = "SELECT COALESCE(SUM(potion_ml), 0) FROM barrel_ledger WHERE barrel_type = :barrel_type"

    with db.engine.begin() as connection:
        # Initialize globals
        ml, running_total, max_ml = connection.execute(sqlalchemy.text(inventory_sql)).fetchone()
        ml_capacity = (max_ml * 10000)
        available_ml = ml_capacity - ml
        wholesale_catalog.sort(key=lambda x: x.ml_per_barrel/x.price, reverse=True)
        # Initialize loop variables
        barrel_plan = []
        barrel_type_set = set()
        dark_present = False
        for barrel in wholesale_catalog:
            if barrel.potion_type[3] == 1:
                dark_present = True
        for barrel in wholesale_catalog:
            # Determine the threshold for the barrel
            if barrel.sku.__contains__("SMALL"):
                if ml_capacity < 20000:
                    ml_threshold = int(ml_capacity * 0.2)
                else:
                    ml_threshold = int(ml_capacity * 0.1)
            elif barrel.sku.__contains__("MEDIUM"):
                if ml_capacity < 40000:
                    ml_threshold = int(ml_capacity / 4)
                else:
                    ml_threshold = int(ml_capacity / 8)
            elif barrel.sku.__contains__("LARGE"):
                ml_threshold = ml_capacity / 4
            elif barrel.sku.__contains__("MINI"):
                ml_threshold = 0
            else:
                ml_threshold = 0
                print(f"Unknown barrel type: {barrel.sku}")
            if dark_present:
                ml_threshold = int(ml_threshold * 4 / 3)
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