import argparse
import logging
import os

import matplotlib.pyplot as plt
import numpy as np
import requests
import tablib

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
        reached_dataset = False
        current_year = None
        year_cpi = []
        for line in fp:
            # Skip until we reach the header line "DATE"
            if not reached_dataset:
                if line.startswith("DATE "):
                    reached_dataset = True
                continue

            # Remove new-line character at the end of each line
            # and split into list
            data = line.rstrip().split()

            # Extract year from date by splitting date string
            year = int(data[0].split("-")[0])
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
            print(result.url)
            print(result.status_code)
            result.raise_for_status()

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


def generate_plot(platforms, output_file):
    """Generates a bar chart out of the given platforms and writes
    the output into the specified file as PNG image.

    """
    # Convert the platforms in a format that can be attached to the 2 axis
    # of the bar chart.
    labels = []
    values = []
    for platform in platforms:
        name = platform['name']
        adjusted_price = platform['adjusted_price']
        price = platform['original_price']

        # Skip prices higher than 2000 USD
        if price > 2000:
            continue

        # If the platform name is too long, replace it with the abbreviation.
        if len(name) > 15:
            name = platform['abbreviation']
        labels.insert(0, "{0}\n$ {1}\n$ {2}".format(name, price,
                                                    round(adjusted_price, 2)))
        values.insert(0, adjusted_price)

    # Define the width of each bar and the size of the resulting graph.
    width = 0.3
    ind = np.arange(len(values))
    fig = plt.figure(figsize=(len(labels) * 1.8, 10))

    # Generate a subplot and put values onto it.
    ax = fig.add_subplot(1, 1, 1)
    ax.bar(ind, values, width, align='center')

    # Format the X and Y axis labels. Set the ticks on the x-axis
    # slightly further apart and give them a slight tilting effect.
    plt.ylabel('Adjusted price')
    plt.xlabel('Year / Console')
    ax.set_xticks(ind + 0.3)
    ax.set_xticklabels(labels)
    fig.autofmt_xdate()
    plt.grid(True)

    plt.savefig(output_file, dpi=72)
    plt.show(dpi=72)


def generate_csv(platforms, output_file):
    """Writes the given platforms into a CSV file.

    The output_file can either be the path to a file or a file-like object.

    """
    dataset = tablib.Dataset(headers=['Abbreviation', 'Name', 'Year', 'Price',
                                      'Adjusted price'])
    for p in platforms:
        dataset.append([p['abbreviations'], p['name'], p['year'],
                        p['original_price'], p['adjusted_price']])

    # If the output_file is a string it represents a path to a file which
    # we have to open first for writing.
    if isinstance(output_file, str):
        with open(output_file, 'w+') as fp:
            fp.write(dataset.csv)
    else:
        output_file.write(dataset.csv)


def parse_args():
    parser = argparse.ArgumentParser()
    parser.add_argument('--giantbomb-api-key', required=True,
                        help='API key provided by Giantbomb.com')
    parser.add_argument('--cpi-file', default=os.path.join(os.path.dirname(__file__),
                                                           'CPIAUCSL.txt'),
                        help='Path to file containing the CPI data')
    parser.add_argument('--cpi-data-url', default=CPI_DATA_URL,
                        help='URL which should be used as CPI data source')
    parser.add_argument('--debug', default=False, action='store_true',
                        help='Increases the output level.')
    parser.add_argument('--csv-file',
                        help='Path to the PNG file which should contain the'
                             'data output')
    parser.add_argument('--plot-file',
                        help='Path to the PNG file which should contain the'
                             'data output')
    parser.add_argument('--limit', type=int,
                        help='Number of recent platforms to be considered')
    opts = parser.parse_args()
    if not (opts.plot_file or opts.csv_file):
        parser.error("You have to specify either a --csv-file or --plot-file!")
    return opts


def main():
    """This functiom handles the actual logic of this script."""
    opts = parse_args()

    if opts.debug:
        logging.basicConfig(level=logging.DEBUG)
    else:
        logging.basicConfig(level=logging.INFO)

    # Grab CPI data
    cpi_data = CPIData()

    # Grab platform API data
    gb_api = GiantbombAPI(opts.giantbomb_api_key)

    print("Disclaimer: This script uses data provided by FRED, Federal"
          "Reserve Economic Data, from the Federal Reserve Bank of St. Louis"
          "and Giantbomb.com:\n- {0}\n- http://www.giantbomb.com/api/\n"
          .format(CPI_DATA_URL))

    if os.path.exists(opts.cpi_file):
        with open(opts.cpi_file) as fp:
            cpi_data.load_from_file(fp)
    else:
        cpi_data.load_from_url(opts.cpi_data_url, save_as_file=opts.cpi_file)

    platforms = []
    counter = 0

    # Grab the platforms and calculate their current price
    # in relation to the CPI value.
    for platform in gb_api.get_platforms(sort='release_date:desc',
                                         field_list=['release_date',
                                                     'original_price',
                                                     'abbreviation']):
        # Skip platforms that don't have a release date or price.
        if not is_valid_datset(platform):
            continue

        # Figure out current price of each platform
        year = int(platform['release_date'].split('-'[0]))
        price = platform['original_price']
        adjusted_price = cpi_data.get_adjusted_price(price, year)
        platform['year'] = year
        platform['original_price'] = price
        platform['adjusted_price'] = adjusted_price
        platforms.append(platform)

        # Check if the dataset contains all the data we need.
        if opts.limit is not None and counter + 1 >= opts.limit:
            break
        counter += 1

    # Generate graph for adjusted price data
    if opts.plotfile:
        generate_plot(platforms, opts.plotfile)
    # Generate CSV file to save adjusted price data
    if opts.csv_file:
        generate_csv(platforms, opts.csv_file)


if __name__ == '__main__':
    main()
