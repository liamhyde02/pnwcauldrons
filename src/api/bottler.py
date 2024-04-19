from fastapi import APIRouter, Depends
from enum import Enum
from pydantic import BaseModel
from src.api import auth
import sqlalchemy
from src import database as db
from src.api.helpers import potion_type_tostr
from src.api.helpers import list_floor_division
router = APIRouter(
    prefix="/bottler",
    tags=["bottler"],
    dependencies=[Depends(auth.get_api_key)],
)

class PotionInventory(BaseModel):
    potion_type: list[int]
    quantity: int

@router.post("/deliver/{order_id}")
def post_deliver_bottles(potions_delivered: list[PotionInventory], order_id: int):
    """ """
    print(f"potions delivered: {potions_delivered} order_id: {order_id}")
    with db.engine.begin() as connection:
        for potion in potions_delivered:
            for i in range(4):
                barrel_type = [0 for _ in range(4)]
                barrel_type[i] = 1
                if potion.potion_type[i] == 0:
                    continue
                barrel_update_sql = f"UPDATE barrel_inventory SET potion_ml = potion_ml - {potion.quantity * potion.potion_type[i]} WHERE barrel_type = '{potion_type_tostr(barrel_type)}'"
                connection.execute(sqlalchemy.text(barrel_update_sql))
            gold_update_sql = f"UPDATE potion_catalog_items SET quantity = quantity + {potion.quantity} WHERE potion_type = '{potion_type_tostr(potion.potion_type)}'"
            connection.execute(sqlalchemy.text(gold_update_sql))
    return "OK"

@router.post("/plan")
def get_bottle_plan():
    """
    Go from barrel to bottle.
    """

    # Each bottle has a quantity of what proportion of red, blue, and
    # green potion to add.
    # Expressed in integers from 1 to 100 that must sum up to 100.
    with db.engine.begin() as connection:
        potion_threshold_sql = "SELECT potion_threshold FROM global_inventory"
        result = connection.execute(sqlalchemy.text(potion_threshold_sql))
        potion_threshold = result.fetchone()[0]
        max_potion_sql = "SELECT potion_capacity_units FROM global_plan"
        result = connection.execute(sqlalchemy.text(max_potion_sql))
        max_potion = result.fetchone()[0] * 50
        potion_sql = "SELECT SUM(quantity) FROM potion_catalog_items"
        result = connection.execute(sqlalchemy.text(potion_sql))
        potions = result.fetchone()[0]
        available_potions = max_potion - potions
        barrel_inventory_sql = "SELECT * FROM barrel_inventory"
        result = connection.execute(sqlalchemy.text(barrel_inventory_sql))
        rows = result.fetchall()
        rows = [row._asdict() for row in rows]
        ml_inventory = [0, 0, 0, 0]
        for row in rows:
            ml_inventory = [ml_inventory[i] + row["potion_ml"] * row["barrel_type"][i] for i in range(4)]
        potion_catalog_sql = "SELECT * FROM potion_catalog_items"
        result = connection.execute(sqlalchemy.text(potion_catalog_sql))
        potions = result.fetchall()
        potions.sort(key=lambda x: x.price, reverse=True)
        bottling_plan = []
        for potion in potions:
            potion_quantity_sql = "SELECT quantity FROM potion_catalog_items WHERE potion_type = :potion_type"
            result = connection.execute(sqlalchemy.text(potion_quantity_sql), {"potion_type": potion.potion_type})
            potion_quantity = result.fetchone()[0]
            if potion_quantity > potion_threshold:
                continue
            potion = potion._asdict()
            quantity = list_floor_division(ml_inventory, potion["potion_type"])
            quantity = min(quantity, available_potions)
            available_potions -= quantity
            ml_inventory = [ml_inventory[i] - quantity * potion["potion_type"][i] for i in range(4)]
            if quantity > 0:
                bottling_plan.append(
                                    {"potion_type": potion["potion_type"], 
                                        "quantity": quantity
                                    }
                            )
        print(f"bottling_plan: {bottling_plan}")
        return bottling_plan
