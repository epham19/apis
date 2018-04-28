import requests

CPI_DATA_URL = 'http://research.stlouisfed.org/fred2/data/CPIAUCSL.txt'

class CPIData:
    """Abstraction of the CPI data provided by FRED.

    This stores internally only one value per year.

    """

    def __init__(self):
        # Each year available to the dataset will end up as a simple key-value
        # pair within this dict.
        self.year_cpi = {}

        # First and last year of the dataset needs to be remembered
        # to handle years outside the documented time span.
        self.last_year = None
        self.first_year = None

    def load_from_url(self, url, save_as_file=None):
        """Loads data from a given url.

        The downloaded file can also be saved into a location for later
        re-use with the "save_as_file" parameter specifying a filename.

        After fetching the file this implementation uses load_from_file
        internally.

        """
        # Need to keep as little data as possible in memory at all times
        # by disabling gzip-compression
        fp = requests.get(url, stream=True,
                          headers={'Accept-Encoding': None}).raw

        # If save_as_file parameter is not passed, return
        # raw data from the previous line.
        if save_as_file is None:
            return self.load_from_file(fp)

        # Else, write to the desired file.
        else:
            with open(save_as_file, 'wb+') as out:
                while True:
                    buffer = fp.read(81920)
                    if not buffer:
                        break
                    out.write(buffer)
            with open(save_as_file) as fp:
                return self.load_from_file(fp)


    def load_from_file(self, fp):
        """Loads CPI data from a given file-like object."""
        # Create temporary variables when iterating over data file.
        current_year = None
        year_cpi = []
        for line in fp:
            # Skip until we reach the header line "DATE"
            while not line.startswith("Date "):
                pass

            # Remove new-line character at the end of each line
            # and split into list
            data = line.rstrip().split()

            # Extract year from date by splitting date string
            year = int(data[0].split["-"][0])
            cpi = float(data[1])

            if self.first_year is None:
                    self.first_year = year
            self.last_year = year

            # Once a new year is reached, reset the CPI data
            # and calculate the average CPI of the current_year.

            if current_year != year:
                if current_year is not None:
                    self.year_cpi[current_year] = sum(year_cpi) / len(year_cpi)
                year_cpi = []
                current_year = year
            year_cpi.append(cpi)

        # Do calculation again for the last year in the dataset
        if current_year is not None and current_year not in self.year_cpi:
            self.year_cpi[current_year] = sum(year_cpi) / len(year_cpi)

    def get_adjusted_price(self, price, year, current_year=None):
        """Returns the adapted price from a given year compared to what current
        year has been specified i.e inflation.

        """
        # Currently there is no CPI data after 2018
        if current_year is None or current_year > 2018:
            current_year = 2018

        # if data range doesn't provide a CPI for a given year,
        # use the edge data.
        if year < self.first_year:
            year = self.first_year
        elif year > self.last_year:
            year = self.last_year

        year_cpi = self.year_cpi[year]
        current_cpi = self.year_cpi[current_year]

        return float(price) / year_cpi * current_cpi

def main():
    """This functiom handles the actual logic of this script."""

    # Grab CPI data

    # Grab platform API data

    # Figure out current price of each platform
    # Requires looping through each game platform and adjust the price based on CPI data
    # Validate data so we do not skew results

    # Generate graph for adjusted price data

    # Generate CSV file to save adjusted price data

