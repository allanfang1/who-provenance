-- TRUNCATE TABLE
--     s_purchase_lineitem,
--     s_purchase,
--     s_catalog_order,
--     s_web_order,
--     s_catalog_order_lineitem,
--     s_web_order_lineitem,
--     s_store_returns,
--     s_catalog_returns,
--     s_inventory,
--     s_web_returns
-- RESTART IDENTITY
-- CASCADE;

DELETE FROM store_returns sr
USING store_sales ss, date_dim d, delete_dates dd
WHERE sr.sr_ticket_number = ss.ss_ticket_number
  AND sr.sr_item_sk       = ss.ss_item_sk
  AND ss.ss_sold_date_sk  = d.d_date_sk
  AND d.d_date BETWEEN dd.start_date AND dd.end_date;

DELETE FROM store_sales ss
USING date_dim d, delete_dates dd
WHERE ss.ss_sold_date_sk = d.d_date_sk
  AND d.d_date BETWEEN dd.start_date AND dd.end_date;

DELETE FROM catalog_returns cr
USING catalog_sales cs, date_dim d, delete_dates dd
WHERE cr.cr_order_number = cs.cs_order_number
  AND cr.cr_item_sk      = cs.cs_item_sk
  AND cs.cs_sold_date_sk = d.d_date_sk
  AND d.d_date BETWEEN dd.start_date AND dd.end_date;

DELETE FROM catalog_sales cs
USING date_dim d, delete_dates dd
WHERE cs.cs_sold_date_sk = d.d_date_sk
  AND d.d_date BETWEEN dd.start_date AND dd.end_date;

DELETE FROM web_returns wr
USING web_sales ws, date_dim d, delete_dates dd
WHERE wr.wr_order_number = ws.ws_order_number
  AND wr.wr_item_sk      = ws.ws_item_sk
  AND ws.ws_sold_date_sk = d.d_date_sk
  AND d.d_date BETWEEN dd.start_date AND dd.end_date;

DELETE FROM web_sales ws
USING date_dim d, delete_dates dd
WHERE ws.ws_sold_date_sk = d.d_date_sk
  AND d.d_date BETWEEN dd.start_date AND dd.end_date;

DELETE FROM inventory inv
  USING date_dim d, inventory_delete_dates dd
  WHERE inv.inv_date_sk = d.d_date_sk
    AND d.d_date BETWEEN dd.start_date AND dd.end_date;

DROP TABLE delete_dates;
DROP TABLE inventory_delete_dates;

CREATE TEMP VIEW crv AS 
SELECT 
    d_date_sk                                       AS cr_returned_date_sk,
    t_time_sk                                       AS cr_returned_time_sk,
    i_item_sk                                       AS cr_item_sk,
    c1.c_customer_sk                                AS cr_refunded_customer_sk,
    c1.c_current_cdemo_sk                           AS cr_refunded_cdemo_sk,
    c1.c_current_hdemo_sk                           AS cr_refunded_hdemo_sk,
    c1.c_current_addr_sk                            AS cr_refunded_addr_sk,
    c2.c_customer_sk                                AS cr_returning_customer_sk,
    c2.c_current_cdemo_sk                           AS cr_returning_cdemo_sk,
    c2.c_current_hdemo_sk                           AS cr_returning_hdemo_sk,
    c2.c_current_addr_sk                            AS cr_returning_addr_sk,
    cc_call_center_sk                               AS cr_call_center_sk,
    cp_catalog_page_sk                              AS cr_catalog_page_sk,
    sm_ship_mode_sk                                 AS cr_ship_mode_sk,
    w_warehouse_sk                                  AS cr_warehouse_sk,
    r_reason_sk                                     AS cr_reason_sk,
    cret_order_id                                   AS cr_order_number,
    cret_return_qty                                 AS cr_return_quantity,
    cret_return_amt                                 AS cr_return_amount,
    cret_return_tax                                 AS cr_return_tax,
    cret_return_amt + cret_return_tax               AS cr_return_amt_inc_tax,
    cret_return_fee                                 AS cr_fee,
    cret_return_ship_cost                           AS cr_return_ship_cost,
    cret_refunded_cash                              AS cr_refunded_cash,
    cret_reversed_charge                            AS cr_reversed_charge,
    cret_merchant_credit                            AS cr_store_credit,
    cret_return_amt + cret_return_tax + cret_return_fee 
      - cret_refunded_cash - cret_reversed_charge - cret_merchant_credit AS cr_net_loss
FROM s_catalog_returns   
LEFT OUTER JOIN date_dim      ON (CAST(cret_return_date AS date) = d_date) 
LEFT OUTER JOIN time_dim      ON (
    (CAST(SUBSTR(cret_return_time, 1, 2) AS integer) * 3600 
   + CAST(SUBSTR(cret_return_time, 4, 2) AS integer) * 60 
   + CAST(SUBSTR(cret_return_time, 7, 2) AS integer)) = t_time
) 
LEFT OUTER JOIN item          ON (cret_item_id = i_item_id) 
LEFT OUTER JOIN customer c1   ON (cret_return_customer_id = c1.c_customer_id) 
LEFT OUTER JOIN customer c2   ON (cret_refund_customer_id = c2.c_customer_id) 
LEFT OUTER JOIN reason        ON (cret_reason_id = r_reason_id) 
LEFT OUTER JOIN call_center   ON (cret_call_center_id = cc_call_center_id) 
LEFT OUTER JOIN catalog_page  ON (cret_catalog_page_id = cp_catalog_page_id) 
LEFT OUTER JOIN ship_mode     ON (cret_shipmode_id = sm_ship_mode_id) 
LEFT OUTER JOIN warehouse     ON (cret_warehouse_id = w_warehouse_id) 
WHERE i_rec_end_date IS NULL 
  AND cc_rec_end_date IS NULL;


INSERT INTO catalog_returns (
    cr_returned_date_sk,
    cr_returned_time_sk,
    cr_item_sk,
    cr_refunded_customer_sk,
    cr_refunded_cdemo_sk,
    cr_refunded_hdemo_sk,
    cr_refunded_addr_sk,
    cr_returning_customer_sk,
    cr_returning_cdemo_sk,
    cr_returning_hdemo_sk,
    cr_returning_addr_sk,
    cr_call_center_sk,
    cr_catalog_page_sk,
    cr_ship_mode_sk,
    cr_warehouse_sk,
    cr_reason_sk,
    cr_order_number,
    cr_return_quantity,
    cr_return_amount,
    cr_return_tax,
    cr_return_amt_inc_tax,
    cr_fee,
    cr_return_ship_cost,
    cr_refunded_cash,
    cr_reversed_charge,
    cr_store_credit,
    cr_net_loss
)
SELECT 
    cr_returned_date_sk,
    cr_returned_time_sk,
    cr_item_sk,
    cr_refunded_customer_sk,
    cr_refunded_cdemo_sk,
    cr_refunded_hdemo_sk,
    cr_refunded_addr_sk,
    cr_returning_customer_sk,
    cr_returning_cdemo_sk,
    cr_returning_hdemo_sk,
    cr_returning_addr_sk,
    cr_call_center_sk,
    cr_catalog_page_sk,
    cr_ship_mode_sk,
    cr_warehouse_sk,
    cr_reason_sk,
    cr_order_number,
    cr_return_quantity,
    cr_return_amount,
    cr_return_tax,
    cr_return_amt_inc_tax,
    cr_fee,
    cr_return_ship_cost,
    cr_refunded_cash,
    cr_reversed_charge,
    cr_store_credit,
    cr_net_loss
FROM crv;

CREATE TEMP VIEW csv AS 
SELECT 
    d1.d_date_sk                                                              AS cs_sold_date_sk,
    t_time_sk                                                                 AS cs_sold_time_sk,
    d2.d_date_sk                                                              AS cs_ship_date_sk,
    c1.c_customer_sk                                                          AS cs_bill_customer_sk,
    c1.c_current_cdemo_sk                                                     AS cs_bill_cdemo_sk,
    c1.c_current_hdemo_sk                                                     AS cs_bill_hdemo_sk,
    c1.c_current_addr_sk                                                      AS cs_bill_addr_sk,
    c2.c_customer_sk                                                          AS cs_ship_customer_sk,
    c2.c_current_cdemo_sk                                                     AS cs_ship_cdemo_sk,
    c2.c_current_hdemo_sk                                                     AS cs_ship_hdemo_sk,
    c2.c_current_addr_sk                                                      AS cs_ship_addr_sk,
    cc_call_center_sk                                                         AS cs_call_center_sk,
    cp_catalog_page_sk                                                        AS cs_catalog_page_sk,
    sm_ship_mode_sk                                                           AS cs_ship_mode_sk,
    w_warehouse_sk                                                            AS cs_warehouse_sk,
    i_item_sk                                                                 AS cs_item_sk,
    p_promo_sk                                                                AS cs_promo_sk,
    cord_order_id                                                             AS cs_order_number,
    clin_quantity                                                             AS cs_quantity,
    i_wholesale_cost                                                          AS cs_wholesale_cost,
    i_current_price                                                           AS cs_list_price,
    clin_sales_price                                                          AS cs_sales_price,
    (i_current_price - clin_sales_price) * clin_quantity                      AS cs_ext_discount_amt,
    clin_sales_price * clin_quantity                                          AS cs_ext_sales_price,
    i_wholesale_cost * clin_quantity                                          AS cs_ext_wholesale_cost,
    i_current_price * clin_quantity                                           AS cs_ext_list_price,
    i_current_price * cc_tax_percentage                                       AS cs_ext_tax,
    clin_coupon_amt                                                           AS cs_coupon_amt,
    clin_ship_cost * clin_quantity                                            AS cs_ext_ship_cost,
    (clin_sales_price * clin_quantity) - clin_coupon_amt                     AS cs_net_paid,
    ((clin_sales_price * clin_quantity) - clin_coupon_amt) * (1 + cc_tax_percentage) AS cs_net_paid_inc_tax,
    (clin_sales_price * clin_quantity) - clin_coupon_amt 
      + (clin_ship_cost * clin_quantity)                                      AS cs_net_paid_inc_ship,
    (clin_sales_price * clin_quantity) - clin_coupon_amt 
      + (clin_ship_cost * clin_quantity) 
      + (i_current_price * cc_tax_percentage)                                 AS cs_net_paid_inc_ship_tax,
    ((clin_sales_price * clin_quantity) - clin_coupon_amt) 
      - (clin_quantity * i_wholesale_cost)                                    AS cs_net_profit
FROM s_catalog_order  
LEFT OUTER JOIN date_dim d1 ON (CAST(cord_order_date AS date) = d1.d_date) 
LEFT OUTER JOIN time_dim ON (cord_order_time = t_time) 
LEFT OUTER JOIN customer c1 ON (cord_bill_customer_id = c1.c_customer_id) 
LEFT OUTER JOIN customer c2 ON (cord_ship_customer_id = c2.c_customer_id) 
LEFT OUTER JOIN call_center ON (cord_call_center_id = cc_call_center_id AND cc_rec_end_date IS NULL) 
LEFT OUTER JOIN ship_mode ON (cord_ship_mode_id = sm_ship_mode_id) 
JOIN s_catalog_order_lineitem ON (cord_order_id = clin_order_id) 
LEFT OUTER JOIN date_dim d2 ON (CAST(clin_ship_date AS date) = d2.d_date) 
LEFT OUTER JOIN catalog_page ON (clin_catalog_page_number = cp_catalog_page_number AND clin_catalog_number = cp_catalog_number) 
LEFT OUTER JOIN warehouse ON (clin_warehouse_id = w_warehouse_id) 
LEFT OUTER JOIN item ON (clin_item_id = i_item_id AND i_rec_end_date IS NULL) 
LEFT OUTER JOIN promotion ON (clin_promotion_id = p_promo_id);


INSERT INTO catalog_sales (
    cs_sold_date_sk,
    cs_sold_time_sk,
    cs_ship_date_sk,
    cs_bill_customer_sk,
    cs_bill_cdemo_sk,
    cs_bill_hdemo_sk,
    cs_bill_addr_sk,
    cs_ship_customer_sk,
    cs_ship_cdemo_sk,
    cs_ship_hdemo_sk,
    cs_ship_addr_sk,
    cs_call_center_sk,
    cs_catalog_page_sk,
    cs_ship_mode_sk,
    cs_warehouse_sk,
    cs_item_sk,
    cs_promo_sk,
    cs_order_number,
    cs_quantity,
    cs_wholesale_cost,
    cs_list_price,
    cs_sales_price,
    cs_ext_discount_amt,
    cs_ext_sales_price,
    cs_ext_wholesale_cost,
    cs_ext_list_price,
    cs_ext_tax,
    cs_coupon_amt,
    cs_ext_ship_cost,
    cs_net_paid,
    cs_net_paid_inc_tax,
    cs_net_paid_inc_ship,
    cs_net_paid_inc_ship_tax,
    cs_net_profit
)
SELECT 
    cs_sold_date_sk,
    cs_sold_time_sk,
    cs_ship_date_sk,
    cs_bill_customer_sk,
    cs_bill_cdemo_sk,
    cs_bill_hdemo_sk,
    cs_bill_addr_sk,
    cs_ship_customer_sk,
    cs_ship_cdemo_sk,
    cs_ship_hdemo_sk,
    cs_ship_addr_sk,
    cs_call_center_sk,
    cs_catalog_page_sk,
    cs_ship_mode_sk,
    cs_warehouse_sk,
    cs_item_sk,
    cs_promo_sk,
    cs_order_number,
    cs_quantity,
    cs_wholesale_cost,
    cs_list_price,
    cs_sales_price,
    cs_ext_discount_amt,
    cs_ext_sales_price,
    cs_ext_wholesale_cost,
    cs_ext_list_price,
    cs_ext_tax,
    cs_coupon_amt,
    cs_ext_ship_cost,
    cs_net_paid,
    cs_net_paid_inc_tax,
    cs_net_paid_inc_ship,
    cs_net_paid_inc_ship_tax,
    cs_net_profit
FROM csv;

CREATE TEMP VIEW iv AS 
SELECT 
    d_date_sk       AS inv_date_sk, 
    i_item_sk       AS inv_item_sk, 
    w_warehouse_sk  AS inv_warehouse_sk, 
    invn_qty_on_hand AS inv_quantity_on_hand 
FROM s_inventory 
LEFT OUTER JOIN warehouse ON (invn_warehouse_id = w_warehouse_id) 
LEFT OUTER JOIN item      ON (invn_item_id = i_item_id AND i_rec_end_date IS NULL) 
LEFT OUTER JOIN date_dim  ON (d_date = invn_date::date);


INSERT INTO inventory (
    inv_date_sk,
    inv_item_sk,
    inv_warehouse_sk,
    inv_quantity_on_hand
)
SELECT 
    inv_date_sk,
    inv_item_sk,
    inv_warehouse_sk,
    inv_quantity_on_hand
FROM iv;

CREATE TEMP VIEW srv AS 
SELECT 
    d_date_sk                                       AS sr_returned_date_sk,
    t_time_sk                                       AS sr_return_time_sk,
    i_item_sk                                       AS sr_item_sk,
    c_customer_sk                                   AS sr_customer_sk,
    c_current_cdemo_sk                              AS sr_cdemo_sk,
    c_current_hdemo_sk                              AS sr_hdemo_sk,
    c_current_addr_sk                               AS sr_addr_sk,
    s_store_sk                                      AS sr_store_sk,
    r_reason_sk                                     AS sr_reason_sk,
    sret_ticket_number                              AS sr_ticket_number,
    sret_return_qty                                 AS sr_return_quantity,
    sret_return_amt                                 AS sr_return_amt,
    sret_return_tax                                 AS sr_return_tax,
    sret_return_amt + sret_return_tax               AS sr_return_amt_inc_tax,
    sret_return_fee                                 AS sr_fee,
    sret_return_ship_cost                           AS sr_return_ship_cost,
    sret_refunded_cash                              AS sr_refunded_cash,
    sret_reversed_charge                            AS sr_reversed_charge,
    sret_store_credit                               AS sr_store_credit,
    sret_return_amt + sret_return_tax + sret_return_fee 
      - sret_refunded_cash - sret_reversed_charge - sret_store_credit AS sr_net_loss
FROM s_store_returns   
LEFT OUTER JOIN date_dim  ON (CAST(sret_return_date AS date) = d_date) 
LEFT OUTER JOIN time_dim  ON (
    (CAST(SUBSTR(sret_return_time, 1, 2) AS integer) * 3600 
   + CAST(SUBSTR(sret_return_time, 4, 2) AS integer) * 60 
   + CAST(SUBSTR(sret_return_time, 7, 2) AS integer)) = t_time
) 
LEFT OUTER JOIN item      ON (sret_item_id = i_item_id) 
LEFT OUTER JOIN customer  ON (sret_customer_id = c_customer_id) 
LEFT OUTER JOIN store     ON (sret_store_id = s_store_id) 
LEFT OUTER JOIN reason    ON (sret_reason_id = r_reason_id) 
WHERE i_rec_end_date IS NULL 
  AND s_rec_end_date IS NULL;


INSERT INTO store_returns (
    sr_returned_date_sk,
    sr_return_time_sk,
    sr_item_sk,
    sr_customer_sk,
    sr_cdemo_sk,
    sr_hdemo_sk,
    sr_addr_sk,
    sr_store_sk,
    sr_reason_sk,
    sr_ticket_number,
    sr_return_quantity,
    sr_return_amt,
    sr_return_tax,
    sr_return_amt_inc_tax,
    sr_fee,
    sr_return_ship_cost,
    sr_refunded_cash,
    sr_reversed_charge,
    sr_store_credit,
    sr_net_loss
)
SELECT 
    sr_returned_date_sk,
    sr_return_time_sk,
    sr_item_sk,
    sr_customer_sk,
    sr_cdemo_sk,
    sr_hdemo_sk,
    sr_addr_sk,
    sr_store_sk,
    sr_reason_sk,
    sr_ticket_number::integer,
    sr_return_quantity,
    sr_return_amt,
    sr_return_tax,
    sr_return_amt_inc_tax,
    sr_fee,
    sr_return_ship_cost,
    sr_refunded_cash,
    sr_reversed_charge,
    sr_store_credit,
    sr_net_loss
FROM srv;

CREATE TEMP VIEW ssv AS 
SELECT  
    d_date_sk                                                               AS ss_sold_date_sk,  
    t_time_sk                                                               AS ss_sold_time_sk,  
    i_item_sk                                                               AS ss_item_sk,  
    c_customer_sk                                                           AS ss_customer_sk,  
    c_current_cdemo_sk                                                      AS ss_cdemo_sk,  
    c_current_hdemo_sk                                                      AS ss_hdemo_sk, 
    c_current_addr_sk                                                       AS ss_addr_sk, 
    s_store_sk                                                              AS ss_store_sk,  
    p_promo_sk                                                              AS ss_promo_sk, 
    purc_purchase_id                                                        AS ss_ticket_number,  
    plin_quantity                                                           AS ss_quantity,  
    i_wholesale_cost                                                        AS ss_wholesale_cost,  
    i_current_price                                                         AS ss_list_price, 
    plin_sale_price                                                         AS ss_sales_price, 
    (i_current_price - plin_sale_price) * plin_quantity                     AS ss_ext_discount_amt, 
    plin_sale_price * plin_quantity                                         AS ss_ext_sales_price, 
    i_wholesale_cost * plin_quantity                                        AS ss_ext_wholesale_cost,  
    i_current_price * plin_quantity                                         AS ss_ext_list_price,  
    i_current_price * s_tax_precentage                                      AS ss_ext_tax,  
    plin_coupon_amt                                                         AS ss_coupon_amt, 
    (plin_sale_price * plin_quantity) - plin_coupon_amt                     AS ss_net_paid, 
    ((plin_sale_price * plin_quantity) - plin_coupon_amt) * (1 + s_tax_precentage) AS ss_net_paid_inc_tax, 
    ((plin_sale_price * plin_quantity) - plin_coupon_amt) - (plin_quantity * i_wholesale_cost) AS ss_net_profit 
FROM s_purchase  
LEFT OUTER JOIN customer          ON (purc_customer_id = c_customer_id)  
LEFT OUTER JOIN store             ON (purc_store_id = s_store_id) 
LEFT OUTER JOIN date_dim          ON (CAST(purc_purchase_date AS date) = d_date) 
LEFT OUTER JOIN time_dim          ON (PURC_PURCHASE_TIME = t_time) 
JOIN s_purchase_lineitem          ON (purc_purchase_id = plin_purchase_id) 
LEFT OUTER JOIN promotion         ON (plin_promotion_id = p_promo_id) 
LEFT OUTER JOIN item              ON (plin_item_id = i_item_id) 
WHERE purc_purchase_id = plin_purchase_id 
  AND i_rec_end_date IS NULL 
  AND s_rec_end_date IS NULL;


INSERT INTO store_sales (
    ss_sold_date_sk,
    ss_sold_time_sk,
    ss_item_sk,
    ss_customer_sk,
    ss_cdemo_sk,
    ss_hdemo_sk,
    ss_addr_sk,
    ss_store_sk,
    ss_promo_sk,
    ss_ticket_number,
    ss_quantity,
    ss_wholesale_cost,
    ss_list_price,
    ss_sales_price,
    ss_ext_discount_amt,
    ss_ext_sales_price,
    ss_ext_wholesale_cost,
    ss_ext_list_price,
    ss_ext_tax,
    ss_coupon_amt,
    ss_net_paid,
    ss_net_paid_inc_tax,
    ss_net_profit
)
SELECT 
    ss_sold_date_sk,
    ss_sold_time_sk,
    ss_item_sk,
    ss_customer_sk,
    ss_cdemo_sk,
    ss_hdemo_sk,
    ss_addr_sk,
    ss_store_sk,
    ss_promo_sk,
    ss_ticket_number,
    ss_quantity,
    ss_wholesale_cost,
    ss_list_price,
    ss_sales_price,
    ss_ext_discount_amt,
    ss_ext_sales_price,
    ss_ext_wholesale_cost,
    ss_ext_list_price,
    ss_ext_tax,
    ss_coupon_amt,
    ss_net_paid,
    ss_net_paid_inc_tax,
    ss_net_profit
FROM ssv;

CREATE TEMP VIEW wrv AS 
SELECT 
    d_date_sk                                       AS wr_return_date_sk,
    t_time_sk                                       AS wr_return_time_sk,
    i_item_sk                                       AS wr_item_sk,
    c1.c_customer_sk                                AS wr_refunded_customer_sk,
    c1.c_current_cdemo_sk                           AS wr_refunded_cdemo_sk,
    c1.c_current_hdemo_sk                           AS wr_refunded_hdemo_sk,
    c1.c_current_addr_sk                            AS wr_refunded_addr_sk,
    c2.c_customer_sk                                AS wr_returning_customer_sk,
    c2.c_current_cdemo_sk                           AS wr_returning_cdemo_sk,
    c2.c_current_hdemo_sk                           AS wr_returning_hdemo_sk,
    c2.c_current_addr_sk                            AS wr_returning_addr_sk,
    wp_web_page_sk                                  AS wr_web_page_sk,
    r_reason_sk                                     AS wr_reason_sk,
    wret_order_id                                   AS wr_order_number,
    wret_return_qty                                 AS wr_return_quantity,
    wret_return_amt                                 AS wr_return_amt,
    wret_return_tax                                 AS wr_return_tax,
    wret_return_amt + wret_return_tax               AS wr_return_amt_inc_tax,
    wret_return_fee                                 AS wr_fee,
    wret_return_ship_cost                           AS wr_return_ship_cost,
    wret_refunded_cash                              AS wr_refunded_cash,
    wret_reversed_charge                            AS wr_reversed_charge,
    wret_account_credit                             AS wr_account_credit,
    wret_return_amt + wret_return_tax + wret_return_fee 
      - wret_refunded_cash - wret_reversed_charge - wret_account_credit AS wr_net_loss
FROM s_web_returns 
LEFT OUTER JOIN date_dim      ON (CAST(wret_return_date AS date) = d_date) 
LEFT OUTER JOIN time_dim      ON (
    (CAST(SUBSTR(wret_return_time, 1, 2) AS integer) * 3600 
   + CAST(SUBSTR(wret_return_time, 4, 2) AS integer) * 60 
   + CAST(SUBSTR(wret_return_time, 7, 2) AS integer)) = t_time
) 
LEFT OUTER JOIN item          ON (wret_item_id = i_item_id) 
LEFT OUTER JOIN customer c1   ON (wret_return_customer_id = c1.c_customer_id) 
LEFT OUTER JOIN customer c2   ON (wret_refund_customer_id = c2.c_customer_id) 
LEFT OUTER JOIN reason        ON (wret_reason_id = r_reason_id) 
LEFT OUTER JOIN web_page      ON (wret_web_page_id = wp_web_page_id) 
WHERE i_rec_end_date IS NULL 
  AND wp_rec_end_date IS NULL;


INSERT INTO web_returns (
    wr_returned_date_sk,
    wr_returned_time_sk,
    wr_item_sk,
    wr_refunded_customer_sk,
    wr_refunded_cdemo_sk,
    wr_refunded_hdemo_sk,
    wr_refunded_addr_sk,
    wr_returning_customer_sk,
    wr_returning_cdemo_sk,
    wr_returning_hdemo_sk,
    wr_returning_addr_sk,
    wr_web_page_sk,
    wr_reason_sk,
    wr_order_number,
    wr_return_quantity,
    wr_return_amt,
    wr_return_tax,
    wr_return_amt_inc_tax,
    wr_fee,
    wr_return_ship_cost,
    wr_refunded_cash,
    wr_reversed_charge,
    wr_account_credit,
    wr_net_loss
)
SELECT 
    wr_return_date_sk,
    wr_return_time_sk,
    wr_item_sk,
    wr_refunded_customer_sk,
    wr_refunded_cdemo_sk,
    wr_refunded_hdemo_sk,
    wr_refunded_addr_sk,
    wr_returning_customer_sk,
    wr_returning_cdemo_sk,
    wr_returning_hdemo_sk,
    wr_returning_addr_sk,
    wr_web_page_sk,
    wr_reason_sk,
    wr_order_number,
    wr_return_quantity,
    wr_return_amt,
    wr_return_tax,
    wr_return_amt_inc_tax,
    wr_fee,
    wr_return_ship_cost,
    wr_refunded_cash,
    wr_reversed_charge,
    wr_account_credit,
    wr_net_loss
FROM wrv;

CREATE TEMP VIEW wsv AS 
SELECT  
    d1.d_date_sk                                                              AS ws_sold_date_sk,  
    t_time_sk                                                                 AS ws_sold_time_sk,  
    d2.d_date_sk                                                              AS ws_ship_date_sk, 
    i_item_sk                                                                 AS ws_item_sk,  
    c1.c_customer_sk                                                          AS ws_bill_customer_sk,  
    c1.c_current_cdemo_sk                                                     AS ws_bill_cdemo_sk,  
    c1.c_current_hdemo_sk                                                     AS ws_bill_hdemo_sk, 
    c1.c_current_addr_sk                                                      AS ws_bill_addr_sk, 
    c2.c_customer_sk                                                          AS ws_ship_customer_sk, 
    c2.c_current_cdemo_sk                                                     AS ws_ship_cdemo_sk, 
    c2.c_current_hdemo_sk                                                     AS ws_ship_hdemo_sk, 
    c2.c_current_addr_sk                                                      AS ws_ship_addr_sk, 
    wp_web_page_sk                                                            AS ws_web_page_sk, 
    web_site_sk                                                               AS ws_web_site_sk, 
    sm_ship_mode_sk                                                           AS ws_ship_mode_sk, 
    w_warehouse_sk                                                            AS ws_warehouse_sk, 
    p_promo_sk                                                                AS ws_promo_sk, 
    word_order_id                                                             AS ws_order_number,  
    wlin_quantity                                                             AS ws_quantity,  
    i_wholesale_cost                                                          AS ws_wholesale_cost,  
    i_current_price                                                           AS ws_list_price, 
    wlin_sales_price                                                          AS ws_sales_price, 
    (i_current_price - wlin_sales_price) * wlin_quantity                     AS ws_ext_discount_amt, 
    wlin_sales_price * wlin_quantity                                          AS ws_ext_sales_price, 
    i_wholesale_cost * wlin_quantity                                          AS ws_ext_wholesale_cost,  
    i_current_price * wlin_quantity                                           AS ws_ext_list_price,  
    i_current_price * web_tax_percentage                                      AS ws_ext_tax,   
    wlin_coupon_amt                                                           AS ws_coupon_amt, 
    wlin_ship_cost * wlin_quantity                                            AS ws_ext_ship_cost, 
    (wlin_sales_price * wlin_quantity) - wlin_coupon_amt                      AS ws_net_paid, 
    ((wlin_sales_price * wlin_quantity) - wlin_coupon_amt) * (1 + web_tax_percentage) AS ws_net_paid_inc_tax, 
    ((wlin_sales_price * wlin_quantity) - wlin_coupon_amt) - (wlin_quantity * i_wholesale_cost) AS ws_net_paid_inc_ship, 
    (wlin_sales_price * wlin_quantity) - wlin_coupon_amt + (wlin_ship_cost * wlin_quantity) 
        + i_current_price * web_tax_percentage                                AS ws_net_paid_inc_ship_tax, 
    ((wlin_sales_price * wlin_quantity) - wlin_coupon_amt) - (i_wholesale_cost * wlin_quantity) AS ws_net_profit 
FROM s_web_order  
LEFT OUTER JOIN date_dim d1     ON (CAST(word_order_date AS date) = d1.d_date) 
LEFT OUTER JOIN time_dim        ON (word_order_time = t_time) 
LEFT OUTER JOIN customer c1     ON (word_bill_customer_id = c1.c_customer_id) 
LEFT OUTER JOIN customer c2     ON (word_ship_customer_id = c2.c_customer_id) 
LEFT OUTER JOIN web_site        ON (word_web_site_id = web_site_id AND web_rec_end_date IS NULL) 
LEFT OUTER JOIN ship_mode       ON (word_ship_mode_id = sm_ship_mode_id) 
JOIN s_web_order_lineitem       ON (word_order_id = wlin_order_id) 
LEFT OUTER JOIN date_dim d2     ON (CAST(wlin_ship_date AS date) = d2.d_date) 
LEFT OUTER JOIN item            ON (wlin_item_id = i_item_id AND i_rec_end_date IS NULL) 
LEFT OUTER JOIN web_page        ON (wlin_web_page_id = wp_web_page_id AND wp_rec_end_date IS NULL) 
LEFT OUTER JOIN warehouse       ON (wlin_warehouse_id = w_warehouse_id) 
LEFT OUTER JOIN promotion       ON (wlin_promotion_id = p_promo_id);


INSERT INTO web_sales (
    ws_sold_date_sk,
    ws_sold_time_sk,
    ws_ship_date_sk,
    ws_item_sk,
    ws_bill_customer_sk,
    ws_bill_cdemo_sk,
    ws_bill_hdemo_sk,
    ws_bill_addr_sk,
    ws_ship_customer_sk,
    ws_ship_cdemo_sk,
    ws_ship_hdemo_sk,
    ws_ship_addr_sk,
    ws_web_page_sk,
    ws_web_site_sk,
    ws_ship_mode_sk,
    ws_warehouse_sk,
    ws_promo_sk,
    ws_order_number,
    ws_quantity,
    ws_wholesale_cost,
    ws_list_price,
    ws_sales_price,
    ws_ext_discount_amt,
    ws_ext_sales_price,
    ws_ext_wholesale_cost,
    ws_ext_list_price,
    ws_ext_tax,
    ws_coupon_amt,
    ws_ext_ship_cost,
    ws_net_paid,
    ws_net_paid_inc_tax,
    ws_net_paid_inc_ship,
    ws_net_paid_inc_ship_tax,
    ws_net_profit
)
SELECT 
    ws_sold_date_sk,
    ws_sold_time_sk,
    ws_ship_date_sk,
    ws_item_sk,
    ws_bill_customer_sk,
    ws_bill_cdemo_sk,
    ws_bill_hdemo_sk,
    ws_bill_addr_sk,
    ws_ship_customer_sk,
    ws_ship_cdemo_sk,
    ws_ship_hdemo_sk,
    ws_ship_addr_sk,
    ws_web_page_sk,
    ws_web_site_sk,
    ws_ship_mode_sk,
    ws_warehouse_sk,
    ws_promo_sk,
    ws_order_number,
    ws_quantity,
    ws_wholesale_cost,
    ws_list_price,
    ws_sales_price,
    ws_ext_discount_amt,
    ws_ext_sales_price,
    ws_ext_wholesale_cost,
    ws_ext_list_price,
    ws_ext_tax,
    ws_coupon_amt,
    ws_ext_ship_cost,
    ws_net_paid,
    ws_net_paid_inc_tax,
    ws_net_paid_inc_ship,
    ws_net_paid_inc_ship_tax,
    ws_net_profit
FROM wsv;

TRUNCATE TABLE
    s_purchase_lineitem,
    s_purchase,
    s_catalog_order,
    s_web_order,
    s_catalog_order_lineitem,
    s_web_order_lineitem,
    s_store_returns,
    s_catalog_returns,
    s_inventory,
    s_web_returns
RESTART IDENTITY
CASCADE;