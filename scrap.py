from bs4 import BeautifulSoup
import requests

def get_html(url):
    response = requests.get(url)
    return response.text

def parse_polizei_html(html):
    soup = BeautifulSoup(html, 'html.parser')
    data = []
    for item in soup.find('ul', class_='list--tablelist').find_all('li'):
        time = item.find('div', class_='cell nowrap date').text
        title = item.find('div', class_='cell text').text
        district = item.find('span', class_='category').text.split('Ereignisort: ')[1].strip()
        url = 'https://www.berlin.de'+item.find('a')['href']
        details_html= get_html(url)
        details = parse_polizei_record_html(details_html)
        data.append({'title': title, 'time': time, 'district': district, 'url': url, 'details': details})
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
