import logging
import time
from collections.abc import Collection

import requests
from bs4 import BeautifulSoup

logger = logging.getLogger(__name__)

HEADERS = {
    "User-Agent": "Mozilla/5.0 (X11; Linux aarch64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Safari/537.36",
    "Accept-Language": "de,en;q=0.8",
}
_session = requests.Session()
_session.headers.update(HEADERS)


def get_html(url: str, retries: int = 3, timeout: float = 20) -> str:
    for attempt in range(1, retries + 1):
        try:
            response = _session.get(url, timeout=timeout)
            response.raise_for_status()
            return response.text
        except requests.RequestException:
            if attempt == retries:
                raise
            time.sleep(2 * attempt)


def parse_polizei_html(html: str, skip_urls: Collection[str] = frozenset(), delay: float = 0.5) -> list[dict]:
    soup = BeautifulSoup(html, 'html.parser')
    data = []
    for item in soup.find('ul', class_='list--tablelist').find_all('li'):
        url = 'https://www.berlin.de' + item.find('a')['href']
        if url in skip_urls:
            continue
        time_text = item.find('div', class_='cell nowrap date').text
        title = item.find('div', class_='cell text').text
        district = item.find('span', class_='category').text.split('Ereignisort: ')[1].strip()
        try:
            time.sleep(delay)
            details = parse_polizei_record_html(get_html(url))
        except Exception:
            # not saved, so it is picked up again on the next poll
            logger.warning("Skipping %s: failed to fetch details", url, exc_info=True)
            continue
        data.append({'title': title, 'time': time_text, 'district': district, 'url': url, 'details': details})
    return data

def parse_polizei_record_html(html: str) -> str:
    soup = BeautifulSoup(html, 'html.parser')
    return "".join(p.text for p in soup.find('div', class_='textile').find_all('p'))

def parse_meeting_html(html: str) -> list[dict]:
    soup = BeautifulSoup(html, 'html.parser')
    headers = [th.get('id') for th in soup.find('thead').find_all('th')]

    rows_data = []
    for tr in soup.find('tbody').find_all('tr'):
        cells = [td.text.strip() for td in tr.find_all('td')]
        rows_data.append(dict(zip(headers, cells, strict=False)))
    return rows_data
