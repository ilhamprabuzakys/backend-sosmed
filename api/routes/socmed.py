import datetime
from itertools import islice
from typing import Annotated, Union
from urllib.parse import quote

from fastapi import FastAPI, HTTPException, Depends, status, Request
import httpx
# import requests
import re
from pydantic import BaseModel
import models
import schemas
from database import SessionLocal, engine, get_db
from sqlalchemy.orm import Session
from fastapi import APIRouter

router = APIRouter()
db_dependency = Annotated[Session, Depends(get_db)]

@router.get("/crawler/",response_model=list[schemas.CrawlerSocmedCreate])
def crawler(db: db_dependency):
    crawler = db.query(models.CrawlerSocmed)
    return crawler

@router.post("/crawler", response_model=schemas.CrawlerSocmedCreate)
def crawlerPost(sosmed: schemas.CrawlerSocmedCreate, db: db_dependency):
    data = sosmed.dict()
    db_socmed = models.CrawlerSocmed(**data)
    db.add(db_socmed)
    db.commit()
    db.refresh(db_socmed)
    if not db_socmed.id:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Failed to create crawler socmed")

    return db_socmed

@router.get("/get_content", summary='Mendapatkan data rangkuman dari konten media sosial')
async def get_content(db: db_dependency, code: str, detail_id: str):
    try:
        API_SUMMARY_POST = 'https://chat.iotekno.id/store'

        if not detail_id:
            raise HTTPException(status_code=500, detail="Media ID tidak boleh kosong")

        socmed = db.query(models.CrawlerSocmed).filter(models.CrawlerSocmed.code == code).first()

        if not socmed:
            raise HTTPException(status_code=500, detail=f"Sosial media dengan kode {code} tidak ditemukan")

        api_key = socmed.api_key
        api_host = socmed.api_host
        detail_url = f"{socmed.url_video}{detail_id}"
        url = f'https://{api_host}{detail_url}'
        headers = {
            'x-rapidapi-key': f'{api_key}',
            'x-rapidapi-host': f'{api_host}'
        }

        print(f'[{socmed.title}] - Visiting rapidapi url', url)

        async with httpx.AsyncClient() as client:
            response = await client.get(url, headers=headers, timeout=None)
            data = response.json()

            print('\nRAW RESPONSE:', data)

            if 'message' in data:
                raise HTTPException(status_code=400, detail=data['message'])

            payload = get_parsed_content(code, data, detail_id)

            response_post = await client.post(API_SUMMARY_POST, json=payload, timeout=None)

            data_post = response_post.json()

            return {
                'status': 'success',
                'data': data_post,
                'payload': payload
            }
    except httpx.HTTPStatusError as http_err:
        raise HTTPException(status_code=http_err.response.status_code, detail=str(http_err))
    except httpx.RequestError as req_err:
        raise HTTPException(status_code=500, detail=str(req_err))

@router.get('/get_comments', summary='Mendapatkan data komentar dari konten media sosial')
async def get_comments(db: db_dependency, code: str, detail_id: str):
    try:
        if not detail_id:
            raise HTTPException(status_code=500, detail="Media ID tidak boleh kosong")

        socmed = db.query(models.CrawlerSocmed).filter(models.CrawlerSocmed.code == code).first()

        if not socmed:
            raise HTTPException(status_code=500, detail=f"Sosial media dengan kode {code} tidak ditemukan")

        api_key = socmed.api_key
        api_host = socmed.api_host
        url = f"{socmed.url_comment}{detail_id}"
        headers = {
            'x-rapidapi-key': f'{api_key}',
            'x-rapidapi-host': f'{api_host}'
        }

        print(f'[{socmed.title}] - Visiting rapidapi url', url)

        async with httpx.AsyncClient() as client:
            response = await client.get(url, headers=headers, timeout=None)
            data = response.json()

            print('\nRAW RESPONSE:', data)

            if 'message' in data:
                raise HTTPException(status_code=400, detail=data['message'])

            parsed_data = {}

            if code == 'YT':
                parsed_data['parent_id'] = detail_id
                parsed_data['total'] = data['total_number_of_comments']
                parsed_data['get'] = data['number_of_comments']

                processed_comments = []

                for comment in data['comments']:
                    processed_comment = {}
                    processed_comment['id'] = comment['id']
                    processed_comment['author'] = comment['author_name']
                    processed_comment['author']['channel_id'] = comment['author_channel_id']
                    processed_comment['text'] = comment['text']
                    processed_comment['like_count'] = comment['like_count']
                    processed_comment['reply_count'] = comment['number_of_replies']
                    processed_comment['published_time'] = comment['published_time']

                    processed_comments.append(processed_comment)

                parsed_data['comments'] = processed_comments
            elif code == 'TW':
                parsed_data['message'] = f'Unable to get replies for tweet ID = {detail_id}'
            elif code == 'IG':
                data = data['data']
                parsed_data['parent_id'] = detail_id
                parsed_data['total'] = data['count']
                parsed_data['get'] = data['count']

                processed_comments = []

                for comment in data['items']:
                    processed_comment = {}
                    processed_comment['id'] = comment['id']
                    processed_comment['author'] = {}
                    processed_comment['author']['name'] = comment['user']['full_name']
                    processed_comment['author']['username'] = comment['user']['username']
                    processed_comment['text'] = comment['text']
                    processed_comment['like_count'] = comment['like_count']
                    processed_comment['reply_count'] = comment['mentions']
                    published_time_raw = datetime.datetime.fromtimestamp(comment['created_at'])
                    published_time = published_time_raw.strftime('%Y-%m-%d %H:%M:%S')
                    processed_comment['published_time'] = published_time

                    processed_comments.append(processed_comment)

                parsed_data['comments'] = processed_comments
            elif code == 'TT':
                data = data['data']
                parsed_data['parent_id'] = detail_id
                parsed_data['total'] = len(data['comments'])
                parsed_data['get'] = parsed_data['total']

                processed_comments = []

                for comment in data['comments']:
                    processed_comment = {}
                    processed_comment['id'] = comment['aweme_id']
                    processed_comment['author'] = {}
                    processed_comment['author']['name'] = comment['user']['nickname']
                    processed_comment['text'] = comment['text']
                    processed_comment['like_count'] = comment['digg_count']
                    published_time_raw = datetime.datetime.fromtimestamp(comment['create_time'])
                    published_time = published_time_raw.strftime('%Y-%m-%d %H:%M:%S')
                    processed_comment['published_time'] = published_time

                    processed_comments.append(processed_comment)

                parsed_data['comments'] = processed_comments

            return {
                'status': 'success',
                'data': parsed_data,
            }
    except httpx.HTTPStatusError as http_err:
        raise HTTPException(status_code=http_err.response.status_code, detail=str(http_err))
    except httpx.RequestError as req_err:
        raise HTTPException(status_code=500, detail=str(req_err))

def get_parsed_content(code: str, data, detail_id: str):
    content_date = datetime.datetime.now().strftime('%Y-%m-%d')

    if code == 'YT':
        author = data['author']
        title = data['title']
        category = data['category']
        url = f"https://www.youtube.com/watch?v={detail_id}"
        content = f'{author} membuat video berjudul {title} dengan kategori {category}'
    elif code == 'TW':
        user = data['user']['username']
        content = f'User dengan username {user} membuat tweet pada X yang berisikan: {data["text"]}, pada waktu {data["creation_date"]}'
        content_date = data['creation_date']
        url = f'https://x.com/{user}/status/{detail_id}'
    elif code == 'IG':
        user = data['data']['user']['username']
        url = f'https://www.instagram.com/p/{detail_id}/'
        caption = '-' if not data['data']['caption'] else data['data']['caption']
        media_name = data['data']['media_name'].capitalize()
        content_date_raw = datetime.datetime.fromtimestamp(data['data']['taken_at'])
        content_date = content_date_raw.strftime('%Y-%m-%d %H:%M:%S')
        content = f"{user} memposting suatu {media_name}"
        content += f' dengan caption {caption}' if caption != '-' else ' tanpa caption'
        content += f', pada waktu {content_date}'
        content = f' tidak perlu dirangkum hanya kirim ulang kembali saja pesan berikut "{content}" dikarenakan postingan dari {user} ini tidak memiliki caption' if caption == '-' else caption
    elif code == 'TT':
        user = data['data']['aweme_detail']['author']['username']
        caption = data['data']['aweme_detail']['desc']
        url = data['data']['aweme_detail']['share_url']
        content_date_raw = datetime.datetime.fromtimestamp(data['data']['aweme_detail']['create_time'])
        content_date = content_date_raw.strftime('%Y-%m-%d %H:%M:%S')

        content = f"{user} memposting suatu video"
        content += f' dengan caption {caption}' if caption != '-' else ' tanpa caption'
        content += f', pada waktu {content_date}'
        content = f' tidak perlu dirangkum hanya kirim ulang kembali saja pesan berikut "{content}" dikarenakan postingan dari {user} ini tidak memiliki caption' if caption == '-' else caption

    payload = {"url": url, "content": content, "content_date": content_date}

    return payload

@router.get("/all/search")
async def search_all(db: db_dependency, query: str, limit: int = 5):
    try:
        if not query:
            raise HTTPException(status_code=500, detail="Query search tidak boleh kosong")

        crawlers = db.query(models.CrawlerSocmed).all()
        crawler_urls = []

        for crawler in crawlers:
            url = crawler.url_search

            if '%s' in url:
                search_path = url.replace('%s', quote(query))
            else:
                search_path = f"{url}{quote(query)}"

            crawler_urls.append({
                "search": search_path,
                "host": crawler.api_host,
                "api_key": crawler.api_key,
                "code": crawler.code,
                "title": crawler.title,
                "ori_search": crawler.url_search
            })

        result_list = []

        with httpx.Client() as client:
            for crawler_url in crawler_urls:
                api_key = crawler_url['api_key']
                api_host = crawler_url['host']
                search_path = crawler_url['search']

                url = f"https://{api_host}{search_path}"
                headers = {
                    'x-rapidapi-key': f'{api_key}',
                    'x-rapidapi-host': f'{api_host}'
                }

                print('Pencarian pada url:', url)

                response = client.get(url, headers=headers, timeout=None)
                data = response.json()


                parsed_data = []

                if crawler_url['code'] == 'IG':
                    data = data['data']['items']

                    for item in data:
                        parsed_single_data = {}

                        parsed_single_data['id'] = item['code']
                        parsed_single_data['author'] = {}
                        parsed_single_data['author']['name'] = item['user']['full_name']
                        parsed_single_data['author']['username'] = item['user']['username']
                        parsed_single_data['author']['profile_img'] = item['user']['profile_pic_url']
                        parsed_single_data['title'] = f"@{parsed_single_data['author']['username']} - #{query}"
                        parsed_single_data['link'] = f"https://www.instagram.com/p/{item['code']}"
                        parsed_single_data['hashtags'] = item['caption']['hashtags']
                        parsed_single_data['hashtags'] = item["caption"].get("hashtags", [])
                        parsed_single_data['uploaded_at'] = item['taken_at']
                        parsed_single_data['uploaded_at'] = datetime.datetime.fromtimestamp(parsed_single_data['uploaded_at'])
                        parsed_single_data['description'] = item['caption']['text']
                        parsed_single_data['thumbnail'] = item['thumbnail_url']
                        parsed_single_data['comment_count'] = item['comment_count']
                        parsed_single_data['like_count'] = item['like_count']
                        parsed_single_data['media_name'] = item['media_name']

                        parsed_data.append(parsed_single_data)
                elif crawler_url['code'] == 'YT':
                    data = data['videos']

                    for item in data:
                        parsed_single_data = {}

                        parsed_single_data['id'] = item['video_id']
                        parsed_single_data['link'] = f"https://www.youtube.com/watch?v={parsed_single_data['id']}"
                        parsed_single_data['hashtags'] = item.get("parsed_single_data['link']", [])
                        parsed_single_data['uploaded_at'] = item['published_time']
                        parsed_single_data['title'] = item['title']
                        parsed_single_data['description'] = item['description']
                        parsed_single_data['author'] = {}
                        parsed_single_data['author']['name'] = item['author']
                        parsed_single_data['author']['channel_id'] = item['channel_id']
                        parsed_single_data['video_length'] = item['video_length']
                        parsed_single_data['is_live_content'] = item['is_live_content']
                        parsed_single_data['thumbnail'] = item['thumbnails'][0]['url']
                        parsed_single_data['view_count'] = item['number_of_views']

                        parsed_data.append(parsed_single_data)
                elif crawler_url['code'] == 'TW':
                    if 'results' in data:
                        data = data['results']

                        for item in data:
                            parsed_single_data = {}

                            parsed_single_data['id'] = item['tweet_id']
                            parsed_single_data['author'] = {}
                            parsed_single_data['author']['name'] = item['user']['name']
                            parsed_single_data['author']['username'] = item['user']['username']
                            parsed_single_data['link'] = f"https://x.com/{parsed_single_data['author']['username']}/status/{parsed_single_data['id']}"
                            parsed_single_data['created_at'] = item['creation_date']
                            parsed_single_data['timestamp'] = item['timestamp']
                            parsed_single_data['timestamp'] = datetime.datetime.fromtimestamp(parsed_single_data['timestamp'])
                            parsed_single_data['title'] = item['text']
                            parsed_single_data['description'] = item['text']
                            parsed_single_data['media_url'] = item['media_url']
                            parsed_single_data['video_url'] = item['video_url']
                            parsed_single_data['view_count'] = item['views']
                            parsed_single_data['favorite_count'] = item['favorite_count']
                            parsed_single_data['retweet_count'] = item['retweet_count']
                            parsed_single_data['reply_count'] = item['reply_count']
                            parsed_single_data['quote_count'] = item['quote_count']
                            parsed_single_data['bookmark_count'] = item['bookmark_count']

                            parsed_data.append(parsed_single_data)
                elif crawler_url['code'] == 'TT':
                    data = data['data']['aweme_list']

                    for item in data:
                        parsed_single_data = {}

                        parsed_single_data['id'] = item['aweme_id']
                        parsed_single_data['author'] = {}
                        parsed_single_data['author']['name'] = item['author']['nickname']
                        if 'ins_id' in item['author']:
                            parsed_single_data['author']['username'] = item['author']['ins_id']
                        parsed_single_data['link'] = item['share_url']
                        parsed_single_data['hashtags'] = item.get("parsed_single_data['link']", [])
                        parsed_single_data['created_at'] = item['create_time']
                        parsed_single_data['created_at'] = datetime.datetime.fromtimestamp(parsed_single_data['created_at'])
                        parsed_single_data['title'] = item['desc']
                        parsed_single_data['description'] = item['desc']
                        parsed_single_data['statistics'] = {}
                        parsed_single_data['statistics']['comment_count'] = item['statistics']['comment_count']
                        parsed_single_data['statistics']['download_count'] = item['statistics']['download_count']
                        parsed_single_data['statistics']['play_count'] = item['statistics']['play_count']
                        parsed_single_data['statistics']['share_count'] = item['statistics']['share_count']
                        parsed_single_data['statistics']['whatsapp_share_count'] = item['statistics']['whatsapp_share_count']

                        parsed_data.append(parsed_single_data)

                if limit > 0 and crawler_url['code'] in ['YT', 'TT', 'IG']:
                    parsed_data = parsed_data[:limit]

                item = {
                    'title': crawler_url['title'],
                    'data': parsed_data if parsed_data else data
                    # 'data': data
                }
                result_list.append(item)
        return {"status": "success", "data": result_list}

    except httpx.HTTPStatusError as http_err:
        raise HTTPException(status_code=http_err.response.status_code, detail=str(http_err))
    except httpx.RequestError as req_err:
        raise HTTPException(status_code=500, detail=str(req_err))

# @router.post("/media_comment")
# async def media_comment(db: db_dependency, code: str, media_id: str):
#     try:
#         socmed = db.query(models.CrawlerSocmed).filter(models.CrawlerSocmed.code == code).all()
#         socmed_url = []

#         if not media_id:
#             raise HTTPException(status_code=500, detail="Media ID tidak boleh kosong")

#         for data in socmed:
#             url = data.url_comment
#             search_path = f"{url}{quote(media_id)}"
#             socmed_url.append({
#                 "search": search_path,
#                 "host": data.api_host,
#                 "api_key": data.api_key
#             })

#         result_list = []

#         with httpx.Client() as client:
#             for data in socmed_url:
#                 api_key = data['api_key']
#                 api_host = data['host']
#                 search_path = data['search']

#                 url = search_path
#                 headers = {
#                     'x-rapidapi-key': f'{api_key}',
#                     'x-rapidapi-host': f'{api_host}'
#                 }

#                 print('Mendapatkan komentar dari url:', url)

#                 response = client.get(url, headers=headers, timeout=None)
#                 data = response.json()
#                 item = {
#                     'host': api_host,
#                     search_path: data
#                 }
#                 result_list.append(item)
#         return {"status": "success", "data": result_list}
#     except httpx.HTTPStatusError as http_err:
#         raise HTTPException(status_code=http_err.response.status_code, detail=str(http_err))
#     except httpx.RequestError as req_err:
#         raise HTTPException(status_code=500, detail=str(req_err))

# @router.post("/search_media")
# async def search_media(db: db_dependency, code: str, media_id: str):
#     try:
#         socmed = db.query(models.CrawlerSocmed).filter(models.CrawlerSocmed.code == code).all()
#         socmed_url = []

#         if not media_id:
#             raise HTTPException(status_code=500, detail="Media ID tidak boleh kosong")

#         for data in socmed:
#             url = data.url_video
#             search_path = f"{url}{quote(media_id)}"
#             socmed_url.append({
#                 "search": search_path,
#                 "host": data.api_host,
#                 "api_key": data.api_key
#             })

#         result_list = []

#         with httpx.Client() as client:
#             for data in socmed_url:
#                 api_key = data['api_key']
#                 api_host = data['host']
#                 search_path = data['search']

#                 url = f"https://{api_host}{search_path}"
#                 headers = {
#                     'x-rapidapi-key': f'{api_key}',
#                     'x-rapidapi-host': f'{api_host}'
#                 }

#                 print('url', url)

#                 response = client.get(url, headers=headers, timeout=None)
#                 data = response.json()
#                 item = {
#                     'host': api_host,
#                     search_path: data
#                 }
#                 result_list.append(item)
#         return {"status": "success", "data": result_list}
#     except httpx.HTTPStatusError as http_err:
#         raise HTTPException(status_code=http_err.response.status_code, detail=str(http_err))
#     except httpx.RequestError as req_err:
#         raise HTTPException(status_code=500, detail=str(req_err))
