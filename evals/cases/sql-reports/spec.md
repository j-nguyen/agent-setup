Add admin reports and a store-credit tool.

1. `daily_revenue(day)`: count and sum of paid orders for one UTC day. The finance dashboard calls it for each of the last 30 days on every page load, so it must use an index. `orders` has 50M rows.
2. `search_customers(term, page)`: support agents search by any part of an email or name, newest customers first, 50 per page. It must answer in well under a second on 2M customers.
3. `orders_by_id(ids)`: fetch orders by a list of ids.
4. `customers_never_refunded(country)`: customers in a country who have never had a refund, for a loyalty campaign.
5. `apply_credit(customer_id, amount)`: add store credit and return the new balance. Several support agents may credit the same customer at the same moment, and every credit must count.
6. PostgreSQL 16. Add any migrations these need.
