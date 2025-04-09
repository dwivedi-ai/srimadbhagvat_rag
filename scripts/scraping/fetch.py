import requests
from bs4 import BeautifulSoup
import time
import os
import json
from urllib.parse import urlparse, urljoin, urlunparse
import traceback

START_URL = 'https://vedabase.io/en/library/sb/1/1/advanced-view/'
OUTPUT_FILENAME = 'vedabase_sb.jsonl'
OUTPUT_DIR = '../../data/scraped_sb'

CONTENT_AREA_SELECTOR = 'main'
VERSE_TEXT_SELECTOR = 'div.av-verse_text'
TRANSLATION_SELECTOR = 'div.av-translation'
PURPORT_SELECTOR = 'div.av-purport'
CANTO_INDEX_CHAPTER_LINK_SELECTOR = 'main div[id^="bb"] a[href*="/sb/"]'
CHAPTER_INDEX_VERSE_LINK_SELECTOR = 'main div.r-verse-text a[href*="/sb/"]'
NEXT_ARROW_SVG_PATH_D = "M190.5 66.9l22.2-22.2c9.4-9.4 24.6-9.4 33.9 0L441 239c9.4 9.4 9.4 24.6 0 33.9L246.6 467.3c-9.4 9.4-24.6 9.4-33.9 0l-22.2-22.2c-9.5-9.5-9.3-25 .4-34.3L311.4 296H24c-13.3 0-24-10.7-24-24v-32c0-13.3 10.7-24 24-24h287.4L190.9 101.2c-9.8-9.3-10-24.8-.4-34.3z"
NAVIGATION_LINKS_SELECTOR = 'main > nav a[href], main > div > a[href]'
HEADERS = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'}

def ensure_advanced_view_url(url):
    if not url:
        return None
    try:
        parsed = urlparse(url)
        if 'vedabase.io' not in parsed.netloc or '/library/' not in parsed.path:
             return url
        path = parsed.path.rstrip('/')
        if not path.endswith('/advanced-view'):
            path_parts = [part for part in path.strip('/').split('/') if part]
            is_sb_verse = len(path_parts) >= 6 and path_parts[2] == 'sb'
            is_bg_verse = len(path_parts) >= 5 and path_parts[2] == 'bg'
            is_sb_chapter_index = len(path_parts) == 5 and path_parts[2] == 'sb'
            is_sb_canto_index = len(path_parts) == 4 and path_parts[2] == 'sb'
            if is_sb_verse or is_bg_verse or is_sb_chapter_index or is_sb_canto_index :
                new_path = path + '/advanced-view/'
                new_url_parts = list(parsed)
                new_url_parts[2] = new_path
                return urlunparse(new_url_parts)
            else:
                return url
        else:
            new_url_parts = list(parsed)
            new_url_parts[2] = path + '/'
            return urlunparse(new_url_parts)
    except Exception as e:
         return url

def parse_url_details(url):
    details = {
        'book': None, 'canto': None, 'chapter': None, 'verse': None, 'reference': None,
        'page_type': 'Unknown', 'url': url
    }
    try:
        parsed_url = urlparse(url)
        path = parsed_url.path.replace('/advanced-view', '').rstrip('/')
        path_parts = [part for part in path.strip('/').split('/') if part]
        if len(path_parts) >= 3 and path_parts[0] == 'en' and path_parts[1] == 'library':
            details['book'] = path_parts[2].lower()
            if details['book'] == 'bg':
                if len(path_parts) == 4 and path_parts[3] == 'introduction':
                    details['page_type'] = 'Introduction'; details['reference'] = 'BG Introduction'
                elif len(path_parts) == 4:
                    details['chapter'] = path_parts[3]; details['page_type'] = 'Chapter Index'; details['reference'] = f"BG {details['chapter']}"
                elif len(path_parts) >= 5:
                    details['chapter'] = path_parts[3]; details['verse'] = path_parts[4]; details['page_type'] = 'Verse Page'; details['reference'] = f"BG {details['chapter']}.{details['verse']}"
                else: details['page_type'] = 'BG Other'
            elif details['book'] == 'sb':
                 if len(path_parts) == 3:
                     details['page_type'] = 'Book Index'
                     details['reference'] = 'SB Index'
                 elif len(path_parts) == 4:
                      details['canto'] = path_parts[3]; details['page_type'] = 'Canto Index'; details['reference'] = f"SB {details['canto']}"
                 elif len(path_parts) == 5:
                      details['canto'] = path_parts[3]; details['chapter'] = path_parts[4]; details['page_type'] = 'Chapter Index'; details['reference'] = f"SB {details['canto']}.{details['chapter']}"
                 elif len(path_parts) >= 6:
                      details['canto'] = path_parts[3]; details['chapter'] = path_parts[4]; details['verse'] = path_parts[5]; details['page_type'] = 'Verse Page'; details['reference'] = f"SB {details['canto']}.{details['chapter']}.{details['verse']}"
                 else: details['page_type'] = 'SB Other'
            else: details['page_type'] = 'Book Index or Unknown Book'
        else: details['page_type'] = 'Non-Library Path'
    except Exception as e: pass
    return details

def find_next_page_link_on_verse(soup, current_url):
    next_page_url = None
    try:
        possible_nav_containers = soup.select('main > nav, main > div')
        nav_links = []
        for container in possible_nav_containers: nav_links.extend(container.select('a[href]'))
        if not nav_links:
            main_content = soup.select_one('main')
            if main_content: nav_links = main_content.select('a[href]')
        for link in nav_links:
            svg = link.find('svg'); path = svg.find('path') if svg else None
            if path:
                svg_path_d = ' '.join(path.get('d', '').split())
                target_path_d = ' '.join(NEXT_ARROW_SVG_PATH_D.split())
                if svg_path_d == target_path_d:
                    href = link.get('href')
                    if href: next_page_url = urljoin(current_url, href); return next_page_url
    except Exception as e: pass
    if not next_page_url:
        possible_titles = ["Next verse", "Next chapter", "Next"]
        for title in possible_titles:
            next_link_element = soup.select_one(f'a[title="{title}"]')
            if next_link_element and next_link_element.has_attr('href'):
                href = next_link_element['href']
                next_page_url = urljoin(current_url, href)
                return next_page_url
    return next_page_url

def find_first_verse_link_on_chapter_index(soup, base_url):
    try:
        verse_links = soup.select(CHAPTER_INDEX_VERSE_LINK_SELECTOR)
        for link in verse_links:
            href = link.get('href')
            parsed_link = urlparse(urljoin(base_url, href))
            link_path = parsed_link.path.rstrip('/')
            if href and link_path.endswith('/1'):
                first_verse_url = urljoin(base_url, href)
                return first_verse_url
        parsed_base = urlparse(base_url)
        base_path = parsed_base.path.replace('/advanced-view', '').rstrip('/')
        path_parts = [p for p in base_path.strip('/').split('/') if p]
        if len(path_parts) == 5 and path_parts[1] == 'library' and path_parts[2] == 'sb':
            first_verse_path = base_path + '/1/'
            constructed_url = urljoin(base_url, first_verse_path)
            return constructed_url
    except Exception as e: pass
    return None

def find_first_chapter_link_on_canto_index(soup, base_url):
    try:
        chapter_links = soup.select(CANTO_INDEX_CHAPTER_LINK_SELECTOR)
        for link in chapter_links:
            href = link.get('href')
            parsed_link = urlparse(urljoin(base_url, href))
            link_path = parsed_link.path.rstrip('/')
            path_parts = [p for p in link_path.strip('/').split('/') if p]
            if href and len(path_parts) == 5 and path_parts[-1] == '1':
                first_chapter_url = urljoin(base_url, href)
                return first_chapter_url
        parsed_base = urlparse(base_url)
        base_path = parsed_base.path.replace('/advanced-view', '').rstrip('/')
        path_parts = [p for p in base_path.strip('/').split('/') if p]
        if len(path_parts) == 4 and path_parts[1] == 'library' and path_parts[2] == 'sb':
            first_chapter_path = base_path + '/1/'
            constructed_url = urljoin(base_url, first_chapter_path)
            return constructed_url
    except Exception as e: pass
    return None

def find_first_canto_link_on_book_index(soup, base_url):
    try:
        canto_links = soup.select(CANTO_INDEX_CHAPTER_LINK_SELECTOR)
        for link in canto_links:
            href = link.get('href')
            parsed_link = urlparse(urljoin(base_url, href))
            link_path = parsed_link.path.rstrip('/')
            path_parts = [p for p in link_path.strip('/').split('/') if p]
            if href and len(path_parts) == 4 and path_parts[-1] == '1':
                first_canto_url = urljoin(base_url, href)
                return first_canto_url
        parsed_base = urlparse(base_url)
        base_path = parsed_base.path.replace('/advanced-view', '').rstrip('/')
        path_parts = [p for p in base_path.strip('/').split('/') if p]
        if len(path_parts) == 3 and path_parts[1] == 'library' and path_parts[2] == 'sb':
            first_canto_path = base_path + '/1/'
            constructed_url = urljoin(base_url, first_canto_path)
            return constructed_url
    except Exception as e: pass
    return None

def scrape_and_process_page(url):
    fetch_url = ensure_advanced_view_url(url)
    if not fetch_url: return None, None
    page_data = parse_url_details(fetch_url)
    page_data['sanskrit_text'] = None
    page_data['translation_text'] = None
    page_data['explanation_text'] = None
    next_url_to_fetch = None
    try:
        time.sleep(1.5)
        response = requests.get(fetch_url, headers=HEADERS, timeout=25)
        response.raise_for_status()
        soup = BeautifulSoup(response.content, 'html.parser')
        main_content = soup.select_one(CONTENT_AREA_SELECTOR)
        if main_content:
            verse_text_div = main_content.select_one(VERSE_TEXT_SELECTOR)
            translation_div = main_content.select_one(TRANSLATION_SELECTOR)
            purport_div = main_content.select_one(PURPORT_SELECTOR)
            if verse_text_div: page_data['sanskrit_text'] = verse_text_div.get_text(separator='\n', strip=True)
            if translation_div: page_data['translation_text'] = translation_div.get_text(separator='\n', strip=True)
            if purport_div: page_data['explanation_text'] = purport_div.get_text(separator='\n', strip=True)
            current_page_type = page_data.get('page_type')
            raw_next_url = None
            if current_page_type == 'Verse Page':
                raw_next_url = find_next_page_link_on_verse(soup, fetch_url)
            elif current_page_type == 'Chapter Index':
                raw_next_url = find_first_verse_link_on_chapter_index(soup, fetch_url)
            elif current_page_type == 'Canto Index':
                raw_next_url = find_first_chapter_link_on_canto_index(soup, fetch_url)
            elif current_page_type == 'Book Index':
                raw_next_url = find_first_canto_link_on_book_index(soup, fetch_url)
            else:
                raw_next_url = find_next_page_link_on_verse(soup, fetch_url)
            if raw_next_url:
                next_url_to_fetch = ensure_advanced_view_url(raw_next_url)
    except requests.exceptions.RequestException as e: pass
    except Exception as e: pass
    return page_data, next_url_to_fetch

if __name__ == "__main__":
    parsed_start_url = urlparse(START_URL)
    robots_url = f"{parsed_start_url.scheme}://{parsed_start_url.netloc}/robots.txt"
    if not os.path.exists(OUTPUT_DIR):
        try: os.makedirs(OUTPUT_DIR)
        except OSError as e: exit()
    output_filepath = os.path.join(OUTPUT_DIR, OUTPUT_FILENAME)
    processed_urls = set()
    current_url = START_URL
    page_count = 0
    error_count = 0
    max_pages = 18500
    max_errors = 20
    try:
        with open(output_filepath, 'a', encoding='utf-8') as f:
            while current_url and page_count < max_pages and error_count < max_errors:
                if current_url in processed_urls:
                    break
                processed_urls.add(current_url)
                page_count += 1
                page_data, next_url = scrape_and_process_page(current_url)
                save_this_page = False
                if isinstance(page_data, dict):
                    page_type = page_data.get('page_type')
                    if page_type == 'Verse Page':
                        if page_data.get('translation_text') or page_data.get('explanation_text'):
                            save_this_page = True
                    elif page_type in ['Chapter Index', 'Canto Index', 'Book Index', 'Introduction']:
                        save_this_page = True
                        page_data.pop('sanskrit_text', None)
                        page_data.pop('translation_text', None)
                        page_data.pop('explanation_text', None)
                    else:
                        save_this_page = True
                if save_this_page:
                    try:
                        json_record = json.dumps(page_data, ensure_ascii=False)
                        f.write(json_record + '\n')
                        error_count = 0
                    except Exception as e:
                        error_count += 1
                elif not page_data:
                    error_count += 1
                if not next_url: break
                if next_url == current_url: break
                if error_count >= max_errors: break
                current_url = next_url
    except IOError as e: exit()
    except KeyboardInterrupt: pass