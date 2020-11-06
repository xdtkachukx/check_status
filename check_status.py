import asyncio
import csv
import httplib2
import logging
import re
import requests
import sys


FILE_NAME = 'urls.csv'


class GoogleAPI:
    DRIVE_URL = 'https://docs.google.com/uc?export=download'

    def __init__(self, file_id):
        self.file_id = file_id

    @staticmethod
    def save_content(response):
        with open(FILE_NAME, 'wb') as f:
            for chunk in response.iter_content(32768):
                if chunk:
                    f.write(chunk)

    @staticmethod
    def get_token(response):
        for k, v in response.cookies.items():
            if k.startswith('download_warning'):
                return v

    def get_file(self):
        session = requests.Session()
        response = session.get(self.DRIVE_URL, params={'id': self.file_id}, stream=True)
        token = self.get_token(response)

        if token:
            params = {'id': self.file_id, 'confirm': token}
            response = session.get(self.DRIVE_URL, params=params, stream=True)

        self.save_content(response)


class CheckUrls:
    logging.basicConfig(stream=sys.stdout, level=logging.INFO)

    @staticmethod
    def get_urls_from_text(text):
        # regex for find all correct links in string and return as list
        link_regex = r'\b((?:https?://)?(?:(?:www\.)?(?:[\da-z\.-]+)\.(?:[a-z]{2,6})|(?:(?:25[0-5]|2[0-4][0-9]|[01]?[' \
                     r'0-9][0-9]?)\.){3}(?:25[0-5]|2[0-4][0-9]|[01]?[0-9][0-9]?)|(?:(?:[0-9a-fA-F]{1,4}:){7,7}[0-9a-f' \
                     r'A-F]{1,4}|(?:[0-9a-fA-F]{1,4}:){1,7}:|(?:[0-9a-fA-F]{1,4}:){1,6}:[0-9a-fA-F]{1,4}|(?:[0-9a-fA-' \
                     r'F]{1,4}:){1,5}(?::[0-9a-fA-F]{1,4}){1,2}|(?:[0-9a-fA-F]{1,4}:){1,4}(?::[0-9a-fA-F]{1,4}){1,3}|' \
                     r'(?:[0-9a-fA-F]{1,4}:){1,3}(?::[0-9a-fA-F]{1,4}){1,4}|(?:[0-9a-fA-F]{1,4}:){1,2}(?::[0-9a-fA-F]' \
                     r'{1,4}){1,5}|[0-9a-fA-F]{1,4}:(?:(?::[0-9a-fA-F]{1,4}){1,6})|:(?:(?::[0-9a-fA-F]{1,4}){1,7}|:)|' \
                     r'fe80:(?::[0-9a-fA-F]{0,4}){0,4}%[0-9a-zA-Z]{1,}|::(?:ffff(?::0{1,4}){0,1}:){0,1}(?:(?:25[0-5]|' \
                     r'(?:2[0-4]|1{0,1}[0-9]){0,1}[0-9])\.){3,3}(?:25[0-5]|(?:2[0-4]|1{0,1}[0-9]){0,1}[0-9])|(?:[0-9a' \
                     r'-fA-F]{1,4}:){1,4}:(?:(?:25[0-5]|(?:2[0-4]|1{0,1}[0-9]){0,1}[0-9])\.){3,3}(?:25[0-5]|(?:2[0-4]' \
                     r'|1{0,1}[0-9]){0,1}[0-9])))(?::[0-9]{1,4}|[1-5][0-9]{4}|6[0-4][0-9]{3}|65[0-4][0-9]{2}|655[0-2]' \
                     r'[0-9]|6553[0-5])?(?:/[\w\.-]*)*/?)\b'
        return re.findall(link_regex, text)

    def read_file(self):
        with open(FILE_NAME, 'r') as csv_file:
            reader = csv.reader(csv_file)
            urls = []
            for row in reader:
                if urls_in_row := self.get_urls_from_text(str(row)):
                    urls.extend(urls_in_row)
            return set(urls)

    @staticmethod
    async def check_url(url):
        url_ = f'http://{url}' if not url.startswith('http') else url
        try:
            http = httplib2.Http()
            response = http.request(url_, 'HEAD')
            status = response[0]['status']

            # '301' for permanently redirected on https
            if status == '301':
                url_ = f'https://{url}'
                response = http.request(url_, 'HEAD')
                status = response[0]['status']

            # statuses '2xx' for success
            status_regex = re.compile('^(2[0-9]{2})+$')
            status_matching = status_regex.match(status)
            if status_matching:
                message = f'{url} - availability OK, status: {status}'
            else:
                message = f'{url} - NOT AVAILABLE, status: {status}'
        except Exception:
            message = f'{url} - NOT AVAILABLE'
        logging.info(message)

    async def main(self, urls_list):
        tasks = (self.check_url(url) for url in urls_list)
        await asyncio.gather(*tasks)


if __name__ == '__main__':
    # https://drive.google.com/file/d/1fgkcoBBQmAvGL4lf_RTAE0lSEHruSbvC/view
    # where 1fgkcoBBQmAvGL4lf_RTAE0lSEHruSbvC is file id on Google Drive
    drive_file_id = '1fgkcoBBQmAvGL4lf_RTAE0lSEHruSbvC'

    # open file from Google Drive and save locally as 'urls.csv'
    api = GoogleAPI(drive_file_id)
    api.get_file()

    # check urls.csv for urls
    checker = CheckUrls()
    urls_to_check = checker.read_file()

    # check sites availability and log results
    event_loop = asyncio.get_event_loop()
    try:
        event_loop.run_until_complete(checker.main(urls_to_check))
    finally:
        event_loop.close()
