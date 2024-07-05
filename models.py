from sqlalchemy import Column, Integer, String, TIMESTAMP, text, DefaultClause, Text
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.sql import func

Base = declarative_base()

class News(Base):
    __tablename__ = "news"

    id = Column(Integer, primary_key=True, nullable=False)
    title = Column(String, nullable=False)
    url_source = Column(Text, nullable=False)
    content = Column(Text, nullable=False)
    published_time = Column(TIMESTAMP(timezone=True), default=func.now())
    image = Column(Text, nullable=True)

class Crawler(Base):
    __tablename__ = "crawler"

    id = Column(Integer, primary_key=True, nullable=False)
    code = Column(String, nullable=False)
    title = Column(String, nullable=False)
    url_latest = Column(Text, nullable=False)
    url_search = Column(Text, nullable=False)
    url_popular = Column(Text, nullable=False)
    api = Column(Text, nullable=False)
    api_key = Column(Text, nullable=False)

class CrawlerSocmed(Base):
    __tablename__ = "crawler_socmed"

    id = Column(Integer, primary_key=True, nullable=False)
    code = Column(String, nullable=False)
    title = Column(String, nullable=False)
    url_search = Column(Text, nullable=False)
    url_comment = Column(Text, nullable=False)
    url_hashtag = Column(Text, nullable=False)
    url_video = Column(Text, nullable=False)
    api_host = Column(Text, nullable=False)
    api_key = Column(Text, nullable=False)