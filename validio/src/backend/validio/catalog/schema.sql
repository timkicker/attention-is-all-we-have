create table product (
  id text primary key, json text not null, name_en text, name_fi text, category text, vendor text,
  sales_unit text, base_unit text, base_volume_l real, base_weight_kg real, lacs_g real,
  temperature integer, deleted integer, has_allergen_data integer,
  marketing_en text, key_ingredients_en text
);
create table claim (product_id text, claim text);
create table allergen (product_id text, code text, level text);
create table unit (product_id text, unit_id text, size_in_base real);
create table substitution (product_id text, substitute_id text, position integer);
create table reliability (product_id text primary key, value real);
create table carbon (product_id text primary key, kg_co2e_per_kg real);
create table label (product_id text, code text);
create table planted (product_id text, language text, text text, note text);
create virtual table product_fts using fts5(id unindexed, name_en, name_fi, name_sv);
create index claim_p on claim(product_id);
create index claim_c on claim(claim);
create index allergen_p on allergen(product_id);
create index unit_p on unit(product_id);
create index subst_p on substitution(product_id);
create index label_p on label(product_id);
create index product_cat on product(category);
