from pydantic import BaseModel

class NewsCreate(BaseModel):
    title: str
    url_source: str
    content: str
    image: str

class CrawlerCreate(BaseModel):
    code: str
    title: str
    url_latest: str
    url_search: str
    url_popular: str
    api: str
    api_key: str

class CrawlerSocmedCreate(BaseModel):
    code: str
    title: str
    url_search: str
    url_comment: str
    url_hashtag: str
    url_video: str
    api_host: str
    api_key: str
