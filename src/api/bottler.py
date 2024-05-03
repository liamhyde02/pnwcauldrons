from fastapi import APIRouter, Depends
from enum import Enum
from pydantic import BaseModel
from src.api import auth
import sqlalchemy
from src import database as db
from src.api.helpers import potion_type_tostr
from src.api.helpers import list_floor_division
import random
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
    processed_entry_sql = "INSERT INTO processed (order_id, type) VALUES (:order_id, 'bottles') RETURNING id"
    barrel_update_sql = "INSERT INTO barrel_ledger (processed_id, barrel_type, potion_ml) VALUES (:processed_id, :barrel_type, :potion_ml)"
    potion_insert_sql = "INSERT INTO potion_ledger (processed_id, potion_type, quantity) VALUES (:processed_id, :potion_type, :quantity)"
    
    with db.engine.begin() as connection:
        processed_id = connection.execute(sqlalchemy.text(processed_entry_sql),
                           [{"order_id": order_id}]).scalar_one()
        for potion in potions_delivered:
            for i in range(4):
                barrel_type = [1 if j == i else 0 for j in range(4)]
                if potion.potion_type[i] == 0:
                    continue
                connection.execute(sqlalchemy.text(barrel_update_sql),
                                    [{"processed_id": processed_id,
                                      "barrel_type": potion_type_tostr(barrel_type), 
                                      "potion_ml": (-potion.quantity * potion.potion_type[i])}])
                
            connection.execute(sqlalchemy.text(potion_insert_sql),
                                [{"processed_id": processed_id,
                                  "potion_type": potion_type_tostr(potion.potion_type),
                                  "quantity": potion.quantity}])
    return "OK"

@router.post("/plan")
def get_bottle_plan():
    """
    Go from barrel to bottle.
    """

    # Each bottle has a quantity of what proportion of red, blue, and
    # green potion to add.
    # Expressed in integers from 1 to 100 that must sum up to 100.
    max_potion_sql = "SELECT SUM(potion_capacity_units) FROM global_plan"
    total_potions_sql = "SELECT COALESCE(SUM(quantity), 0) FROM potion_ledger"
    barrel_sql = "SELECT COALESCE(SUM(potion_ml), 0) FROM barrel_ledger WHERE barrel_type = :barrel_type"
    potion_threshold_sql = "SELECT potion_threshold FROM global_inventory"
    potion_catalog_sql = "SELECT * FROM potion_catalog_items"
    potion_type_sql = "SELECT COALESCE(SUM(quantity), 0) FROM potion_ledger WHERE potion_type = :potion_type"
    visits_sql = "SELECT character_class, COUNT(character_class) as total_characters FROM visits JOIN global_time ON visits.day = global_time.day GROUP BY character_class"
    class_preference_sql = "SELECT potion_type, COALESCE(COUNT(potion_type), 0) as amount_bought FROM class_preferences WHERE character_class = :character_class GROUP BY potion_type, character_class"

    with db.engine.begin() as connection:
        result = connection.execute(sqlalchemy.text(visits_sql)).fetchall()
        visits = [row._asdict() for row in result]
        class_totals = {visit["character_class"]: visit["total_characters"] for visit in visits}
        sorted_classes = sorted(class_totals, key=lambda x: class_totals[x], reverse=True)
        print(f"sorted_classes: {sorted_classes}")
        max_potion = connection.execute(sqlalchemy.text(max_potion_sql)).scalar_one() * 50
        potions = connection.execute(sqlalchemy.text(total_potions_sql)).scalar_one()
        available_potions = max_potion - potions
        potion_threshold = connection.execute(sqlalchemy.text(potion_threshold_sql)).scalar_one()
        ml_inventory = [0 for _ in range(4)]
        for i in range(4):
            barrel_type = [1 if j == i else 0 for j in range(4)]
            ml_inventory[i] = connection.execute(sqlalchemy.text(barrel_sql), 
                                        [{"barrel_type": potion_type_tostr(barrel_type)}]).scalar_one()
        result = connection.execute(sqlalchemy.text(potion_catalog_sql))
        potions = result.fetchall()
        bottling_plan = []
        # for character_class in sorted_classes:
        #     class_preference = connection.execute(sqlalchemy.text(class_preference_sql), 
        #                                           [{"character_class": character_class}]).fetchall()
        #     class_preference = [row._asdict() for row in class_preference]
        #     if len(class_preference) == 0:
        #         print(f"character_class: {character_class}, class_preference: No preference yet")
        #     else: 
        #         weighted_choices = [(pref['potion_type'], pref['amount_bought']) for pref in class_preference]
        #         selected_potion = random.choices(
        #             [choice[0] for choice in weighted_choices], 
        #             weights=[choice[1] for choice in weighted_choices],
        #             k=1
        #         )[0]
        #         print(f"character_class: {character_class}, selected_potion: {selected_potion}")
        #         for potion in potions:
        #             if potion.potion_type == selected_potion:
        #                 current_potions = connection.execute(sqlalchemy.text(potion_type_sql), 
        #                                             [{"potion_type": potion.potion_type}]).scalar_one()
        #                 inventory_max = list_floor_division(ml_inventory, potion.potion_type)
        #                 threshold_max = potion_threshold - current_potions
        #                 quantity = min(inventory_max, threshold_max, available_potions)
        #                 if quantity > 0:
        #                     bottling_plan.append(
        #                                         {"potion_type": potion.potion_type, 
        #                                             "quantity": quantity
        #                                         }
        #                                 )
        #                     ml_inventory = [ml_inventory[i] - quantity * potion.potion_type[i] for i in range(4)]
        #                     available_potions -= quantity
        #                     potions.remove(potion)
        
        random.shuffle(potions)
        for potion in potions:
            current_potions = connection.execute(sqlalchemy.text(potion_type_sql), 
                                        [{"potion_type": potion.potion_type}]).scalar_one()
            inventory_max = list_floor_division(ml_inventory, potion.potion_type)
            threshold_max = potion_threshold - current_potions
            quantity = min(inventory_max, threshold_max, available_potions)
            if quantity > 0:
                bottling_plan.append(
                                    {"potion_type": potion.potion_type, 
                                        "quantity": quantity
                                    }
                            )
                ml_inventory = [ml_inventory[i] - quantity * potion.potion_type[i] for i in range(4)]
                available_potions -= quantity
        print(f"bottling_plan: {bottling_plan}, leftover inventory: {ml_inventory}")
        return bottling_plan