# Import libraries
import warnings
warnings.filterwarnings("ignore")
import os
import mechanize
import http.cookiejar
import logging
import json
import calendar
import itertools
import pandas as pd
import http.client as http_client
import zipfile
import configparser
import ast
import sqlite3
import gzip
import csv
from datetime import datetime
from db_operations import table_data, is_header, get_column_names, add_iso_timestamp, create_index, add_weather_data

class PEMSConnector:
    def __init__(self, config_file, debug=False):
        """
        Initialize the PEMSConnector with configuration details and set up the connection to PeMS.
        
        Args:
            config_file (str): Path to the configuration file.
            debug (bool): Enable debug logging if True.
        """
        
        # Initialize with configuration file path
        self.config_file = config_file
        self.config = configparser.ConfigParser()
        self.config.read(config_file)

        # PeMS Credential Details
        self.username = self.config['Credentials']['user']
        self.password = self.config['Credentials']['password']

        # Paths for various files
        self.data_path = self.config['Paths']['data_path']

        # About data
        self.start_date = str(self.config['BasicDetails']['start_date'])
        self.end_date = str(self.config['BasicDetails']['end_date'])
        self.file_details = ast.literal_eval(self.config['BasicDetails']['file_details'])
        
        # About DB
        # self.db = self.config['BasicDetails']['db']
        self.db = self.config['Paths']['db_path']
        self.cursor = self._connect_to_db()

        self.debug = debug
        self.log = logging.getLogger(__name__)
        # Login to website 
        self.browser = self._setup_pems_connection() 
 

    def _setup_pems_connection(self, retries=3):

        """
        Set up the connection to the PeMS website and handle login.

        This method configures a mechanize browser object to interact with the PeMS website, including handling login and setting up necessary browser options.

        Args:
            retries (int): Number of retries for login in case of failure. Default is 3.

        Returns:
            mechanize.Browser: Configured mechanize browser object if login is successful; otherwise, returns 0.
        """

        # Base URL of the PeMS website
        base_url = 'http://pems.dot.ca.gov'
        login_url = f"{base_url}/?dnode=Clearinghouse" # URL for the login page

        # Create a Browser object from mechanize
        br = mechanize.Browser()

        # Set up a CookieJar to handle cookies
        cj = http.cookiejar.CookieJar()
        br.set_cookiejar(cj)

        # Enable HTTP debugging if the debug flag is set
        if self.debug:
            http_client.HTTPConnection.debuglevel = 1

        # Configure browser options to handle various aspects of HTTP requests
        br.set_handle_equiv(True)        # Handle `Content-Type` and `Content-Encoding` headers
        br.set_handle_redirect(True)     # Follow HTTP redirects
        br.set_handle_referer(True)      # Send the referer header with requests
        br.set_handle_robots(False)      # Ignore robots.txt

        # Set the user agent to simulate a real browser
        br.addheaders = [('User-agent', 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/114.0.0.0 Safari/537.36')]
        
        self.log.info('Connecting to PeMS...')
        try:
            
            br.open(login_url)
            self.log.info('Opened connection to PeMS.')
            non_login_response = br.response().read()  # Read the response content before login

            # Select the first form on the page for login
            br.select_form(nr=0)  
            br.form['username'] = self.username # Fill in the username
            br.form['password'] = self.password # Fill in the password

            for retry in range(0, retries):
                try:
                    # Submit the form and attempt to log in
                    response = br.submit()
                except:
                    # Check if login was successful
                    response = br.open(login_url)
                    if br.response().read()!=non_login_response and response.code == 200:  
                        self.log.info('Successfully logged in.')
                        return br # Return the configured browser object
                    else:
                        print ('Try Number:', retry) 
                        continue # Retry on exception

        except mechanize.URLError as e:
            # Log the error and raise an exception if connection or login fails
            self.log.error(f'Login failed: {e}')
            raise
        return 0
    
    @staticmethod
    def get_date_range(start_date_str, end_date_str):
        """
        Computes the range of months and years between two dates.

        Parameters:
        - start_date_str (str): Start date in 'YYYY-MM-DD' format.
        - end_date_str (str): End date in 'YYYY-MM-DD' format.

        Returns:
        - dict: Dictionary where keys are years and values are lists of months in that year.
        """


        # Define month names for later use in constructing the date range
        month_names = list(calendar.month_name)[1:] # Exclude the empty string at index 0
        
        # Parse the input date strings into datetime objects
        start_date = datetime.strptime(start_date_str, '%Y-%m-%d')
        end_date = datetime.strptime(end_date_str, '%Y-%m-%d')
        
        # Initialize an empty dictionary to hold the date range results
        date_range = {}
        
        # Extract the starting year and month from the start date
        current_year = start_year = start_date.year
        start_month = start_date.strftime('%B') # Get the full month name (e.g., 'January')

        # Extract the ending year and month from the end date
        end_year = end_date.year
        end_month = end_date.strftime('%B') # Get the full month name (e.g., 'January')

        # Loop through each year from the start year to the end year
        while current_year <= end_year:

            # Determine which months to include for the current year
            if current_year == end_year and current_year == start_year: # Case where start and end year are the same
                date_range[current_year] = month_names[month_names.index(start_month):month_names.index(end_month)+1]
            elif current_year == start_year and current_year < end_year: # Case where the current year is the start year but not the end year
                date_range[current_year] = month_names[month_names.index(start_month):]
            else: # Case for all other years in the range
                date_range[current_year] = month_names[:month_names.index(end_month)+1]
            
            # Move to the next year
            current_year += 1

        return date_range
    
    def _download_files(self):

        """
        Downloads data files from the PeMS website based on the specified date range and file details.

        This method constructs URLs for the data files based on the specified date range and file details, 
        retrieves the data from the PeMS website, processes it, and saves it locally.

        Returns:
            int: Returns 0 upon successful execution.
        """

        # Compute the date range for the given start and end dates
        date_range = self.get_date_range(self.start_date, self.end_date)
        print (date_range)

        # DataFrame to hold all downloadable data
        downloadable_data = pd.DataFrame()
        
        # Iterate over each year and file detail configuration
        for year, (districts, file_type) in itertools.product(sorted(date_range.keys()), self.file_details):
            for district in districts:
                # Construct the URL for the data file
                file_url = "http://pems.dot.ca.gov/?srq=clearinghouse&district_id={}&yy={}&type={}&returnformat=text".format(district, str(year), file_type)
                print (file_url) # Print the URL for debugging purposes
                
                # Open the URL and read the response
                self.browser.open(file_url)
                target_data = json.loads(self.browser.response().read()) # Parse the JSON response
                if 'data' in target_data:
                    target_data =target_data['data']

                    # Process each month of data for the given year
                    for month in date_range[year]:
                        if month in target_data:
                            temp_data = pd.DataFrame(target_data[month])
                            downloadable_data = pd.concat([downloadable_data, temp_data])
                else:
                    print ('Data Not Available') # Indicate if no data is available for the URL
                
                # Special handling for meta files to include previous year's data if needed
                if file_type == 'meta':
                    old_meta_added = False
                    start_year = datetime.strptime(self.start_date, '%Y-%m-%d').year
                    
                    while old_meta_added==False:
                        start_year = start_year-1
                        file_url = "http://pems.dot.ca.gov/?srq=clearinghouse&district_id={}&yy={}&type={}&returnformat=text".format(district, str(start_year), file_type)
                        self.browser.open(file_url)
                        target_data = json.loads(self.browser.response().read())
                        
                        if 'data' in target_data:
                            target_data =target_data['data']
                            month_names = list(calendar.month_name)[1:]
                            # Determine the most recent month available in the data
                            get_month = month_names[max([month_names.index(month) for month in list(target_data.keys())])]
                            temp_data = pd.DataFrame(target_data[get_month])
                            downloadable_data = pd.concat([downloadable_data, temp_data])
                            old_meta_added = True
                
        # Save downloaded data to local files
        if len(downloadable_data)>0:
            file_types = [item[1] for item in self.file_details]
            
            for file_type in file_types:
                # Filter data for the current file type
                downloadable_data_dummy = downloadable_data.loc[downloadable_data['file_name'].str.contains(file_type)]

                # Create a directory to save the files
                save_path = os.path.join(self.data_path, file_type)
                os.makedirs(save_path, exist_ok=True)
            
                for _, file in downloadable_data_dummy.iterrows():
                    file_name = file['file_name']
                    base_url = 'http://pems.dot.ca.gov'
                    file_url = base_url+file['url']
                    download_path = os.path.join(save_path, file_name)
                
                    
                    try:
                        self.log.info('Start download, {}'.format(file_name))

                        self.browser.retrieve(file_url, download_path)
                        self.log.info('Download completed, {}'.format(file_name))
                        print ('Download completed, {}'.format(file_name))

                    except Exception:
                        self.log.info('Error downloading {}}'.format(file_name))

        return 0 

    def _connect_to_db(self):
        """
        Connects to the SQLite database specified in the configuration file.

        Returns:
        - sqlite3.Cursor: Database cursor object.
        """
        # Ensure the directory exists
        os.makedirs(os.path.dirname(self.db), exist_ok=True)
        # If the database does not exist, it will be created
        self.conn = sqlite3.connect(self.db)
        cursor = self.conn.cursor()
        return cursor
    
    def _create_table(self):
        """
        Creates database tables as defined in the `table_data` function from `ddl` module.
        """
        for table in table_data():
            self.cursor.execute(table[0]) # drop table if exists
            self.cursor.execute(table[1]) # create table
            self.conn.commit()
            print ('Table Created Successfully')

    def _insert_data(self):

        """
        Inserts data from downloaded files into the SQLite database.

        This method processes files in the specified data directory, handles different file formats (.zip, .gz, .txt), and inserts the data into the appropriate tables in the database.

        The following steps are performed:
        1. Iterates through each file type as specified in the configuration.
        2. For each file, determines its format and processes it accordingly.
        3. Handles zipped files by extracting them and then processing the extracted files.
        4. Handles gzip-compressed files and normal text files, assuming they contain CSV data.
        5. Constructs and executes SQL INSERT statements to insert the data into the database.

        """
        # Get the list of file types from configuration
        file_types = [item[1] for item in self.file_details]
        for file_type in file_types:
            # List and sort files of the current type in the data directory
            file_list = os.listdir(os.path.join(self.data_path, file_type))
            file_list.sort()

            # Get column names for the current file type
            column_list = get_column_names(self.conn, file_type)
            
            for file in file_list:
                # Open the file and create a list of data rows
                data_to_insert = []
                file_path = self.data_path+'/'+file_type+'/'+file

                # Check if the file is a ZIP archive
                if '.zip' in file:
                    extraction_dir = os.path.join(self.data_path, 'extracted_files')

                    # Create the extraction directory if it doesn't exist
                    os.makedirs(extraction_dir, exist_ok=True)

                    # Unzip the file
                    with zipfile.ZipFile(file_path, 'r') as f:
                        f.extractall(extraction_dir)

                    # List the extracted files and select the one matching the file_type
                    extracted_files = os.listdir(extraction_dir)
                    file = [file for file in extracted_files if file_type in file][0]
                    file_path = extraction_dir+'/'+file
                    print("Extracted file:", file)

                # Check if the file is GZIP compressed
                if '.gz' in file: 
                    with gzip.open(file_path, 'rt') as f:
                        # Assume the file contains CSV data
                        csv_reader = csv.DictReader(f)
                        csv_reader = csv.reader(f)
                        try:
                            count = 0
                            for row in csv_reader:
                                count = count+1
                                # Skip header row
                                if is_header(row) and count==1:
                                    continue
                                # Append data row to list
                                data_to_insert.append(row[:len(column_list[1:])])
                                
                        except:
                            print ('Unable to expand',f,'into data')

                # Check if the file is a text file
                elif '.txt' in file:
                    with open(file_path, 'rt') as f:
                        csv_reader = csv.reader(f, delimiter='\t')
                        try:
                            count = 0
                            for row in csv_reader:
                                count = count+1
                                # Skip header row
                                if is_header(row) and count==1:
                                    continue
                                # Append data row to list
                                data_to_insert.append(row[:len(column_list[1:])])
                                
                        except:
                            print ('Unable to expand',f,'into data')
                
                else:
                    # Skip unsupported file types
                    continue

                # Create the SQL INSERT statement with placeholders for the data
                insert_query = "INSERT INTO "+file_type+" ("+ ','.join(column_list[1:])+") VALUES ("+','.join(['?']*len(column_list[1:]))+")"
                print (len(data_to_insert))

                # Execute the INSERT statement for all data rows
                self.conn.executemany(insert_query, data_to_insert)

                # Commit the transaction to save changes to the database
                self.conn.commit()
                print("Data inserted successfully!", file)
            
    def close_conn(self):
        """
        Closes the connection to the SQLite database.
        """
        self.conn.close()
        return 0

if __name__ == "__main__":
    """
    Entry point of the script.

    Initializes the PEMSConnector with the configuration file, performs data download, table creation, data insertion, and adds weather data. 
    Finally, closes the database connection.

    The following steps are performed:
    1. Create an instance of PEMSConnector with the configuration file.
    2. Perform data download and table creation.
    3. Insert data into the database.
    4. Add weather data to the database.
    5. Close the database connection.
    """

    # Initialize the PEMSConnector with the configuration file
    pems = PEMSConnector("config.ini")

    # perform data download and table creation
    pems._download_files()
    pems._create_table()

    # Insert data from downloaded files into the database
    pems._insert_data()

    # Create ISO timestamp column and create index on this column
    add_iso_timestamp(pems.cursor,'station_5min','timestamp')
    create_index(pems.cursor,'station_5min','iso_timestamp')

    # Add weather data to the database (function from ddl module)
    add_weather_data("config.ini", pems.conn)

    # Close the database connection
    pems.close_conn()
