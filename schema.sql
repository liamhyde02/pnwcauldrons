create table global_time (
  id bigint not null primary key,
  created_at timestamp default now() not null,
  day text,
  hour smallint
);

create table global_plan (
  id bigint not null primary key,
  created_at timestamp default now() not null,
  potion_capacity_units integer,
  ml_capacity_units integer,
  order_id integer
);

create table barrels (
  id bigint not null primary key,
  created_at timestamp default now() not null,
  potion_ml integer,
  barrel_type integer[],
  order_id integer
);

create table carts (
  id bigint not null primary key,
  created_at timestamp default now() not null,
  customer_name text,
  character_class text,
  "level" smallint
);

create table global_inventory (
  id bigint not null primary key,
  created_at timestamp default now() not null,
  ml_threshold integer,
  potion_capacity_plan integer,
  ml_capacity_plan integer,
  potion_threshold integer
);

create table gold_ledger (
  id bigint not null primary key,
  created_at timestamp default now() not null,
  order_id integer,
  gold integer
);

create table potions (
  id bigint not null primary key,
  created_at timestamp default now() not null,
  order_id integer,
  potion_type integer[],
  quantity integer
);

create table potion_catalog_items (
  id bigint not null primary key,
  created_at timestamp default now() not null,
  sku text,
  name text,
  price smallint,
  potion_type smallint[],
  tick_id smallint,
  shop_id smallint
);

create table processed (
  id bigint not null primary key,
  created_at timestamp default now() not null,
  order_id integer,
  order_type text
);

create table cart_items (
  id bigint not null primary key,
  created_at timestamp default now() not null,
  item_sku text,
  cart_id integer,
  quantity integer
);

