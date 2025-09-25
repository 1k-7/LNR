import requests
from bs4 import BeautifulSoup
from typing import List
from urllib.parse import urljoin

class WebToEpubParser:
    def __init__(self, novel_url):
        self.novel_url = novel_url
        self.dom = None
        self.chapters = []
        self.novel_title = ""
        self.novel_author = ""
        self.novel_cover = ""

    def absolute_url(self, url):
        return urljoin(self.novel_url, url)

    def fetch_dom(self, url):
        response = requests.get(url)
        response.raise_for_status()
        return BeautifulSoup(response.content, "lxml")

    def get_chapter_urls(self, dom) -> List[dict]:
        raise NotImplementedError()

    def find_content(self, dom) -> str:
        raise NotImplementedError()

    def read_novel_info(self):
        self.dom = self.fetch_dom(self.novel_url)
        self.novel_title = self.extract_title(self.dom)
        self.novel_author = self.extract_author(self.dom)
        self.novel_cover = self.find_cover_image_url(self.dom)

        chapters_data = self.get_chapter_urls(self.dom)
        for i, chapter_data in enumerate(chapters_data):
            self.chapters.append({
                "id": i + 1,
                "title": chapter_data['title'],
                "url": chapter_data['url'],
            })

    def download_chapter_body(self, chapter_url: str) -> str:
        dom = self.fetch_dom(chapter_url)
        content = self.find_content(dom)
        return str(content)

    def extract_title(self, dom):
        title_tag = dom.select_one("meta[property='og:title']")
        return title_tag['content'] if title_tag else dom.title.string

    def extract_author(self, dom):
        return "<unknown>"

    def find_cover_image_url(self, dom):
        cover_tag = dom.select_one("meta[property='og:image']")
        return cover_tag['content'] if cover_tag else None