from typing import Annotated
from urllib.parse import unquote, urlparse
from bs4 import BeautifulSoup

from fastapi import HTTPException, Depends, status, Request
import datetime
import httpx
import re
import markdown
from pydantic import BaseModel
import validators
from utils import get_clean_payload, get_parsed_links, validate_redirect_urls, is_valid_url, is_contain, is_contains, get_jina_parsed_links, get_title_from_slug, merge_unique_entries
import models
import schemas
from database import get_db
from sqlalchemy.orm import Session
from fastapi import APIRouter

from requests_html import AsyncHTMLSession
import asyncio

router = APIRouter()

db_dependency = Annotated[Session, Depends(get_db)]

EXCLUDED_ID = [6, 7, 8, 9, 10, 11]

@router.get("/crawler", response_model=list[schemas.CrawlerCreate])
def crawler(db: db_dependency):
    data = db.query(models.Crawler)
    return data

@router.post("/crawler", response_model=schemas.CrawlerCreate)
def crawlerpost(crawler: schemas.CrawlerCreate, db: db_dependency):
    data = crawler.dict()
    db_news = models.Crawler(**data)
    db.add(db_news)
    db.commit()
    return db_news

JINA_API_KEYS = [
    'jina_f9230a37378f4540879fab2b1e741cd53rxAaF64oGBakNwpeKvcp_e7RpsM',
]

@router.get("/latest", summary='Mendapatkan berita dari satu media dengan tipe latest')
async def latest(db: db_dependency, kode:str):
    try:
        crawler = db.query(models.Crawler).filter(models.Crawler.code == kode).first()

        if not crawler:
            raise HTTPException(status_code=400, detail="Crawler tidak ditemukan ...")

        result_list = []
        async with httpx.AsyncClient() as client:
            url = crawler.url_latest
            target_url = f"https://r.jina.ai/{url}"

            for api_key in JINA_API_KEYS:
                headers = {'Authorization': f'Bearer {api_key}'}
                try:
                    response = await client.get(target_url, headers=headers, timeout=None)
                    response.raise_for_status()
                    data = response.text
                    print(response.text)
                    parsed_data = get_jina_parsed_links(data)
                    result_list.append({url: parsed_data})
                    return {"status": "success", "data": result_list}
                except httpx.HTTPStatusError as http_err:
                    if http_err.response.status_code == 402:
                        continue  # Coba dengan API key berikutnya
                    else:
                        raise HTTPException(status_code=http_err.response.status_code, detail=str(http_err))
                except httpx.RequestError as req_err:
                    raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(req_err))

        raise HTTPException(status_code=402, detail="Semua API key telah dicoba namun tetap mendapatkan error 402")

    except httpx.RequestError as req_err:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(req_err))

@router.get("/popular", summary='Mendapatkan berita dari satu media dengan tipe popular')
async def popular(db: db_dependency, kode:str):
    try:
        crawler = db.query(models.Crawler).filter(models.Crawler.code == kode).first()
        result_list = []

        async with httpx.AsyncClient() as client:
            for api_key in JINA_API_KEYS:
                headers = {'Authorization': f'Bearer {api_key}'}
                try:
                    url = crawler.url_popular
                    headers = {'Authorization': 'Bearer ' + api_key}
                    target_url = "https://r.jina.ai/" + url

                    response = await client.get(target_url, headers=headers, timeout=None)
                    response.raise_for_status()
                    data = response.text
                    parsed_data = get_jina_parsed_links(data)
                    result_list.append({url: parsed_data})

                    return {"status": "success", "data": result_list}
                except httpx.HTTPStatusError as http_err:
                    if http_err.response.status_code == 402:
                        continue
                    else:
                        raise HTTPException(status_code=http_err.response.status_code, detail=str(http_err))
                except httpx.RequestError as req_err:
                    raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(req_err))
    except httpx.HTTPStatusError as http_err:
        raise HTTPException(status_code=http_err.response.status_code, detail=str(http_err))
    except httpx.RequestError as req_err:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(req_err))

@router.get("/search", summary='Mendapatkan berita dari satu media')
async def search(db: db_dependency, kode:str, query: str):
    try:
        crawler = db.query(models.Crawler).filter(models.Crawler.code == kode).first()
        result_list = []

        async with httpx.AsyncClient() as client:
            for api_key in JINA_API_KEYS:
                headers = {'Authorization': f'Bearer {api_key}'}
                try:
                    search_query = query.replace(' ', '%20')
                    url = crawler.url_search + search_query
                    headers = {'Authorization': f'Bearer {api_key}'}
                    target_url = f"https://r.jina.ai/{url}"

                    response = await client.get(target_url, headers=headers, timeout=None)
                    response.raise_for_status()
                    data = response.text
                    parsed_data = get_jina_parsed_links(data)

                    result_list.append({url: parsed_data})

                    return {"status": "success", "data": result_list}
                except httpx.HTTPStatusError as http_err:
                    if http_err.response.status_code == 402:
                        continue
                    else:
                        raise HTTPException(status_code=http_err.response.status_code, detail=str(http_err))
                except httpx.RequestError as req_err:
                    raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(req_err))
    except httpx.HTTPStatusError as http_err:
        raise HTTPException(status_code=http_err.response.status_code, detail=str(http_err))
    except httpx.RequestError as req_err:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(req_err))

@router.get("/all/search", summary='Mendapatkan berita dari semua media')
async def search_all(db: db_dependency, query: str, limit: int = 1):
    try:
        crawlers = db.query(models.Crawler).all()
        crawler_urls = []

        if not query:
            raise HTTPException(status_code=400, detail="Query search tidak boleh kosong")

        for crawler in crawlers:
            if crawler.id in EXCLUDED_ID:
                continue

            url = crawler.url_search + query.replace(' ', '%20')
            crawler_urls.append({ "title": crawler.title, "search": url })

        temp_dict = {}
        media_count_dict = []

        for crawler_url in crawler_urls:
            async with httpx.AsyncClient() as client:
                for api_key in JINA_API_KEYS:
                    headers = {'Authorization': f'Bearer {api_key}'}
                    try:
                        target_url = f"https://r.jina.ai/{crawler_url['search']}"

                        print(f'Scraping jina.ai {target_url}')

                        response = await client.get(target_url, headers=headers, timeout=None)
                        response.raise_for_status()
                        parsed_data = get_jina_parsed_links(response.text)

                        print(f'Appending {crawler_url["title"]}', parsed_data)

                        media_count_dict.append({
                            'title': crawler_url['title'],
                            'count': len(parsed_data)
                        })

                        key = f"{crawler_url['title']} - {crawler_url['search']}"
                        if key not in temp_dict:
                            temp_dict[key] = parsed_data
                        else:
                            temp_dict[key].extend(parsed_data)
                            temp_dict[key] = list(dict.fromkeys(temp_dict[key]))
                        break
                    except httpx.HTTPStatusError as http_err:
                        if http_err.response.status_code == 402:
                            continue
                        else:
                            raise HTTPException(status_code=http_err.response.status_code, detail=str(http_err))
                    except httpx.RequestError as req_err:
                        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(req_err))

        result_list = []
        for articles in temp_dict.values():
            if limit > 0:
                result_list.extend(articles[:limit])
            else:
                result_list.extend(articles)

        return {"status": "success", "media": media_count_dict, "data": result_list}
    except httpx.HTTPStatusError as http_err:
        raise HTTPException(status_code=http_err.response.status_code, detail=str(http_err))
    except httpx.RequestError as req_err:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(req_err))

@router.get("/all/latest", summary='Mendapatkan berita dari semua media')
async def latest_all(db: db_dependency, limit: int = 1):
    try:
        crawlers = db.query(models.Crawler).all()
        crawler_urls = []

        for crawler in crawlers:
            if crawler.id in EXCLUDED_ID:
                continue

            url = crawler.url_latest
            crawler_urls.append({"title": crawler.title, "url": url})

        temp_dict = {}

        for crawler_url in crawler_urls:
            async with httpx.AsyncClient() as client:
                for api_key in JINA_API_KEYS:
                    headers = {'Authorization': f'Bearer {api_key}'}
                    try:
                        target_url = f"https://r.jina.ai/{crawler_url['url']}"

                        print(f'Scraping jina.ai {target_url}')

                        response = await client.get(target_url, headers=headers, timeout=None)
                        response.raise_for_status()
                        parsed_data = get_jina_parsed_links(response.text)

                        print(f'Appending {crawler_url["title"]}', parsed_data)

                        key = f"{crawler_url['title']} - {crawler_url['url']}"
                        if key not in temp_dict:
                            temp_dict[key] = parsed_data
                        else:
                            temp_dict[key].extend(parsed_data)
                            temp_dict[key] = list(dict.fromkeys(temp_dict[key]))
                        break
                    except httpx.HTTPStatusError as http_err:
                        if http_err.response.status_code == 402:
                            continue
                        else:
                            raise HTTPException(status_code=http_err.response.status_code, detail=str(http_err))
                    except httpx.RequestError as req_err:
                        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(req_err))

        result_list = []
        for articles in temp_dict.values():
            if limit > 0:
                result_list.extend(articles[:limit])
            else:
                result_list.extend(articles)

        return {"status": "success", "data": result_list}
    except httpx.HTTPStatusError as http_err:
        raise HTTPException(status_code=http_err.response.status_code, detail=str(http_err))
    except httpx.RequestError as req_err:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(req_err))

@router.get("/all/popular", summary='Mendapatkan berita dari semua media')
async def popular_all(db: db_dependency, limit: int = 1):
    try:
        crawlers = db.query(models.Crawler).all()
        crawler_urls = []

        for crawler in crawlers:
            if crawler.id in EXCLUDED_ID:
                continue

            url = crawler.url_popular
            crawler_urls.append({ "title": crawler.title, "url": url })

        temp_dict = {}

        for crawler_url in crawler_urls:
            async with httpx.AsyncClient() as client:
                for api_key in JINA_API_KEYS:
                    headers = {'Authorization': f'Bearer {api_key}'}
                    try:
                        target_url = f"https://r.jina.ai/{crawler_url['url']}"

                        print(f'Scraping jina.ai {target_url}')

                        response = await client.get(target_url, headers=headers, timeout=None)
                        response.raise_for_status()
                        parsed_data = get_jina_parsed_links(response.text)

                        print(f'Appending {crawler_url["title"]}', parsed_data)

                        key = f"{crawler_url['title']} - {crawler_url['url']}"
                        if key not in temp_dict:
                            temp_dict[key] = parsed_data
                        else:
                            temp_dict[key].extend(parsed_data)
                            temp_dict[key] = list(dict.fromkeys(temp_dict[key]))
                        break
                    except httpx.HTTPStatusError as http_err:
                        if http_err.response.status_code == 402:
                            continue
                        else:
                            raise HTTPException(status_code=http_err.response.status_code, detail=str(http_err))
                    except httpx.RequestError as req_err:
                        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(req_err))

        result_list = []
        for articles in temp_dict.values():
            if limit > 0:
                result_list.extend(articles[:limit])
            else:
                result_list.extend(articles)

        return {"status": "success", "data": result_list}
    except httpx.HTTPStatusError as http_err:
        raise HTTPException(status_code=http_err.response.status_code, detail=str(http_err))
    except httpx.RequestError as req_err:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(req_err))

@router.post('/get_links')
async def get_links(url: str):
    try:
        async with httpx.AsyncClient() as client:

            if 'republika.co.id/search' in url:
                url = f'https://r.jina.ai/{url}'

            response = await client.get(url, timeout=None)
            response.raise_for_status()
            data = response.text

            if 'jina' in url:
                result = get_jina_parsed_links(data)
            else:
                result = get_parsed_links(url, data)

        return {"status": "success", "data": result}
    except httpx.HTTPStatusError as http_err:
        raise HTTPException(status_code=http_err.response.status_code, detail=str(http_err))
    except httpx.RequestError as req_err:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(req_err))

@router.get("/scrape")
async def scrape(url: str):
    session = AsyncHTMLSession()

    async def get_page():
        response = await session.get(url)
        await asyncio.sleep(3)
        await response.html.arender()
        return response.html.html

    html_content = await get_page()
    return {"content": html_content}

@router.get('/get_payload')
async def get_payload(url: str):
    try:
        async with httpx.AsyncClient() as client:
            for api_key in JINA_API_KEYS:
                headers = {'Authorization': f'Bearer {api_key}'}
                try:
                    target_url = validate_redirect_urls(url)

                    print('Visiting url :', target_url)

                    response = await client.get(target_url, headers=headers, timeout=None)
                    response.raise_for_status()

                    data = response.text

                    payload = get_clean_payload(data, target_url)

                    print('CLEANED_DATA', payload)

                    if payload['status'] == 0:
                        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=payload)

                    return {'status': 'success', 'data': payload}
                except httpx.HTTPStatusError as http_err:
                    if http_err.response.status_code == 402:
                        continue
                    elif http_err.response.status_code == 307:
                        redirect_location = http_err.response.headers.get("Location")
                        if redirect_location:
                            print(f'Redirecting to {redirect_location}')
                            url = redirect_location
                            continue
                    else:
                        raise HTTPException(status_code=http_err.response.status_code, detail=str(http_err))
                except httpx.RequestError as req_err:
                    raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(req_err))
    except httpx.HTTPStatusError as http_err:
        raise HTTPException(status_code=http_err.response.status_code, detail=str(http_err))
    except httpx.RequestError as req_err:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(req_err))

@router.post('/process')
async def process(url: str):
    try:
        API_SUMMARY_POST = 'https://chat.iotekno.id/store'

        async with httpx.AsyncClient() as client:
            for api_key in JINA_API_KEYS:
                headers = {'Authorization': f'Bearer {api_key}'}
                try:
                    target_url = validate_redirect_urls(url)

                    print(f'Visiting url: {target_url}')

                    response = await client.get(target_url, headers=headers, timeout=None)

                    response.raise_for_status()

                    payload = None

                    data = response.text

                    # if 'reCAPTCHA' in data or 'recaptcha' in data:
                    #     raise HTTPException(status_code=400, detail="Blocked!!! Content contains reCAPTCHA challenge")

                    content_date = datetime.datetime.now().strftime('%Y-%m-%d')

                    cleaned_data = get_clean_payload(data, target_url)

                    if cleaned_data['status'] == 0:
                        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=cleaned_data)

                    print('CLEANED_DATA', cleaned_data)

                    payload = {
                        "title": cleaned_data['title'],
                        "url": url,
                        "content": cleaned_data['data'], "content_date": content_date
                    }

                    print('PAYLOAD KETIKA POST', payload)

                    response_post = await client.post(API_SUMMARY_POST, json=payload, timeout=None)

                    response_post.raise_for_status()

                    data_post = response_post.json()

                    return {'status': 'success', 'data': data_post, 'payload': payload}
                except httpx.HTTPStatusError as http_err:
                    if http_err.response.status_code == 402:
                        continue
                    else:
                        raise HTTPException(status_code=http_err.response.status_code, detail=str(http_err))
                except httpx.RequestError as req_err:
                    raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(req_err))
    except httpx.HTTPStatusError as http_err:
        raise HTTPException(status_code=http_err.response.status_code, detail=str(http_err))
    except httpx.RequestError as req_err:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(req_err))



# NOT USED

# @router.post("/", response_model=schemas.NewsCreate, summary='Menambahkan data berita hasil crawling')
# def create_news(news: schemas.NewsCreate, db: db_dependency):
#     data = news.dict()
#     db_news = models.News(**data)
#     db.add(db_news)
#     db.commit()
#     db.refresh(db_news)
#     if not db_news.id:
#         raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Failed to create news")

#     return db_news

# @router.get("/", response_model=list[schemas.NewsCreate], summary='Data berita hasil crawling')
# def get_news(db: db_dependency):
#     data = db.query(models.News)
#     return data

# @router.get('/list/')
# async def get_list(db: db_dependency, query: str):
#     try:
#         crawlers = db.query(models.Crawler).all()

#         crawler_urls = []

#         if not query:
#             raise HTTPException(status_code=400, detail="Query search tidak boleh kosong")

#         for crawler in crawlers:
#             """
#                 6: Kompas
#                 7: Liputan6
#                 8: Detik
#                 9: Tribun
#                 10: CNN Indonesia
#             """
#             if crawler.id in EXCLUDED_ID:
#                 continue

#             search_query = query.replace(' ', '%20')
#             url = crawler.url_search + search_query
#             crawler_urls.append({ "title": crawler.title, "search": url })

#         result_list = []

#         for crawler_url in crawler_urls:
#             async with httpx.AsyncClient() as client:
#                 headers = {"User-agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/77.0.3865.120 Safari/537.36"}
#                 url = crawler_url['search']

#                 response = await client.get(url, headers=headers, timeout=None)
#                 response.raise_for_status()

#                 content = response.text

#                 list_article = []

#                 if 'tempo' in url:
#                     list_article = get_articles(content, 'tempo')
#                 elif 'republika' in url:
#                     list_article = get_articles(content, 'republika')
#                 elif 'viva' in url:
#                     list_article = get_articles(content, 'viva')
#                 elif 'merdeka' in url:
#                     list_article = get_articles(content, 'merdeka')
#                 elif 'sindo' in url:
#                     list_article = get_articles(content, 'sindo')

#                 item = {
#                     crawler_url['title']: list_article
#                 }

#                 result_list.append(item)

#         return {"status": "success", "data": result_list}
#     except httpx.HTTPStatusError as http_err:
#         raise HTTPException(status_code=http_err.response.status_code, detail=str(http_err))
#     except httpx.RequestError as req_err:
#         raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(req_err))

# @router.get('/detail/')
# async def get_detail(url: str):
#     try:
#         async with httpx.AsyncClient() as client:
#             headers = {"User-agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/77.0.3865.120 Safari/537.36"}

#             response = await client.get(url, headers=headers, timeout=None)
#             response.raise_for_status()

#             content = response.text

#             article = None

#             if 'tempo' in url:
#                 article = get_article(content, 'tempo')
#             elif 'republika' in url:
#                 article = get_article(content, 'republika')
#             elif 'viva' in url:
#                 article = get_article(content, 'viva')
#             elif 'merdeka' in url:
#                 article = get_article(content, 'merdeka')
#             elif 'sindo' in url:
#                 article = get_article(content, 'sindo')

#             # payload = {"url": url, "content": article['content'], "content_date": article['date']}

#             # response_post = await client.post('http://iotekno.id:8000/store', json=payload, timeout=None)

#             # data_post = response_post.json()

#             return {'status': 'success', 'article': article}
#     except httpx.HTTPStatusError as http_err:
#         raise HTTPException(status_code=http_err.response.status_code, detail=str(http_err))
#     except httpx.RequestError as req_err:
#         raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(req_err))

# def get_articles(content, media):
#     if media == 'tempo':
#         return get_articles_tempo(content)
#     elif media == 'republika':
#         return get_articles_republika(content)
#     elif media == 'viva':
#         return get_articles_viva(content)
#     elif media == 'merdeka':
#         return get_articles_merdeka(content)
#     elif media == 'sindo':
#         return get_articles_sindo(content)
#     return get_articles_tempo(content)

# def get_articles_sindo(content):
#     return []

# def get_articles_merdeka(content):
#     return []

# def get_articles_viva(content):
#     return []

# def get_articles_republika(content):
#     soup = BeautifulSoup(content, 'html.parser')

#     results = soup.select('.gsc-webResult')
#     articles = ['A', 'B', len(results)]

#     for result in results:
#         title = result.find('a', class_='gs-title').text.strip()
#         link = result.find('a', class_='gs-title')['href']
#         date = result.find('div', class_='gs-snippet').text.strip().split()[0]

#         image = result.find('img', class_='gs-image')['src']
#         excerpt = result.find('div', class_='gs-snippet').text.strip()

#         article = {
#             'title': title,
#             'link': link,
#             'date': date,
#             'image': image,
#             'excerpt': excerpt
#         }

#         articles.append(article)

#     print('Republika articles', articles)

#     return articles

# def get_articles_tempo(content):
#     return []

# def get_article(content, media):
#     if media == 'tempo':
#         return get_article_tempo(content)
#     elif media == 'republika':
#         return get_article_republika(content)
#     elif media == 'viva':
#         return get_article_viva(content)
#     elif media == 'merdeka':
#         return get_article_merdeka(content)
#     elif media == 'sindo':
#         return get_article_sindo(content)
#     return get_article_tempo(content)

# def get_article_sindo(content):
#     soup = BeautifulSoup(content, 'html.parser')

#     article = {}

#     article['title'] = soup.select_one('title').text

#     article['date'] = soup.select_one('.detail-date-artikel').text

#     article['image'] = soup.select_one('.detail-img img').get('data-src')

#     detail_desc = soup.select_one('.detail-desc')

    # for div in detail_desc.find_all('div'):
    #     div.extract()

    # clean_text = detail_desc.get_text(separator='\n').strip()

#     article['content'] = clean_text

#     return article


# def get_article_merdeka(content):
#     soup = BeautifulSoup(content, 'html.parser')

#     article = {}

#     article['title'] = soup.select_one('title').text

#     article['date'] = soup.select_one('.dt-inner .dt-desc-row-pub-date').get('datetime')

#     article['image'] = soup.select_one('.dt-inner .dt-asset img').get('src')

#     article_content_ps = soup.select('.dt-inner .dt-inner-body .dt-para p')

#     texts = []

#     for p in article_content_ps:
#         text = p.get_text(strip=True)
#         texts.append(text)
#         texts.append('\n')

#     if texts[-1] == '\n':
#         texts.pop()

#     article['content'] = ' '.join(texts)

#     return article

# def get_article_viva(content):
#     soup = BeautifulSoup(content, 'html.parser')

#     article = {}

#     article['title'] = soup.select_one('title').text

#     article['date'] = soup.select_one('.main-content-date').text.replace('\n', '')

#     article['image'] = soup.select_one('.main-content-image img').get('src')

#     article_content_ps = soup.select('.main-content-detail p')

#     texts = []

#     for p in article_content_ps:
#         text = p.get_text(strip=True)
#         texts.append(text)
#         texts.append('\n')

#     if texts[-1] == '\n':
#         texts.pop()

#     article['content'] = ' '.join(texts)

#     return article

# def get_article_republika(content):
#     soup = BeautifulSoup(content, 'html.parser')

#     article = {}

#     article['title'] = soup.select_one('title').text

#     article['date'] = soup.select_one('.read-title h2:nth-of-type(2) span').text

#     article['date'] = ' '.join(article['date'].split())

#     article['image'] = soup.select_one('.read-cover img').get('data-original')

#     article_content_ps = soup.select('.read-desc .read-thumb p')

#     texts = []

#     for p in article_content_ps:
#         text = p.get_text(strip=True)
#         texts.append(text)
#         texts.append('\n')

#     if texts[-1] == '\n':
#         texts.pop()

#     article['content'] = ' '.join(texts)

#     return article

# def get_article_tempo(content):
#     soup = BeautifulSoup(content, 'html.parser')

#     article = {}

#     article['title'] = soup.select_one('.detail-artikel .detail-title .title').text

#     article['date'] = soup.select_one('.detail-artikel .detail-title .date').text

#     article['image'] = soup.select_one('.detail-artikel .foto-detail img').get('src')

#     article_content_ps = soup.select('.detail-artikel #isi .rows-konten .detail-konten p')

#     texts = []

#     for p in article_content_ps:
#         text = p.get_text(strip=True)
#         texts.append(text)
#         texts.append('\n')

#     if texts[-1] == '\n':
#         texts.pop()

#     article['content'] = ' '.join(texts)

#     return article