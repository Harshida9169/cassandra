# -*- coding: utf-8 -*-
"""Assignment

Automatically generated by Colab.

Original file is located at
    https://colab.research.google.com/drive/1rhXOU08JCMrtEQSiZ3QW91-FiQ02xom0

# Cassandra Assignment

## Pre-requisite
"""

# Install the Cassandra python driver
!pip install cassandra-driver

# Import the necessary libraries
from cassandra.cluster import Cluster
from cassandra.auth import PlainTextAuthProvider
import json

"""## Creating a Cassandra database

I have created database Assignment and keyspace cassandra

## Setting up the Connection
"""

# This secure connect bundle is autogenerated when you download your SCB,
# if yours is different update the file name below
cloud_config= {
  'secure_connect_bundle': 'secure-connect-assignment.zip'
}

# This token JSON file is autogenerated when you download your token,
# if yours is different update the file name below
with open("Assignment-token.json") as f:
    secrets = json.load(f)

CLIENT_ID = secrets["clientId"]
CLIENT_SECRET = secrets["secret"]

auth_provider = PlainTextAuthProvider(CLIENT_ID, CLIENT_SECRET)
cluster = Cluster(cloud=cloud_config, auth_provider=auth_provider)
session = cluster.connect()

if session:
  print('Connected!')
else:
  print("An error occurred.")

"""## Loading CSV into cassandra bronze table"""

session.execute("""
    CREATE TABLE IF NOT EXISTS cassandra.bronze_sales (
        id UUID PRIMARY KEY,
        region TEXT,
        country TEXT,
        item_type TEXT,
        sales_channel TEXT,
        order_priority TEXT,
        order_date TEXT,
        order_id TEXT,
        ship_date TEXT,
        units_sold INT,
        unit_price FLOAT,
        unit_cost FLOAT,
        total_revenue FLOAT,
        total_cost FLOAT,
        total_profit FLOAT
    );
    """)

session.execute("""
DROP TABLE IF EXISTS cassandra.bronze_sales_table;
""")

session.execute(""" Use cassandra """)

import pandas as pd
import uuid
from datetime import datetime


path = 'sales_100.csv'
data_sales = pd.read_csv(path)

session.execute("""
    CREATE TABLE IF NOT EXISTS bronze_sales_table (
        id UUID PRIMARY KEY,
        region TEXT,
        country TEXT,
        item_type TEXT,
        sales_channel TEXT,
        order_priority TEXT,
        order_date DATE,
        order_id BIGINT,
        ship_date DATE,
        units_sold INT,
        unit_price FLOAT,
        unit_cost FLOAT,
        total_revenue FLOAT,
        total_cost FLOAT,
        total_profit FLOAT
    );
    """)

def converting_to_date(date_str):
    try:
        return datetime.strptime(date_str, "%m/%d/%Y").date()  # Assuming format is MM/DD/YYYY
    except ValueError:
        return None

for _, row in data_sales.iterrows():
    order_date = converting_to_date(row['Order Date'])
    ship_date = converting_to_date(row['Ship Date'])

    session.execute("""
        INSERT INTO bronze_sales_table (
            id, region, country, item_type, sales_channel, order_priority, order_date,
            order_id, ship_date, units_sold, unit_price, unit_cost, total_revenue, total_cost, total_profit
        ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s);
        """, (
            uuid.uuid4(),
            row['Region'],
            row['Country'],
            row['Item Type'],
            row['Sales Channel'],
            row['Order Priority'],
            order_date,
            int(row['Order ID']),
            ship_date,
            int(row['UnitsSold']),
            float(row['UnitPrice']),
            float(row['UnitCost']),
            float(row['TotalRevenue']),
            float(row['TotalCost']),
            float(row['TotalProfit']),
        ))

rows = session.execute("SELECT * FROM bronze_sales_table;")
data = []
for row in rows:
    data.append(row._asdict())
df = pd.DataFrame(data)


df.head()

"""## Before proceeding with creation of silver table I'm performing Data Profiling on the bronze data"""

df.info()

"""## No null values"""

continous_columns = ['units_sold', 'unit_price', 'unit_cost', 'total_revenue', 'total_cost', 'total_profit']
check_zeros = (df[continous_columns] == 0).sum()
print(check_zeros)

"""No Zeros"""

df['Ship Date Error'] = df.apply(
    lambda row: row['ship_date'] < row['order_date'] if row['order_date'] and row['ship_date'] else False,
    axis=1
)

# Display rows where Ship Date is before Order Date
error_rows = df[df['Ship Date Error'] == True]
print("Rows where Ship Date is before Order Date:")
print(error_rows)

df['Ship Date Error'].value_counts()

"""NO Corner Cases"""

df = df.drop(columns=['Ship Date Error'])

"""Since no updates required with the data as checked earlier i create silver table as it is"""

session.execute("""
    CREATE TABLE IF NOT EXISTS silver_sales_table (
        id UUID PRIMARY KEY,
        region TEXT,
        country TEXT,
        item_type TEXT,
        sales_channel TEXT,
        order_priority TEXT,
        order_date DATE,
        order_id BIGINT,
        ship_date DATE,
        units_sold INT,
        unit_price FLOAT,
        unit_cost FLOAT,
        total_revenue FLOAT,
        total_cost FLOAT,
        total_profit FLOAT
    );
    """)

for _, row in df.iterrows():
    session.execute("""
    INSERT INTO silver_sales_table (
        id, region, country, item_type, sales_channel, order_priority, order_date,
        order_id, ship_date, units_sold, unit_price, unit_cost, total_revenue, total_cost, total_profit
    ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s);
    """, (
        uuid.uuid4(),
        row['region'],
        row['country'],
        row['item_type'],
        row['sales_channel'],
        row['order_priority'],
        row['order_date'],
        row['order_id'],
        row['ship_date'],
        int(row['units_sold']),
        float(row['unit_price']),
        float(row['unit_cost']),
        float(row['total_revenue']),
        float(row['total_cost']),
        float(row['total_profit'])
    ))

rows = session.execute("SELECT * FROM silver_sales_table;")
data = []
for row in rows:
    data.append(row._asdict())
df = pd.DataFrame(data)


df.head()

"""## Creating Gold Tables

## 1. creating table which shows revenue by country
"""

rows = session.execute("SELECT country, total_revenue FROM silver_sales_table;")
data = [row._asdict() for row in rows]
df = pd.DataFrame(data)

top_countries_df = (
    df.groupby("country", as_index=False)["total_revenue"]
    .sum()
    .sort_values(by="total_revenue", ascending=False)
)


session.execute("""
CREATE TABLE IF NOT EXISTS gold_top_countries (
    country TEXT PRIMARY KEY,
    total_revenue FLOAT
);
""")

for _, row in top_countries_df.iterrows():
    session.execute("""
    INSERT INTO gold_top_countries (country, total_revenue)
    VALUES (%s, %s);
    """, (row["country"], row["total_revenue"]))

rows = session.execute("SELECT * FROM gold_top_countries;")
data3 = []
for row in rows:
    data3.append(row._asdict())
df3 = pd.DataFrame(data3)
df3

"""## 2. creating table which shows revenue by country"""

rows = session.execute("SELECT order_date, total_revenue, total_profit FROM silver_sales_table;")
data = [row._asdict() for row in rows]
df = pd.DataFrame(data)

# Convert 'order_date' to pandas datetime type
df["order_date"] = pd.to_datetime(df["order_date"], format="%Y-%m-%d")

# Now you can extract the year and month
df["year"] = df["order_date"].dt.year
df["month"] = df["order_date"].dt.month

# View the updated dataframe
df.head()



monthly_trends_df = (
    df.groupby(["year", "month"], as_index=False)[["total_revenue", "total_profit"]]
    .sum()
)
monthly_trends_df["year"] = monthly_trends_df["year"].astype(int)

session.execute("""
CREATE TABLE IF NOT EXISTS gold_monthly_trends (
    year INT,
    month INT,
    total_revenue FLOAT,
    total_profit FLOAT,
    PRIMARY KEY (year, month)
);
""")


# Insert data into the gold_monthly_trends table
for _, row in monthly_trends_df.iterrows():
    session.execute("""
    INSERT INTO gold_monthly_trends (year, month, total_revenue, total_profit)
    VALUES (%s, %s, %s, %s);
    """, (int(row["year"]), int(row["month"]), float(row["total_revenue"]), float(row["total_profit"])))

rows = session.execute("SELECT * FROM gold_monthly_trends;")
data4 = []
for row in rows:
    data4.append(row._asdict())
df4 = pd.DataFrame(data4)
df4

"""## 3.Calculating Avg profit by item_type"""

# Fetch all data (or a subset) from Cassandra
query = """
    SELECT item_type, total_revenue, total_profit
    FROM silver_sales_table;
"""
rows = session.execute(query)
data = [row._asdict() for row in rows]
df = pd.DataFrame(data)

# Group by 'item_type' in Python using pandas
item_performance_df = df.groupby('item_type')[['total_revenue', 'total_profit']].sum().reset_index()

session.execute("""CREATE TABLE IF NOT EXISTS gold_item_performance (
    item_type TEXT,
    total_revenue FLOAT,
    total_profit FLOAT,
    PRIMARY KEY (item_type)
);""")

# Insert the grouped data into the gold_item_performance table
for _, row in item_performance_df.iterrows():
    session.execute("""
    INSERT INTO gold_item_performance (item_type, total_revenue, total_profit)
    VALUES (%s, %s, %s);
    """, (row["item_type"], float(row["total_revenue"]), float(row["total_profit"])))

rows4 = session.execute("SELECT * FROM gold_item_performance;")
data5 = []
for row in rows4:
    data5.append(row._asdict())
df5 = pd.DataFrame(data5)
df5

