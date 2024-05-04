from fastapi import APIRouter
import sqlalchemy
from src import database as db
import random

router = APIRouter()


@router.get("/catalog/", tags=["catalog"])
def get_catalog():
    """
    Each unique item combination must have only a single price.
    """
    potion_quantity_sql = "SELECT potion_catalog_items.sku as sku, potion_catalog_items.name as name, potion_ledger.potion_type as potion_type, SUM(potion_ledger.quantity) as quantity, potion_catalog_items.price FROM potion_ledger JOIN potion_catalog_items ON potion_ledger.potion_type = potion_catalog_items.potion_type GROUP BY potion_catalog_items.sku, potion_catalog_items.name, potion_ledger.potion_type, potion_catalog_items.price having SUM(potion_ledger.quantity) > 0"
    visits_sql = "SELECT character_class, COUNT(character_class) as total_characters FROM visits JOIN global_time ON visits.day = global_time.day GROUP BY character_class"
    class_preference_sql = "SELECT potion_type, COALESCE(COUNT(potion_type), 0) as amount_bought FROM class_preferences WHERE character_class = :character_class GROUP BY potion_type, character_class"
    total_potions_sql = "SELECT potions, potion_capacity from inventory"
    with db.engine.begin() as connection:
        potions = connection.execute(sqlalchemy.text(potion_quantity_sql)).fetchall()
        result = connection.execute(sqlalchemy.text(visits_sql)).fetchall()
        visits = [row._asdict() for row in result]
        if len(visits) == 0:
            print("No recorded visits")
            selected_classes = []
        else:
            weights = [(pref["character_class"], pref["total_characters"]) for pref in visits]
            selected_classes = random.choices(
                [weight[0] for weight in weights], 
                weights=[weight[1] for weight in weights],
                k=3
            )
        print(f"selected_classes: {selected_classes}")
        total_potions, potion_capacity = connection.execute(sqlalchemy.text(total_potions_sql)).fetchone()
        if total_potions / (potion_capacity * 50) < 0.2:
            print("Low inventory, no class preferences")
            sorted_classes = []
        fire_sale = False
        if potion_capacity > 2 and total_potions / (potion_capacity * 50) > 0.6:
            print("FIRE SALE!!!")
            fire_sale = True
            
        catalog = []
        listed_items = 0
        for character_class in selected_classes:
            class_preference = connection.execute(sqlalchemy.text(class_preference_sql), 
                                                  [{"character_class": character_class}]).fetchall()
            class_preference = [row._asdict() for row in class_preference]
            if len(class_preference) == 0:
                print(f"character_class: {character_class}, class_preference: No preference yet")
            else: 
                weighted_choices = [(pref['potion_type'], pref['amount_bought']) for pref in class_preference]
                selected_potion = random.choices(
                    [choice[0] for choice in weighted_choices], 
                    weights=[choice[1] for choice in weighted_choices],
                    k=1
                )[0]
                print(f"character_class: {character_class}, class_preference: {class_preference}, selected_potion: {selected_potion}")
                for potion in potions:
                    if potion.potion_type == selected_potion:
                        catalog.append(
                            {
                                "sku": potion.sku,
                                "name": potion.name,
                                "quantity": potion.quantity,
                                "price": (int(.9 * (int(potion.price * 0.75)) if fire_sale else potion.price)),
                                "potion_type": potion.potion_type
                            }
                        )
                        listed_items += 1
                        potions.remove(potion)
            if listed_items > 4:
                break
            if len(potions) == 0:
                break
        print(f"trained_catalog: {catalog}")
        
        random.shuffle(potions)
        while len(potions) > 0 and listed_items < 6:
            potion = potions.pop()
            catalog.append(
                {
                    "sku": potion.sku,
                    "name": potion.name,
                    "quantity": potion.quantity,
                    "price": (int(potion.price * 0.75)) if fire_sale else potion.price,
                    "potion_type": potion.potion_type
                }
            )
            listed_items += 1
        print(f"catalog: {catalog}, unlisted items: {potions}")
        return catalog