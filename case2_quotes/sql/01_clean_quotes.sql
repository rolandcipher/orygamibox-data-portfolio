-- Case 2 - Quote funnel | Step 1: clean the raw quotes table
-- Source tables (BigQuery dataset `orygamibox`):
--   raw_quotes : data/raw/quotes.csv loaded with every column as STRING (so the dirt is preserved)
--   clients    : data/clean/clients.csv
--   orders     : data/clean/orders.csv
-- Output: view `orygamibox.clean_quotes` (one row per real quote)

CREATE OR REPLACE VIEW orygamibox.clean_quotes AS
WITH parsed AS (
  -- 1) Parse dates written in two formats, standardise labels, cast numbers
  SELECT
    quote_id,
    client_id AS raw_client_id,
    COALESCE(SAFE.PARSE_DATE('%Y-%m-%d', request_date),
             SAFE.PARSE_DATE('%d/%m/%Y', request_date))  AS request_date,
    COALESCE(SAFE.PARSE_DATE('%Y-%m-%d', response_date),
             SAFE.PARSE_DATE('%d/%m/%Y', response_date)) AS response_date,
    CASE LOWER(TRIM(board_type))
      WHEN 'sbs' THEN 'SBS' WHEN 'coated' THEN 'Coated'
      WHEN 'kraft' THEN 'Kraft' WHEN 'microflute' THEN 'Microflute' END AS board_type,
    CASE LOWER(TRIM(print_type))
      WHEN 'offset' THEN 'Offset' WHEN 'digital' THEN 'Digital' END AS print_type,
    CASE LOWER(TRIM(finish))
      WHEN 'no finish' THEN 'No finish'
      WHEN 'matte lamination' THEN 'Matte lamination'
      WHEN 'matte lam.' THEN 'Matte lamination'
      WHEN 'emboss' THEN 'Emboss' WHEN 'foil' THEN 'Foil' END AS finish,
    CAST(gsm AS INT64)                  AS gsm,
    CAST(length_mm AS FLOAT64)          AS length_mm,
    CAST(width_mm AS FLOAT64)           AS width_mm,
    CAST(height_mm AS FLOAT64)          AS height_mm,
    CAST(quantity AS INT64)             AS quantity,
    SAFE_CAST(cost_estimate AS FLOAT64) AS cost_estimate,
    CAST(quoted_price AS FLOAT64)       AS quoted_price,
    status,
    loss_reason,
    seller
  FROM orygamibox.raw_quotes
),
units_fixed AS (
  -- 2) Real box lengths are 60-400 mm, so a length below 50 was typed in cm: multiply the 3 dimensions by 10
  SELECT
    quote_id, raw_client_id, request_date, response_date, board_type, print_type, finish, gsm,
    IF(length_mm < 50, ROUND(length_mm * 10), length_mm) AS length_mm,
    IF(length_mm < 50, ROUND(width_mm * 10),  width_mm)  AS width_mm,
    IF(length_mm < 50, ROUND(height_mm * 10), height_mm) AS height_mm,
    quantity, cost_estimate, quoted_price, status, loss_reason, seller
  FROM parsed
),
ranked AS (
  -- 3) The same quote was sometimes loaded twice under a different quote_id.
  --    Same business content = same quote: keep the lowest quote_id.
  SELECT
    *,
    ROW_NUMBER() OVER (
      PARTITION BY raw_client_id, request_date, board_type, gsm, print_type, finish,
                   length_mm, width_mm, height_mm, quantity, quoted_price
      ORDER BY quote_id
    ) AS rn
  FROM units_fixed
),
unique_quotes AS (
  SELECT * FROM ranked WHERE rn = 1
),
with_client AS (
  -- 4) Some client_ids do not exist. If the quote became an order, take the client from the order;
  --    otherwise mark it UNKNOWN (kept in the data, excluded from client analysis).
  SELECT
    u.quote_id, u.request_date, u.response_date, u.board_type, u.print_type, u.finish, u.gsm,
    u.length_mm, u.width_mm, u.height_mm, u.quantity, u.cost_estimate, u.quoted_price,
    u.status, u.loss_reason, u.seller,
    CASE
      WHEN c.client_id IS NOT NULL THEN u.raw_client_id
      WHEN o.client_id IS NOT NULL THEN o.client_id
      ELSE 'UNKNOWN'
    END AS client_id
  FROM unique_quotes u
  LEFT JOIN orygamibox.clients c ON c.client_id = u.raw_client_id
  LEFT JOIN orygamibox.orders  o ON o.quote_id  = u.quote_id
)
SELECT
  w.quote_id, w.client_id, cl.sector, cl.client_size,
  w.request_date, w.response_date,
  DATE_DIFF(w.response_date, w.request_date, DAY) AS response_days,
  w.board_type, w.print_type, w.finish, w.gsm,
  w.length_mm, w.width_mm, w.height_mm, w.quantity,
  w.cost_estimate, w.quoted_price,
  ROUND(w.quoted_price / w.cost_estimate, 4)      AS markup,
  w.status,
  CASE WHEN w.status = 'Lost' THEN COALESCE(w.loss_reason, 'Not recorded') ELSE w.loss_reason END AS loss_reason,
  w.seller
FROM with_client w
LEFT JOIN orygamibox.clients cl ON cl.client_id = w.client_id;
