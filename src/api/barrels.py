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
    ml_sql = "SELECT COALESCE(SUM(potion_ml), 0) FROM barrel_ledger"
    global_inventory_sql = "SELECT * FROM global_inventory"
    gold_sql = "SELECT SUM(gold) FROM gold_ledger"
    barrel_ml_sql = "SELECT COALESCE(SUM(potion_ml), 0) FROM barrel_ledger WHERE barrel_type = :barrel_type"

    with db.engine.begin() as connection:
        max_ml = connection.execute(sqlalchemy.text(max_ml_sql)).scalar_one() * 10000
        ml = connection.execute(sqlalchemy.text(ml_sql)).scalar_one()
        available_ml = max_ml - ml
        global_inventory = connection.execute(sqlalchemy.text(global_inventory_sql)).fetchone()._asdict()
        running_total = connection.execute(sqlalchemy.text(gold_sql)).scalar_one()
        wholesale_catalog.sort(key=lambda x: x.ml_per_barrel/x.price, reverse=True)
        barrel_plan = []
        barrel_type_set = set()
        for barrel in wholesale_catalog:
            ml_threshold = global_inventory["ml_threshold"]
            if barrel.sku.__contains__("large"):
                ml_threshold = global_inventory["large_ml_threshold"]
            if potion_type_tostr(barrel.potion_type) not in barrel_type_set:
                barrel_ml = connection.execute(sqlalchemy.text(barrel_ml_sql), 
                                            [{"barrel_type": potion_type_tostr(barrel.potion_type)}]).scalar_one()
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