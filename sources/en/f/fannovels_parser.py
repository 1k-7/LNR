# Parser for FanNovel.com, FanNovels.com, and similar sites.
# These sites use an AJAX call to load the chapter list.
import re
from lncrawl.parser import WebToEpubParser

class FanNovelsParser(WebToEpubParser):
    base_url = [
        "https://fannovels.com/",
        "https://fannovel.net/",
        "https://www.fannovel.com/",
    ]

    def get_chapter_urls(self, dom):
        """
        This is the key part for this group of sites.
        1. Find the unique novel ID from a hidden input field.
        2. Use that ID to make a request to the site's internal API.
        3. Parse the HTML response from the API to get the chapter list.
        """
        chapter_list = []
        
        # 1. Find the novel ID
        novel_id_input = dom.select_one('input#novelId')
        if not novel_id_input or not novel_id_input.has_attr('value'):
            print("WARNING: Could not find novel ID. Cannot fetch chapter list.")
            return []
        
        novel_id = novel_id_input['value']
        
        # 2. Make the API request
        # The endpoint is usually '/ajax/chapter-archive?novelId=...'
        ajax_url = self.absolute_url(f'/ajax/chapter-archive?novelId={novel_id}')
        
        try:
            print(f"Fetching chapter list from API: {ajax_url}")
            chapter_dom = self.fetch_dom(ajax_url)
        except Exception as e:
            print(f"ERROR: Failed to fetch chapter list from API. {e}")
            return []

        # 3. Parse the chapter list from the API response
        for a in chapter_dom.select('ul.list-chapter li a'):
            chapter_list.append({
                'title': a.text.strip(),
                'url': self.absolute_url(a['href'])
            })
            
        return chapter_list

    def find_content(self, dom):
        selector = '#chapter-content'
        content = dom.select_one(selector)
        # Remove unwanted elements like ads or social sharing buttons
        for ad_element in content.select('.ads-holder, .cha-note'):
            ad_element.decompose()
        return content

    def extract_title(self, dom):
        selector = 'h3.title'
        if selector:
            title_tag = dom.select_one(selector)
            if title_tag:
                return title_tag.text.strip()
        return super().extract_title(dom)

    def extract_author(self, dom):
        selector = 'div.info a[href*="/author/"]'
        if selector:
            author_tag = dom.select_one(selector)
            if author_tag:
                return author_tag.text.strip()
        return super().extract_author(dom)

    def find_cover_image_url(self, dom):
        selector = 'div.book img'
        if selector:
            cover_tag = dom.select_one(selector)
            if cover_tag and cover_tag.has_attr('src'):
                return self.absolute_url(cover_tag['src'])
        return super().find_cover_image_url(dom)
