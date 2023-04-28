--change the work_order_cnc.sale_product_id ondelete to 'restrict'
alter table "cnc_id_rel" drop CONSTRAINT "cnc_id_rel_id_id_fkey";
alter table "cnc_id_rel" add CONSTRAINT "cnc_id_rel_id_id_fkey" FOREIGN KEY (id_id) REFERENCES sale_product(id) ON DELETE RESTRICT;
alter TABLE "stock_picking" drop CONSTRAINT "stock_picking_mr_sale_prod_id_fkey";