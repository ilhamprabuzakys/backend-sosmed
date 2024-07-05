import re
import markdown
from urllib.parse import unquote, urlparse
from bs4 import BeautifulSoup

def get_parsed_links(url, content):
    data = None

    if 'republika' in url:
        data = get_parsed_republika_links(url, content)

    return data

def get_parsed_links(url, content):
    data = None

    if 'republika' in url:
        data = get_parsed_republika_links(url, content)

    return data

def get_parsed_republika_links(url, content):
    soup = BeautifulSoup(content, "html.parser")

    selector_articles = '.main-content__middle'

    if url == 'https://republika.co.id/hot-topic':
        selector_articles = '.main-content__middle'
    elif url == 'https://republika.co.id':
        selector_articles = '.main-content__left'

    articles_card = soup.select(f'{selector_articles} ul li a')

    articles = ['Empty']

    print('Article cards:', articles_card)

    articles_card = [a for a in articles_card if a.find('div')]

    with open("output.html", "w", encoding="utf-8") as file:
        for card in articles_card:
            file.write(str(card))
            file.write("\n")


    for card in articles_card:

        print('Card:', card)

        link = card.get('href')
        title = card.select_one('h3 span')

        if not title:
            title = card.select_one('.caption .title')

        title = title.get_text(strip=True)

        date_container = card.select_one('.caption .date').get_text(strip=True)
        date_container_parts = date_container.split('-')
        time = date_container_parts[0].strip()
        if len(date_container_parts) > 1:
            time = date_container_parts[1].strip()
        image = card.select_one('.thumbnail img').get('data-original')

        if not image:
            image = card.select_one('.thumbnail img').get('src')

        article = {
            'title': title,
            'link': link,
            'time': time.replace(" ,", ","),
            'image': image,
        }

        articles.append(article)

        # if href:
        #     parsed_url = urlparse(href)
        #     path_components = parsed_url.path.strip('/').split('/')

        #     if len(path_components) >= 3:
        #         links.append(href)

    return articles


def get_clean_payload(content, url):
    soup = BeautifulSoup(content, "html.parser")

    error_msg = 'Konten berita tidak dapat diakses! dikarenakan konten berita kosong atau gagal diambil!'

    result = {}

    result['status'] = 1
    result['title'] = soup.select_one('title').text

    selectors = 'article'
    selectors_image = '.main-content__left .komik img'

    if 'republika' in url:
        selectors = 'article, .artikel, .article-content, .article-news, .read__article'
    elif 'tempo' in url:
        selectors = '.detail-konten'
    elif 'viva' in url:
        selectors = '.main-content-detail'
    elif 'vlix' in url:
        selectors = '.detail-channel-description'
    elif 'merdeka' in url:
        selectors = '.dt-inner-body .dt-para'
    elif 'sindo' in url:
        selectors = '#detail-desc, .box-desc-article, article'
        if 'mpi' in url:
            selectors = '.pc-desc-artikel'

    # Get article content
    print(f'Mencari dom menggunakan selectors {selectors}')

    raw = soup.select_one(selectors)

    if not raw:
        print('ERR: RAW')

        result['data'] = error_msg
        result['status'] = 0

        return result

    for div in raw.find_all('div'):
        div.extract()

    data = raw.get_text(separator='\n').strip()
    data = re.sub(r'\n{3,}', '\n\n', data)

    if not data:
        print('ERR: EMPTY')

        result['data'] = error_msg
        result['status'] = 0

        return result

    result['data'] = data
    
    # Get image url
    image_el = soup.select_one(selectors_image)
    
    image = None if not image_el else image_el.get('src')
    
    result['image'] = image

    return result


def validate_redirect_urls(url):
    # MPI Sindonews
    mpi_sindonews_pattern = r'https://mpi\.sindonews\.com/article/(.*)/(\d+)'
    mpi_sindonews_match = re.search(mpi_sindonews_pattern, url)

    if mpi_sindonews_match:
        article_id = mpi_sindonews_match.group(2)
        new_url = f'https://mpi.idxchannel.com/framedetail/{article_id}/sindonews'
        return new_url
    else:
        return url

def is_valid_url(url):
    # Regex pattern for URL validation
    regex = re.compile(
        r'^(?:http|ftp)s?://'  # http:// or https://
        r'(?:(?:[A-Z0-9](?:[A-Z0-9-]{0,61}[A-Z0-9])?\.)+(?:[A-Z]{2,6}\.?|[A-Z0-9-]{2,}\.?)|'  # domain...
        r'localhost|'  # localhost...
        r'\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}|'  # ...or ipv4
        r'\[?[A-F0-9]*:[A-F0-9:]+\]?)'  # ...or ipv6
        r'(?::\d+)?'  # optional port
        r'(?:/?|[/?]\S+)$', re.IGNORECASE)

    # Validate URL using regex
    if re.match(regex, url) is not None:
        # Further validation using urlparse
        parsed_url = urlparse(url)
        return all([parsed_url.scheme, parsed_url.netloc])
    return False

def is_contain(comparison, text):
    if isinstance(comparison, str):
        return comparison in text
    elif isinstance(comparison, list):
        for comp in comparison:
            if comp in text:
                return True
        return False
    else:
        raise ValueError("Parameter 'comparison' harus berupa string tunggal atau list/array dari string.")

def is_contains(comparison, text):
    return any(substring in text for substring in comparison)

def get_jina_parsed_links(text):
    # Regex untuk valid URL
    url_pattern = re.compile(
        r'\b(?:https?://|www\.)[a-zA-Z0-9\-.]+(?:/[^\s]*)?\b', re.IGNORECASE
    )

    # Regex untuk menemukan URL di dalam '](...)'
    bracket_url_pattern = re.compile(
        r'\]\((https?://[^\)]+)\)', re.IGNORECASE
    )

    urls = url_pattern.findall(text)

    # Menemukan semua URL yang cocok dalam pola '](...)'
    bracket_urls = bracket_url_pattern.findall(text)

    after_right_bracket_urls = []
    for url in urls:
        index = url.find(')[')
        if index != -1:
            modified_url = url[:index]
            after_right_bracket_urls.append(modified_url)
        else:
            after_right_bracket_urls.append(url)

    all_urls = urls + bracket_urls + after_right_bracket_urls

    invalid_list = [
        ')]', 'tbn:', 'search', 'pencarian', 'tag',
        '...', '**', '[]', ')]', '[(', ')[',
        'jpeg', 'jpg', 'png', 'webp', 'svg',
        'utm_source', 'whatsapp.com', 'edit', 'profile', 'dashboard',
        'about', 'contact', 'linkedin', 'play.google', 'twitter', 'x.com', 'youtube.com', 'logout', 'login', 'signin', 'signout', 'sign-in', 'sign-out', 'apple.com'
    ]

    valid_urls = [
        url for url in all_urls
        if is_valid_url(url)
        and not is_contain(invalid_list, url)
        and len(url) > 50
    ]

    # Menghapus URL yang duplikat
    urls = list(set(valid_urls))

    # Buat daftar dictionary berisi title dan url
    url_list = []

    for url in urls:
        title = get_title_from_slug(url)
        url_list.append({
            "title": title,
            "url": url
        })

    return url_list

def get_title_from_slug(url):
    # Parsing URL untuk mendapatkan path tanpa query parameter
    parsed_url = urlparse(url)
    path = parsed_url.path

    # Ambil slug dari path
    slug = path.rstrip('/').split('/')[-1]

    # Dekode slug untuk menghilangkan karakter yang ter-encode
    slug = unquote(slug)

    # Pecahkan slug menjadi kata-kata dengan memisahkan pada tanda '-'
    words = slug.split('-')

    # Hapus kata pertama jika mengandung hanya angka
    if words and words[0].isdigit():
        words.pop(0)

    # Inisialisasi daftar kata kapital
    capitalized_words = []

    # Periksa setiap kata
    for word in words:
        # Kapitalisasi kata
        capitalized_words.append(word.capitalize())

    # Gabungkan kembali kata-kata menjadi kalimat
    title = ' '.join(capitalized_words)

    title = title.strip()

    # Atur titik di akhir kalimat
    title = title.replace('Bnn', 'BNN').replace('Rp', 'Rp.').replace('Kbb', 'KBB').replace('Ai', 'AI').replace('.html', '').replace('Ri', 'RI').replace('Mvk', '')

    return title

def merge_unique_entries(result_list):
    temp_dict = {}
    for entry in result_list:
        for key, value in entry.items():
            # Pastikan value adalah list dan tidak mengandung dict
            if not isinstance(value, list):
                raise TypeError(f"Value for key {key} is not a list")
            if any(isinstance(i, dict) for i in value):
                raise TypeError(f"Value for key {key} contains a dict")

            if key not in temp_dict:
                temp_dict[key] = set(map(str, value))  # Convert each entry to string if needed
            else:
                temp_dict[key].update(map(str, value))

    unique_result_list = [{key: list(map(eval, value))} for key, value in temp_dict.items()]  # Convert back to original type
    return unique_result_list