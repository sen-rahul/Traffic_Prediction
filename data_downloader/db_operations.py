import requests
import configparser
import pandas as pd
import sqlite3

def table_data():
    """
    Generates SQL commands to drop existing tables and create new tables.

    Returns:
        list of tuples: Each tuple contains SQL commands to drop and create a table.
    """

    # Drop table
    drop_table_station_5min = '''
    DROP TABLE IF EXISTS station_5min; 
    '''

    drop_table_meta = '''
    DROP TABLE IF EXISTS meta;
    '''

    drop_table_chp_incidents_month = '''
    DROP TABLE IF EXISTS chp_incidents_month;
    '''

    # Create tables
    create_table_station_5min = '''
    CREATE TABLE IF NOT EXISTS station_5min
    (id INTEGER PRIMARY KEY AUTOINCREMENT,
    timestamp TEXT,
    station INTEGER,
    district INTEGER,
    freeway INTEGER,
    direction_of_travel TEXT,
    lane_type TEXT,
    station_length REAL,
    samples INTEGER,
    "pct_observed" REAL,
    total_flow INTEGER,
    avg_occupancy REAL,
    avg_speed REAL,
    lane_n_samples INTEGER,
    lane_n_flow INTEGER,
    lane_n_avg_occupancy REAL,
    lane_n_avg_speed REAL,
    lane_n_observed INTEGER);
    '''

    create_table_meta = '''
    CREATE TABLE IF NOT EXISTS meta
    (id INTEGER PRIMARY KEY,
    freeway_id INTEGER,
    freeway INTEGER,
    freeway_direction TEXT,
    district TEXT,
    county TEXT,
    city TEXT,
    state_pm TEXT,
    absolute_pm TEXT,
    latitude REAL,
    longitude REAL,
    "length" REAL,
    type TEXT,
    lanes INTEGER,
    name TEXT,
    user_id1 TEXT,
    user_id2 TEXT,
    user_id3 TEXT);
    '''

    create_table_chp_incidents_month = '''
    CREATE TABLE IF NOT EXISTS chp_incidents_month
    (id INTEGER PRIMARY KEY AUTOINCREMENT,
    incident_id INTEGER,
    cc_code TEXT,
    incident_no INTEGER,
    timestamp TEXT,
    description TEXT,
    location TEXT,
    area TEXT,
    zoom_map TEXT,
    tb_xy TEXT,
    latitude REAL,
    longitude REAL,
    district INTEGER,
    county_id INTEGER,
    city_id INTEGER,
    freeway_no INTEGER,
    freeway_direction TEXT,
    state_pm TEXT,
    absolute_pm TEXT,
    severity TEXT,
    duration REAL);
    '''

     # List of SQL commands to drop and create tables
    table_list = [(drop_table_station_5min, create_table_station_5min), 
                (drop_table_meta, create_table_meta), 
                (drop_table_chp_incidents_month, create_table_chp_incidents_month)]
    
    return table_list

def is_header(row):
    """
    Checks if all elements in the row contain at least one alphabet.

    Args:
        row: A list representing a row of data.

    Returns:
        True if all elements in the row contain at least one alphabet, False otherwise.
    """
    # Check if all elements are strings and contain at least one alphabet character
    return all(isinstance(item, str) and any(char.isalpha() for char in item) for item in row)

def get_column_names(conn, table_name):
    """
    Retrieves column names from a table in an SQLite database.

    Args:
        conn: A connection object to the SQLite database.
        table_name: The name of the table from which to get column names.

    Returns:
        list: A list of column names present in the table.
    """
    cursor = conn.cursor()

    # Execute PRAGMA table_info to get details about the table's columns
    cursor.execute(f"PRAGMA table_info('{table_name}')")

    # Extract column names from the result set
    column_names = [row[1] for row in cursor.fetchall()]

    return column_names

def add_iso_timestamp(cursor, table_name, reference_timestamp):
    """
    Adds an ISO 8601 timestamp column to the specified table based on a reference timestamp column.

    Args:
        cursor: A cursor object for executing SQL commands.
        table_name: The name of the table to modify.
        reference_timestamp: The name of the existing timestamp column to base the new column on.

    Returns:
        int: Returns 0 upon successful execution.
    """

    add_timestamp_sql = """ALTER TABLE """ + table_name + """ ADD COLUMN iso_timestamp DATETIME AS 
                           (substr(""" + reference_timestamp + """, 7, 4) || '-' ||  
                            substr(""" + reference_timestamp + """, 1, 2) || '-' ||   
                            substr(""" + reference_timestamp + """, 4, 2) || ' ' ||   
                            substr(""" + reference_timestamp + """, 12, 2) || ':' || 
                            substr(""" + reference_timestamp + """, 15, 2) || ':' || 
                            substr(""" + reference_timestamp + """, 18, 2)           );"""
    
    # Execute the SQL command to add the new column
    cursor.execute(add_timestamp_sql)
    print ('iso_timestamp column added in table', table_name)

    return 0

def create_index(cursor, table_name, column_name):
    """
    Creates an index on the specified column of the given table to improve query performance.

    Args:
        cursor: A cursor object for executing SQL commands.
        table_name: The name of the table on which to create the index.
        column_name: The name of the column to index.

    Returns:
        int: Returns 0 upon successful execution.
    """

    create_index_sql = "CREATE INDEX idx_iso_timestamp ON "+table_name+"("+column_name+");"

    # Execute the SQL command to create the index
    cursor.execute(create_index_sql)
    print ('Index created on table', table_name, 'in column', column_name)

    return 0

def add_weather_data(config_file, conn):
    """
    Fetches weather data from an API and stores it in an SQLite database.

    Args:
        config_file: Path to the configuration file containing API credentials.
        conn: A connection object to the SQLite database.

    Returns:
        None
    """

    config = configparser.ConfigParser()
    config.read(config_file)

    # Read API key from configuration file
    api_key = config['Credentials']['weather_api']
    endpoint = config['Paths']['weather_path']

    # Define parameters for the API request
    # location is based on the centroid of riltered region near Tustin
    location = config['BasicDetails']['weather_location']
    start_date = config['BasicDetails']['weather_start_date']
    end_date = config['BasicDetails']['weather_end_date']  
    params = {
        'key': api_key,
        'unitGroup': 'metric',  # or 'us' for Fahrenheit and other US units
        'include': 'hours'
    }

    # Make the API request
    url = f"{endpoint}/{location}/{start_date}/{end_date}"
    response = requests.get(url, params=params)

    # Check for successful response
    if response.status_code == 200:
        weather_data = response.json()
        print('Extracted Weather Data')
    else:
        print(f"Error: {response.status_code}")
        print('Daily Limit Exceeded (1000 records per day per user)')
        return 0
    
    # Process the weather data into a DataFrame
    weather_df = pd.DataFrame()
    for day in weather_data['days']:
        temp_weather_df = pd.DataFrame(day['hours'])
        temp_weather_df['datetime'] = pd.to_datetime(day['datetime'] + ' ' + temp_weather_df['datetime'])
        weather_df = pd.concat([weather_df,temp_weather_df])

    # Ensure data types are consistent
    weather_df['preciptype'] = weather_df['preciptype'].astype(str)
    weather_df['stations'] = weather_df['stations'].astype(str)

    # Function to map pandas dtypes to SQLite types
    def map_dtype(dtype):
        if pd.api.types.is_integer_dtype(dtype):
            return 'INTEGER'
        elif pd.api.types.is_float_dtype(dtype):
            return 'REAL'
        elif pd.api.types.is_datetime64_any_dtype(dtype):
            return 'TIMESTAMP'
        else:
            return 'TEXT'

    # Create a connection to the SQLite database 
    conn = sqlite3.connect(config['Paths']['db_path'])

    # Create a cursor object
    cursor = conn.cursor()

    # Dynamically generate the SQL CREATE TABLE statement
    table_name = 'weather'
    columns = ', '.join(f'{col} {map_dtype(dtype)}' for col, dtype in zip(weather_df.columns, weather_df.dtypes))
    create_table_query = f'CREATE TABLE IF NOT EXISTS {table_name} ({columns})'

    # Create the table if it doesn't exist
    cursor.execute(create_table_query)

    # Insert the DataFrame data into the SQLite database
    weather_df.to_sql(table_name, conn, if_exists='append', index=False)

    # Commit the changes and close the connection
    conn.commit()
    print ('Added Weather Data in DB')
