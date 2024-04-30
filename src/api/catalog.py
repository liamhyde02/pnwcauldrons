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
    potion_quantity_sql = "SELECT potion_type, SUM(quantity) as potion_quantity FROM potions GROUP BY potion_type having SUM(quantity) > 0"
    potion_catalog_sql = "SELECT * FROM potion_catalog_items WHERE potion_type = :potion_type"
    visits_sql = "SELECT character_class, COUNT(character_class) as total_characters FROM visits JOIN global_time ON visits.day = global_time.day GROUP BY character_class"
    class_preference_sql = "SELECT potion_type, COALESCE(COUNT(potion_type), 0) as amount_bought FROM class_preferences WHERE character_class = :character_class GROUP BY potion_type, character_class"
    with db.engine.begin() as connection:
        result = connection.execute(sqlalchemy.text(potion_quantity_sql))
        potions = [row._asdict() for row in result.fetchall()]
        result = connection.execute(sqlalchemy.text(visits_sql)).fetchall()
        visits = [row._asdict() for row in result]
        class_totals = {visit["character_class"]: visit["total_characters"] for visit in visits}
        sorted_classes = sorted(class_totals, key=lambda x: class_totals[x], reverse=True)

        catalog = []
        listed_items = 0
        for character_class in sorted_classes:
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
                for potion in potions:
                    if potion["potion_type"] == selected_potion:
                        catalog_entry = connection.execute(sqlalchemy.text(potion_catalog_sql), 
                                                    [{"potion_type": potion["potion_type"]}]).fetchone()._asdict()
                        catalog.append(
                            {
                                "sku": catalog_entry["sku"],
                                "name": catalog_entry["name"],
                                "quantity": potion["potion_quantity"],
                                "price": catalog_entry["price"],
                                "potion_type": catalog_entry["potion_type"],
                            }
                        )
                        listed_items += 1
                        potions.remove(potion)
                if listed_items >= 6:
                    break
                if len(potions) == 0:
                    break
                print(f"character_class: {character_class}, class_preference: {class_preference}, selected_potion: {selected_potion}")
        if listed_items < 6 and len(potions) > 0:
            for potion in potions:
                catalog_entry = connection.execute(sqlalchemy.text(potion_catalog_sql), 
                                            [{"potion_type": potion["potion_type"]}]).fetchone()._asdict()
                catalog.append(
                    {
                        "sku": catalog_entry["sku"],
                        "name": catalog_entry["name"],
                        "quantity": potion["potion_quantity"],
                        "price": catalog_entry["price"],
                        "potion_type": catalog_entry["potion_type"],
                    }
                )
                listed_items += 1
                if listed_items >= 6:
                    break
        print(f"catalog: {catalog}")
        return catalog