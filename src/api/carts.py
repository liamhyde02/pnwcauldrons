from random import randint
from fastapi import APIRouter, Depends, Request
from pydantic import BaseModel
from src.api import auth
from enum import Enum
import sqlalchemy
from src import database as db
from src.api.helpers import potion_type_tostr

router = APIRouter(
    prefix="/carts",
    tags=["cart"],
    dependencies=[Depends(auth.get_api_key)],
)

class search_sort_options(str, Enum):
    customer_name = "customer_name"
    item_sku = "item_sku"
    line_item_total = "line_item_total"
    timestamp = "timestamp"

class search_sort_order(str, Enum):
    asc = "asc"
    desc = "desc"   

@router.get("/search/", tags=["search"])
def search_orders(
    customer_name: str = "",
    potion_sku: str = "",
    search_page: str = "",
    sort_col: search_sort_options = search_sort_options.timestamp,
    sort_order: search_sort_order = search_sort_order.desc,
):
    """
    Search for cart line items by customer name and/or potion sku.

    Customer name and potion sku filter to orders that contain the 
    string (case insensitive). If the filters aren't provided, no
    filtering occurs on the respective search term.

    Search page is a cursor for pagination. The response to this
    search endpoint will return previous or next if there is a
    previous or next page of results available. The token passed
    in that search response can be passed in the next search request
    as search page to get that page of results.

    Sort col is which column to sort by and sort order is the direction
    of the search. They default to searching by timestamp of the order
    in descending order.

    The response itself contains a previous and next page token (if
    such pages exist) and the results as an array of line items. Each
    line item contains the line item id (must be unique), item sku, 
    customer name, line item total (in gold), and timestamp of the order.
    Your results must be paginated, the max results you can return at any
    time is 5 total line items.
    """
    offset = 0
    if search_page != "":
        offset = int(search_page) * 5
    search_sql = "SELECT cart_items.id, cart_items.item_sku, carts.customer_name, potion_catalog_items.price * cart_items.quantity as line_item_total, cart_items.created_at as timestamp FROM cart_items JOIN carts ON cart_items.cart_id = carts.id JOIN potion_catalog_items ON cart_items.item_sku = potion_catalog_items.sku WHERE carts.customer_name ILIKE :customer_name AND cart_items.item_sku ILIKE :item_sku ORDER BY {} {} LIMIT 5 OFFSET :offset".format(sort_col, sort_order)
    search_results = []
    # Set up the tables
    metadata = sqlalchemy.MetaData()
    carts = sqlalchemy.Table("carts", metadata, autoload_with=db.engine)
    cart_items = sqlalchemy.Table("cart_items", metadata, autoload_with=db.engine)
    potion_catalog_items = sqlalchemy.Table("potion_catalog_items", metadata, autoload_with=db.engine)

    # Initialize Statement
    search_stmt = sqlalchemy.select(
        cart_items.c.id.label("id"), 
        cart_items.c.item_sku, 
        carts.c.customer_name, 
        (potion_catalog_items.c.price * cart_items.c.quantity).label("line_item_total"), 
        cart_items.c.created_at.label("timestamp")
        ).select_from(
            cart_items.join(
                carts, cart_items.c.cart_id == carts.c.id
                ).join(
                    potion_catalog_items, cart_items.c.item_sku == potion_catalog_items.c.sku
                )
        ).limit(5
        ).offset(offset
        )
    if customer_name != "":
        search_stmt = search_stmt.where(carts.c.customer_name.ilike(customer_name))
    if potion_sku != "":
        search_stmt = search_stmt.where(cart_items.c.item_sku.ilike(potion_sku))
    search_stmt.order_by(sort_col, sort_order)
    with db.engine.begin() as connection:
        result = connection.execute(search_stmt)
        results = [row._asdict() for row in result.fetchall()]
        results = sorted(results, key=lambda x: x["id"], reverse=(sort_order == "asc"))
        print(f"results: {results}")
        for row in results:
            search_results.append(
                {
                    "line_item_id": row["id"],
                    "item_sku": row["item_sku"],
                    "customer_name": row["customer_name"],
                    "line_item_total": row["line_item_total"],
                    "timestamp": row["timestamp"],
                }
            )
    if search_page == "":
        next = 1
    else:
        next = str(int(search_page) + 1)
    previous = search_page
    return {
        "previous": previous,
        "next": next,
        "results": search_results
    }

        
    # return {
    #     "previous": "",
    #     "next": "",
    #     "results": [
    #         {
    #             "line_item_id": 1,
    #             "item_sku": "1 oblivion potion",
    #             "customer_name": "Scaramouche",
    #             "line_item_total": 50,
    #             "timestamp": "2021-01-01T00:00:00Z",
    #         }
    #     ],
    # }


class Customer(BaseModel):
    customer_name: str
    character_class: str
    level: int

@router.post("/visits/{visit_id}")
def post_visits(visit_id: int, customers: list[Customer]):
    """
    Which customers visited the shop today?
    """
    # Log the visit_id and customers
    print(f"visit_id: {visit_id} customers: {customers}")
    # Set up the tables
    metadata = sqlalchemy.MetaData()
    visits = sqlalchemy.Table("visits", metadata, autoload_with=db.engine)
    global_time = sqlalchemy.Table("global_time", metadata, autoload_with=db.engine)
    get_day_sql = "SELECT day FROM global_time"
    visits_entry_sql = "INSERT INTO visits (customer_name, character_class, level, day) VALUES (:customer_name, :character_class, :level, :day)"
    with db.engine.begin() as connection:
        day = connection.execute(sqlalchemy.text(get_day_sql)).scalar_one()
        for customer in customers:
            connection.execute(sqlalchemy.text(visits_entry_sql), 
                               [{"customer_name": customer.customer_name, 
                                 "character_class": customer.character_class, 
                                 "level": customer.level,
                                 "day": day}])
        # # Get the current day
        # day = connection.execute(sqlalchemy.select([global_time.c.day])).scalar_one()
        # for customer in customers:
        #     # Insert the visit
        #     connection.execute(
        #         sqlalchemy.insert(
        #             visits
        #             ).values(
        #                 customer_name=customer.customer_name,
        #                 character_class=customer.character_class,
        #                 level=customer.level,
        #                 day=day
        #             )
        #     )
    return "OK"


@router.post("/")
def create_cart(new_cart: Customer):
    """ """
    metadata = sqlalchemy.MetaData()
    # carts = sqlalchemy.Table("carts", metadata, autoload_with=db.engine)
    # cart_insert_stmt = sqlalchemy.insert(
    #     carts
    #     ).values(
    #         customer_name=new_cart.customer_name,
    #         character_class=new_cart.character_class,
    #         level=new_cart.level
    #     ).returning(carts.c.id)
    with db.engine.begin() as connection:
        cart_insert_stmt = "INSERT INTO carts (customer_name, character_class, level) VALUES (:customer_name, :character_class, :level) RETURNING id"
        cart_id = connection.execute(sqlalchemy.text(cart_insert_stmt),
                                     [{"customer_name": new_cart.customer_name, "character_class": new_cart.character_class, "level": new_cart.level}]).scalar_one()
    print(f"cart_id: {cart_id} customer_name: {new_cart.customer_name} character_class: {new_cart.character_class} level: {new_cart.level}")
    return {"cart_id": cart_id}


class CartItem(BaseModel):
    quantity: int


@router.post("/{cart_id}/items/{item_sku}")
def set_item_quantity(cart_id: int, item_sku: str, cart_item: CartItem):
    """ """
    # Log the cart_id, item_sku, and quantity
    print(f"cart_id: {cart_id} item_sku: {item_sku} quantity: {cart_item.quantity}")
    metadata = sqlalchemy.MetaData()
    # cart_items = sqlalchemy.Table("cart_items", metadata, autoload_with=db.engine)
    # cart_items_insert_stmt = sqlalchemy.insert(
    #     cart_id=cart_id,
    #     item_sku=item_sku,
    #     quantity=cart_item.quantity
    # )
    sql_to_execute = "INSERT INTO cart_items (cart_id, item_sku, quantity) VALUES (:cart_id, :item_sku, :quantity)"
    with db.engine.begin() as connection:
        connection.execute(sqlalchemy.text(sql_to_execute),
                           [{"cart_id": cart_id, "item_sku": item_sku, "quantity": cart_item.quantity}])
        # connection.execute(cart_items_insert_stmt)
    return "OK"


class CartCheckout(BaseModel):
    payment: str

@router.post("/{cart_id}/checkout")
def checkout(cart_id: int, cart_checkout: CartCheckout):
    """ """
    # Log the cart_id and payment
    print(f"cart_id: {cart_id} payment: {cart_checkout.payment}")
    total_quantity = 0
    total_gold = 0
    cart_items_sql = "SELECT * FROM cart_items WHERE cart_id = :cart_id"
    update_timestamp_sql = "UPDATE potion_catalog_items SET last_selected = NOW() WHERE sku = :sku"
    processed_entry_sql = "INSERT INTO processed (order_id, type) VALUES (:order_id, 'checkout') RETURNING id"
    potion_type_sql = "SELECT potion_type, price FROM potion_catalog_items WHERE sku = :sku"
    potion_update_sql = "INSERT INTO potion_ledger (processed_id, potion_type, quantity) VALUES (:processed_id, :potion_type, :quantity)"
    gold_sql = "INSERT INTO gold_ledger (processed_id, gold) VALUES (:processed_id, :gold)"
    potion_price_sql = "SELECT price FROM potion_catalog_items WHERE sku = :sku"
    character_class_sql = "SELECT character_class FROM carts WHERE id = :cart_id"
    preferences_insert_sql = "INSERT INTO class_preferences (character_class, potion_type) VALUES (:character_class, :potion_type)"
    metadata = sqlalchemy.MetaData()
    potions = sqlalchemy.Table("potion_ledger", metadata, autoload_with=db.engine)
    cart_items = sqlalchemy.Table("cart_items", metadata, autoload_with=db.engine)
    potion_catalog_items = sqlalchemy.Table("potion_catalog_items", metadata, autoload_with=db.engine)

    with db.engine.begin() as connection:
        character_class = connection.execute(sqlalchemy.text(character_class_sql), 
                                             [{"cart_id": cart_id}]).scalar_one()
        processed_id = connection.execute(sqlalchemy.text(processed_entry_sql),
                                [{"order_id": cart_id}]).scalar_one()
        result = connection.execute(sqlalchemy.text(cart_items_sql),
                                    [{"cart_id": cart_id}])
        cart_items = [row for row in result]
        for cart_item in cart_items:   
            potion_type = connection.execute(sqlalchemy.text(potion_type_sql), 
                                             [{"sku": cart_item.item_sku}]).scalar_one()
            connection.execute(sqlalchemy.text(update_timestamp_sql), 
                               [{"sku": cart_item.item_sku}])
            connection.execute(sqlalchemy.text(potion_update_sql), 
                               [{"processed_id": processed_id, 
                                 "potion_type": potion_type, 
                                 "quantity": -cart_item.quantity}])
            price = connection.execute(sqlalchemy.text(potion_price_sql),
                                        [{"sku": cart_item.item_sku}]).scalar_one()
            connection.execute(sqlalchemy.text(gold_sql), 
                               [{"processed_id": processed_id, 
                                 "gold": price * cart_item.quantity}])
            connection.execute(sqlalchemy.text(preferences_insert_sql),
                                 [{"character_class": character_class, 
                                    "potion_type": potion_type}])
            total_gold += price * cart_item.quantity
            total_quantity += cart_item.quantity
    # Return the total quantity of potions bought and the total gold paid
    return {"total_potions_bought": total_quantity, "total_gold_paid": total_gold}
