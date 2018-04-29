import requests
import logging

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

class GiantbombAPI:
    """
    Simple implementation of the Giantbomb API that only offers the
    GET /platforms/ call as a generator.

    """

    base_url = 'http://www.giantbomb.com/api'

    def __init__(self, api_key):
        self.api_key = api_key

    def get_platforms(self, sort=None, filter=None, field_list=None):
        """Generator yielding platforms matching the given criteria.
        If no limit is specified, thi will return all platforms.

        """

        # Do value-format conversions from common Python data types to what
        # the API requires. Need to convert a dictionary of criteria
        # into a comma-separated list of key-value paris.
        params = {}
        if sort is not None:
            params['sort'] = sort
        if field_list is not None:
            params['field_list'] = ','.join(field_list)
        if filter is not None:
            params['filter'] = filter
            parsed_filters = []
            for key, value in filter.items():
                parsed_filters.append('{0}:{1}'.format(key, value))
            params['filter'] = ','.join(parsed_filters)

        # Append API key to the list of parameters and have data being
        # returned as JSON.
        params['api_key'] = self.api_key
        params['format'] = 'json'

        incomplete_result = True
        num_total_results = None
        num_fetched_results = 0
        counter = 0

        while incomplete_result:
            # Need to make multiple calls given Giantbomb's limit for items
            # in a result set for this API is 100 items.
            params['offset'] = num_fetched_results
            result = requests.get(self.base_url + '/platforms/', params=params)
            result = result.json()
            if num_total_results is None:
                num_total_results = int(result['number_of_total_results'])
            num_fetched_results += int(result['number_of_page_results'])
            if num_fetched_results >= num_total_results:
                incomplete_result = False
            for item in result['results']:
                logging.debug("Yielding platform {0} of {1}".format(
                    counter + 1,
                    num_total_results))

                # Convert values into a more useful format where appropriate.
                if 'original_price' in item and item['original_price']:
                    item['original_price'] = float(item['original_price'])

                # Make this a generator
                yield item
                counter += 1

def is_valid_datset(platform):
    """Filters out datasets that can't be used because they are either
    lacking a release date or an original price. For rendering the output
    we also require the name and the abbreviation of the platform.

    """
    if 'release_date' not in platform or not platform['release_date']:
        logging.warn("{0} has no release date".format(platform['name']))
        return False
    if 'original_price' not in platform or not platform['original_price']:
        logging.warn("{0} has no original price".format(platform['name']))
        return False
    if 'name' not in platform or not platform['name']:
        logging.warn("No platform name found for given dataset")
        return False
    if 'abbreviation' not in platform or not platform['abbreviation']:
        logging.warn("{0} has no abbreviation".format(platform['name']))
        return False
    return True

def main():
    """This functiom handles the actual logic of this script."""

    # Grab CPI data

    # Grab platform API data

    # Figure out current price of each platform
    # Requires looping through each game platform and adjust the price based on CPI data
    # Validate data so we do not skew results

    # Generate graph for adjusted price data

    # Generate CSV file to save adjusted price data

