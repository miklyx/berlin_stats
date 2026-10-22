import logging
import time

import requests
from bs4 import BeautifulSoup


logger = logging.getLogger(__name__)

HEADERS = {
    "User-Agent": "Mozilla/5.0 (X11; Linux aarch64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Safari/537.36",
    "Accept-Language": "de,en;q=0.8",
}
_session = requests.Session()
_session.headers.update(HEADERS)


def get_html(url, retries=3, timeout=20):
    for attempt in range(1, retries + 1):
        try:
            response = _session.get(url, timeout=timeout)
            response.raise_for_status()
            return response.text
        except requests.RequestException:
            if attempt == retries:
                raise
            time.sleep(2 * attempt)


def parse_polizei_html(html, skip_urls=frozenset(), delay=0.5):
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

def parse_polizei_record_html(html):
    soup = BeautifulSoup(html, 'html.parser')
    text = ""
    for item in soup.find('div', class_='textile').find_all('p'):
        text += item.text
        
    return text

def parse_meeting_html(html):
    soup = BeautifulSoup(html, 'html.parser')
    headers = []
    for th in soup.find('thead').find_all('th'):
        headers.append(th.get('id'))
    
    rows_data = []
    
    for tr in soup.find('tbody').find_all('tr'):
        row = {}
        for i, td in enumerate(tr.find_all('td')):
            if i < len(headers):
                row[headers[i]] = td.text.strip()
        rows_data.append(row)
    
    return rows_data



if __name__ == "__main__":
    import db

    db.init_db()
    meetings = parse_meeting_html(get_html('https://www.berlin.de/polizei/service/versammlungsbehoerde/versammlungen-aufzuege'))
    print(db.insert_only_new_meeting_data(meetings))
