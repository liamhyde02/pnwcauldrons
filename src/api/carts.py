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
    search_sql = "SELECT cart_items.id, cart_items.item_sku, carts.customer_name, potion_catalog_items.price * cart_items.quantity as line_item_total, cart_items.created_at as timestamp FROM cart_items JOIN carts ON cart_items.cart_id = carts.id JOIN potion_catalog_items ON cart_items.item_sku = potion_catalog_items.sku WHERE carts.customer_name ILIKE :customer_name AND cart_items.item_sku ILIKE :item_sku ORDER BY {} {} LIMIT 5".format(sort_col, sort_order)
    search_results = []
    with db.engine.begin() as connection:
        result = connection.execute(sqlalchemy.text(search_sql), 
                                    [{"customer_name": f"%{customer_name}%", 
                                      "item_sku": f"%{potion_sku}%"}])
        results = [row._asdict() for row in result.fetchall()]
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
    return {"previous": "",
            "next": "",
            "results": search_results}

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

    with db.engine.begin() as connection:
        # day = connection.execute(sqlalchemy.text(get_day_sql)).scalar_one()
        # for customer in customers:
        #     connection.execute(sqlalchemy.text(visits_entry_sql), 
        #                        [{"customer_name": customer.customer_name, 
        #                          "character_class": customer.character_class, 
        #                          "level": customer.level,
        #                          "day": day}])
        # Get the current day
        day = connection.execute(sqlalchemy.select([global_time.c.day])).scalar_one()
        for customer in customers:
            # Insert the visit
            connection.execute(
                sqlalchemy.insert(
                    visits
                    ).values(
                        customer_name=customer.customer_name,
                        character_class=customer.character_class,
                        level=customer.level,
                        day=day
                    )
            )
    return "OK"


@router.post("/")
def create_cart(new_cart: Customer):
    """ """
    # Set up the tables
    metadata = sqlalchemy.MetaData()
    carts = sqlalchemy.Table("carts", metadata, autoload_with=db.engine)

    with db.engine.begin() as connection:
        # Insert the cart
        cart_id = connection.execute(sqlalchemy.insert(
            carts).values(
                customer_name=new_cart.customer_name,
                character_class=new_cart.character_class,
                level=new_cart.level
                ).returning(
                    carts.c.id
                    )).scalar_one()
    # Log the cart_id, customer_name, character_class, and level
    print(f"cart_id: {cart_id} customer_name: {new_cart.customer_name} character_class: {new_cart.character_class} level: {new_cart.level}")
    return {"cart_id": cart_id}


class CartItem(BaseModel):
    quantity: int


@router.post("/{cart_id}/items/{item_sku}")
def set_item_quantity(cart_id: int, item_sku: str, cart_item: CartItem):
    """ """
    # Log the cart_id, item_sku, and quantity
    print(f"cart_id: {cart_id} item_sku: {item_sku} quantity: {cart_item.quantity}")
    # Set up the tables
    metadata = sqlalchemy.MetaData()
    cart_items = sqlalchemy.Table("cart_items", metadata, autoload_with=db.engine)
    with db.engine.begin() as connection:
        # Insert the cart item
        connection.execute(
            sqlalchemy.insert(
                cart_items
                ).values(
                    cart_id=cart_id,
                    item_sku=item_sku,
                    quantity=cart_item.quantity
                )
        )
    return "OK"


class CartCheckout(BaseModel):
    payment: str

@router.post("/{cart_id}/checkout")
def checkout(cart_id: int, cart_checkout: CartCheckout):
    """ """
    # Log the cart_id and payment
    print(f"cart_id: {cart_id} payment: {cart_checkout.payment}")
    
    # Set up the tables
    metadata = sqlalchemy.MetaData()
    potions = sqlalchemy.Table("potion_ledger", metadata, autoload_with=db.engine)
    cart_items = sqlalchemy.Table("cart_items", metadata, autoload_with=db.engine)
    potion_catalog_items = sqlalchemy.Table("potion_catalog_items", metadata, autoload_with=db.engine)
    carts = sqlalchemy.Table("carts", metadata, autoload_with=db.engine)
    processed = sqlalchemy.Table("processed", metadata, autoload_with=db.engine)
    gold_ledger = sqlalchemy.Table("gold_ledger", metadata, autoload_with=db.engine)
    class_preferences = sqlalchemy.Table("class_preferences", metadata, autoload_with=db.engine)

    # Initialize the total quantity of potions bought and the total gold paid
    total_quantity = 0
    total_gold = 0
    with db.engine.begin() as connection:
        # Get the character class of the customer
        character_class = connection.execute(
            sqlalchemy.select(
                [carts.c.character_class]
                ).where(carts.c.id == cart_id)
                ).scalar_one()
        # Get the processed id
        processed_id = connection.execute(
            sqlalchemy.insert(
                processed
                ).values(
                    order_id=cart_id,
                    type="checkout"
                ).returning(processed.c.id)
                ).scalar_one()
        # Get the items in the customer's cart
        cart_items = connection.execute(
            sqlalchemy.select(
                [cart_items.c.item_sku, 
                 cart_items.c.quantity]
                ).where(cart_items.c.cart_id == cart_id)
                ).fetchall()

        for cart_item in cart_items:   
            # Get the potion type and price of the item
            potion_type, price = connection.execute(
                sqlalchemy.select(
                    [potion_catalog_items.c.potion_type,
                        potion_catalog_items.c.price]
                    ).where(potion_catalog_items.c.sku == cart_item.item_sku)
            )
            # Update the potion ledger
            connection.execute(
                sqlalchemy.insert(
                    potions
                    ).values(
                        processed_id=processed_id,
                        potion_type=potion_type,
                        quantity=-cart_item.quantity
                    )
            )
            # Update the gold ledger
            connection.execute(
                sqlalchemy.insert(
                    gold_ledger
                    ).values(
                        processed_id=processed_id,
                        gold=price * cart_item.quantity
                    )
            )
            # Update the class preferences
            connection.execute(
                sqlalchemy.insert(
                    class_preferences
                    ).values(
                        character_class=character_class,
                        potion_type=potion_type
                    )
            )
            total_gold += price * cart_item.quantity
            total_quantity += cart_item.quantity
    # Return the total quantity of potions bought and the total gold paid
    return {"total_potions_bought": total_quantity, "total_gold_paid": total_gold}
