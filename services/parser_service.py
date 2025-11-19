from asyncio.log import logger
from typing import Dict, List, Optional
from urllib.parse import urljoin
import re

import aiohttp
from bs4 import BeautifulSoup



class ParserService:
    
    @staticmethod
    async def get_listings(url: str, site_type: str = 'olx', filter_text: Optional[str] = None) -> List[str]:
        if site_type == 'olx':
            return await ParserService._get_olx_listings(url)
        elif site_type == 'avtoelon':
            return await ParserService._get_avtoelon_listings(url, filter_text)
        return []
    
    @staticmethod
    async def _get_olx_listings(url: str) -> List[str]:
        try:
            async with aiohttp.ClientSession() as session:
                headers = {
                    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
                    'Accept-Language': 'ru-RU,ru;q=0.9,en;q=0.8'
                }
                async with session.get(url, headers=headers, timeout=30) as response:
                    if response.status != 200:
                        return []
                    
                    html = await response.text()
                    soup = BeautifulSoup(html, 'html.parser')
                    
                    hrefs = []
                    
                    listing_grid = soup.find('div', {'data-testid': 'listing-grid'})
                    
                    if not listing_grid:
                        return []
                    
                    promoted_div = soup.find('div', id='div-gpt-liting-after-promoted')
                    
                    if promoted_div:
                        next_elements = promoted_div.find_all_next('div', {'data-cy': 'l-card', 'data-testid': 'l-card'})
                        
                        for card in next_elements:
                            if listing_grid in card.parents:
                                promoted_indicator = card.find(string=re.compile(r'ТОП|TOP', re.I))
                                if promoted_indicator:
                                    continue
                                
                                try:
                                    a_tag = card.find('a', href=True)
                                    if a_tag:
                                        href = a_tag['href']
                                        if href.startswith('/d/obyavlenie/') or '/ID' in href:
                                            if href not in hrefs:
                                                hrefs.append(href)
                                except Exception as e:
                                    continue
                        
                    else:
                        all_cards = listing_grid.find_all('div', {'data-cy': 'l-card', 'data-testid': 'l-card'})
                        
                        for card in all_cards:
                            promoted_indicator = card.find(string=re.compile(r'ТОП|TOP', re.I))
                            if promoted_indicator:
                                continue
                            
                            try:
                                a_tag = card.find('a', href=True)
                                if a_tag:
                                    href = a_tag['href']
                                    if href.startswith('/d/obyavlenie/') or '/ID' in href:
                                        if href not in hrefs:
                                            hrefs.append(href)
                            except Exception as e:
                                continue
                    
                    return hrefs
        except Exception as e:
            return []
    
    @staticmethod
    async def _get_avtoelon_listings(url: str, filter_text: Optional[str]) -> List[str]:
        try:
            async with aiohttp.ClientSession() as session:
                headers = {
                    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
                    'Accept-Language': 'ru-RU,ru;q=0.9,en;q=0.8'
                }
                async with session.get(url, headers=headers, timeout=30) as response:
                    if response.status != 200:
                        return []
                    
                    html = await response.text()
                    soup = BeautifulSoup(html, 'html.parser')
                    
                    hrefs = []
                    
                    result_block = soup.find('div', class_='result-block col-sm-8')
                    if not result_block:
                        return []
                    
                    items = result_block.find_all('div', class_='row list-item a-elem')
                    
                    for item in items:
                        try:
                            button = item.find('button', class_='list-link js__advert-button')
                            if not button:
                                continue
                            
                            payment_corner = button.find('div', class_='payment-package-corner')
                            if payment_corner:
                                badge = payment_corner.find('span', class_=re.compile(r'payment-package-corner__badge--'))
                                if badge:
                                    badge_classes = badge.get('class', [])
                                    promo_badges = [
                                        'payment-package-corner__badge--vip-sale',
                                        'payment-package-corner__badge--zor-sale',
                                        'payment-package-corner__badge--alo-sale'
                                    ]
                                    if any(promo_class in badge_classes for promo_class in promo_badges):
                                        continue
                            
                            title_a = item.find('a', class_='js__advert-link')
                            if title_a:
                                title_text = title_a.get_text(strip=True).lower()
                                if filter_text and filter_text.lower() in title_text:
                                    continue
                                
                                href = title_a['href']
                                if href.startswith('/a/show/') and href not in hrefs:
                                    hrefs.append(href)
                        except Exception as e:
                            continue
                    return hrefs
        except Exception as e:
            return []
    
    @staticmethod
    async def get_ad_details(href: str, site_type: str = 'olx') -> Optional[Dict]:
        if site_type == 'olx':
            return await ParserService._get_olx_ad_details(href)
        elif site_type == 'avtoelon':
            return await ParserService._get_avtoelon_ad_details(href)
        return None
    
    @staticmethod
    async def _get_olx_ad_details(href: str) -> Optional[Dict]:
        try:
            full_url = urljoin('https://www.olx.uz', href)
            async with aiohttp.ClientSession() as session:
                headers = {
                    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
                    'Accept-Language': 'ru-RU,ru;q=0.9,en;q=0.8'
                }
                async with session.get(full_url, headers=headers, timeout=30) as response:
                    if response.status != 200:
                        return None
                    
                    html = await response.text()
                    soup = BeautifulSoup(html, 'html.parser')
                    
                    details = {'url': full_url, 'href': href}
                    
                    aside_div = soup.find('div', {'data-testid': 'aside', 'class': 'css-6u8zs6'})
                    
                    if aside_div:
                        title_h4 = aside_div.find('h4', class_='css-1au435n')
                        if title_h4:
                            details['title'] = title_h4.get_text(strip=True)
                        else:
                            title_div = aside_div.find('div', {'data-cy': 'offer_title'})
                            if title_div:
                                title_h4 = title_div.find('h4')
                                if title_h4:
                                    details['title'] = title_h4.get_text(strip=True)
                        
                        prices_wrapper = aside_div.find('div', {'data-testid': 'prices-wrapper'})
                        if prices_wrapper:
                            price_container = prices_wrapper.find('div', {'data-testid': 'ad-price-container'})
                            if price_container:
                                price_h3 = price_container.find('h3')
                                if price_h3:
                                    details['price'] = price_h3.get_text(strip=True)
                        
                        if 'price' not in details:
                            price_h3 = aside_div.find('h3', class_='css-yauxmy')
                            if price_h3:
                                details['price'] = price_h3.get_text(strip=True)
                        
                        if 'price' not in details:
                            price_h3 = aside_div.find('h3', class_='css-90xrc0')
                            if price_h3:
                                details['price'] = price_h3.get_text(strip=True)
                        
                        seller_card = aside_div.find('div', {'data-cy': 'seller_card', 'data-testid': 'seller_card'})
                        if seller_card:
                            user_name = seller_card.find('h4', {'data-testid': 'user-profile-user-name'})
                            if user_name:
                                details['seller_name'] = user_name.get_text(strip=True)
                        
                        map_section = aside_div.find('div', {'data-testid': 'map-aside-section'})
                        if map_section:
                            print(map_section)
                            logger.info("Map section topildi")
                            location_found = False
                            
                            location_p = map_section.find('p', class_='css-9pna1a')
                            region_p = map_section.find('p', class_='css-3cz5o2')
                            
                            logger.info(f"location_p: {location_p}")
                            logger.info(f"region_p: {region_p}")
                            
                            if location_p or region_p:
                                location_parts = []
                                if location_p:
                                    loc_text = location_p.get_text(strip=True)
                                    if loc_text:
                                        location_parts.append(loc_text)
                                        logger.info(f"Location text: {loc_text}")
                                if region_p:
                                    reg_text = region_p.get_text(strip=True)
                                    if reg_text:
                                        location_parts.append(reg_text)
                                        logger.info(f"Region text: {reg_text}")
                                
                                if location_parts:
                                    details['location'] = ', '.join(location_parts)
                                    location_found = True
                                    logger.info(f"Location (usul 1): {details['location']}")
                            
                            if not location_found:
                                map_img = map_section.find('img', alt=True)
                                logger.info(f"Map img: {map_img}")
                                if map_img and map_img.get('alt'):
                                    alt_text = map_img['alt'].strip()
                                    logger.info(f"Alt text: {alt_text}")
                                    if alt_text and alt_text not in ['', 'map', 'static map']:
                                        details['location'] = alt_text
                                        location_found = True
                                        logger.info(f"Location (usul 2): {details['location']}")
                            
                            if not location_found:
                                all_p_tags = map_section.find_all('p')
                                logger.info(f"Barcha <p> teglar soni: {len(all_p_tags)}")
                                location_parts = []
                                for p in all_p_tags:
                                    text = p.get_text(strip=True)
                                    logger.info(f"P text: {text}")
                                    print(text)
                                    if text and text not in ['Местоположение', 'Location']:
                                        location_parts.append(text)
                                
                                if location_parts:
                                    details['location'] = ', '.join(location_parts)
                                    location_found = True
                                    logger.info(f"Location (usul 3): {details['location']}")
                        else:
                            logger.warning("Map section topilmadi!")

                        if 'location' not in details or not details['location']:
                            logger.info("Location topilmadi, parametrlardan izlanmoqda")
                            params = details.get('params', {})
                            if 'Город' in params:
                                details['location'] = params['Город']
                                logger.info(f"Location (params): {details['location']}")
                            elif 'Местоположение' in params:
                                details['location'] = params['Местоположение']
                                logger.info(f"Location (params): {details['location']}")
                        
                        posted_wrapper = aside_div.find('div', class_='css-12kclhg')
                        if posted_wrapper:
                            outer_span = posted_wrapper.find('span', class_='css-1br3d2a')
                            if outer_span:
                                posted_date = outer_span.find('span', {'data-cy': 'ad-posted-at', 'data-testid': 'ad-posted-at'})
                                if posted_date:
                                    details['posted_time'] = posted_date.get_text(strip=True)
                                else:
                                    details['posted_time'] = outer_span.get_text(strip=True).replace('Опубликовано ', '').strip()
                            else:
                                posted_date = posted_wrapper.find('span', {'data-cy': 'ad-posted-at'})
                                if posted_date:
                                    details['posted_time'] = posted_date.get_text(strip=True)
                        else:
                            posted_date = soup.find('span', {'data-cy': 'ad-posted-at', 'data-testid': 'ad-posted-at'})
                            if posted_date:
                                details['posted_time'] = posted_date.get_text(strip=True)
                    else:
                        title = soup.find('h1', class_='css-1kc83jo')
                        if not title:
                            title = soup.find('h4', class_='css-1kc83jo')
                        if title:
                            details['title'] = title.get_text(strip=True)
                        
                        price = soup.find('h3', class_='css-90xrc0')
                        if price:
                            details['price'] = price.get_text(strip=True)
                    
                    images = []
                    
                    gallery = soup.find('div', class_='css-1uilkl7')
                    if gallery:
                        img_tags = gallery.find_all('img', src=True)
                        for img in img_tags[:10]:
                            src = img.get('src', '')
                            if 'apollo.olxcdn.com' in src:
                                if 's=' in src:
                                    src = re.sub(r's=\d+x\d+', 's=1280x1024', src)
                                images.append(src)
                    
                    if not images:
                        all_imgs = soup.find_all('img', src=True)
                        for img in all_imgs:
                            src = img.get('src', '')
                            if 'apollo.olxcdn.com' in src and 'static' not in src:
                                if 's=' in src:
                                    src = re.sub(r's=\d+x\d+', 's=1280x1024', src)
                                if src not in images:
                                    images.append(src)
                    
                    if not images:
                        data_src_imgs = soup.find_all('img', attrs={'data-src': True})
                        for img in data_src_imgs:
                            src = img.get('data-src', '')
                            if 'apollo.olxcdn.com' in src:
                                if 's=' in src:
                                    src = re.sub(r's=\d+x\d+', 's=1280x1024', src)
                                if src not in images:
                                    images.append(src)
                    
                    if images:
                        details['images'] = images[:10]

                    params_div = soup.find('div', {'data-testid': 'ad-parameters-container'})
                    if params_div:
                        params = {}
                        for p in params_div.find_all('p', class_='css-13x8d99'):
                            text = p.get_text(strip=True)
                            if ':' in text:
                                key, value = text.split(':', 1)
                                params[key.strip()] = value.strip()
                        details['params'] = params
                    
                    phone_link = soup.find('a', href=re.compile(r'tel:'))
                    if phone_link:
                        phone = phone_link['href'].replace('tel:', '').strip()
                        details['phone'] = phone
                    else:
                        phone_button = soup.find('button', {'data-testid': 'ad-contact-phone'})
                        if phone_button:
                            phone_text = phone_button.get_text(strip=True)
                            if phone_text and phone_text != 'Показать телефон':
                                details['phone'] = phone_text
                        else:
                            phone_pattern = re.compile(r'\+?\d{1,3}[\s-]?\(?\d{2,3}\)?[\s-]?\d{3}[\s-]?\d{2}[\s-]?\d{2}')
                            phone_matches = phone_pattern.findall(html)
                            if phone_matches:
                                details['phone'] = phone_matches[0]
                    
                    desc_div = soup.find('div', {'data-cy': 'ad_description'})
                    if desc_div:
                        desc_content = desc_div.find('div', class_='css-19duwlz')
                        if desc_content:
                            details['description'] = desc_content.get_text()
                    
                    return details
        except Exception as e:
            return None
    
    @staticmethod
    async def _get_avtoelon_ad_details(href: str) -> Optional[Dict]:
        try:
            full_url = urljoin('https://avtoelon.uz', href)
            async with aiohttp.ClientSession() as session:
                headers = {
                    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
                    'Accept-Language': 'ru-RU,ru;q=0.9,en;q=0.8'
                }
                async with session.get(full_url, headers=headers, timeout=30) as response:
                    if response.status != 200:
                        return None
                    
                    html = await response.text()
                    soup = BeautifulSoup(html, 'html.parser')
                    
                    details = {'url': full_url, 'href': href}
                    
                    product_div = soup.find('div', {'itemscope': '', 'itemtype': 'http://schema.org/Product'})
                    if not product_div:
                        product_div = soup.find('div', class_='item product')
                    
                    if product_div:
                        title_elem = product_div.find('h1', class_='a-title__text') or product_div.find('h1')
                        if title_elem:
                            title_text = title_elem.get_text()
                            title_text = re.sub(r'\s+', ' ', title_text)
                            details['title'] = title_text
                        
                        price_span = product_div.find('span', class_='a-price__text') or product_div.find('div', class_='a-price')
                        if price_span:
                            details['price'] = price_span.get_text(strip=True)
                        
                        posted_div = soup.find('div', class_='f-line')
                        if posted_div:
                            posted_col = posted_div.find('div', class_='col-sm-4')
                            if posted_col:
                                posted_text = posted_col.get_text(strip=True)
                                if 'Опубликовано' in posted_text:
                                    details['posted_time'] = posted_text
                        
                        params = {}
                        dl_params = product_div.find('dl', class_='description-params') or product_div.find('dl', class_='clearfix dl-horizontal description-params')
                        if dl_params:
                            dts = dl_params.find_all('dt')
                            dds = dl_params.find_all('dd')
                            for dt, dd in zip(dts[:len(dds)], dds):
                                key = dt.get_text(strip=True)
                                value = dd.get_text(strip=True)
                                params[key] = value
                        
                        params_block = product_div.find('ul', class_='params-block__list')
                        if params_block:
                            for li in params_block.find_all('li', class_='params-block__list-item'):
                                heading_h4 = li.find('h4', class_='item__heading')
                                if heading_h4:
                                    heading = heading_h4.get_text(strip=True)
                                    span = li.find('span')
                                    if span:
                                        span_text = span.get_text(strip=True)
                                        params[heading] = span_text
                        
                        details['params'] = params
                        
                        desc_div = product_div.find('div', class_='description-text')
                        if desc_div:
                            details['description'] = desc_div.get_text()
                        
                        simple_phone_pattern = re.compile(r'\+?998\s*\d{2}\s*\d{3}\s*\d{2}\s*\d{2}')
                        phone_match = simple_phone_pattern.search(html)
                        if phone_match:
                            details['phone'] = re.sub(r'\s+', ' ', phone_match.group(0)).strip()
                        
                        if 'Город' in params:
                            details['location'] = params['Город']

                        images = []
                        main_div = product_div.find('div', class_='main-photo')
                        if main_div:
                            main_a = main_div.find('a')
                            if main_a and main_a.get('href'):
                                images.append(main_a['href'])
                            else:
                                img = main_div.find('img')
                                if img and img.get('src'):
                                    src = img['src']
                                    src = re.sub(r'-408x306\.webp', '-full.webp', src)
                                    images.append(src)
                        
                        photo_links = product_div.find_all('a', class_='small-thumb')
                        for a in photo_links:
                            href_attr = a.get('href', '')
                            if href_attr and '-full.webp' in href_attr:
                                images.append(href_attr)
                        
                        details['images'] = list(set(images))[:10]
                    
                    return details
        except Exception as e:
            return None
    
    @staticmethod
    def format_message(details: Dict, site_type: str = 'olx') -> str:
        title = details.get('title', 'Yangi e\'lon')
        url = details.get('url', '')
        
        msg = f"🚗 <a href='{url}'><b>{title}</b></a>\n\n"
        
        if 'price' in details:
            msg += f"💰 <b>{details['price']}</b>\n\n"
        
        params = details.get('params', {})
        
        if site_type == 'avtoelon':
            year = params.get('Год выпуска', params.get('Год', ''))
            location = details.get('location', params.get('Город', ''))
            
            msg += "📋 <b>Ma'lumotlar:</b>\n"

            if year:
                msg += f"▫️ Yili: {year}\n"
            
            important_keys = [
                'Объем двигателя, л', 'Объем двигателя', 'Пробег', 
                'Коробка передач', 'Цвет', 'Состояние краски'
            ]
            
            for key in important_keys:
                if key in params:
                    uz_key = {
                        'Объем двигателя, л': 'Hajm',
                        'Объем двигателя': 'Hajm',
                        'Пробег': 'Probeg',
                        'Коробка передач': 'Korobka',
                        'Цвет': 'Rangi',
                        'Состояние краски': 'Kraska holati'
                    }.get(key, key)
                    value = params[key].replace('\n', ' ').strip()
                    msg += f"▫️ {uz_key}: {value}\n"

            if location:
                msg += f"\n📍 <b>Manzil:</b> {location}\n"
            
            msg += "\n"
        
        else:
            year = params.get('Год выпуска', params.get('Год', ''))
            location = details.get('location', params.get('Город', ''))
            
            
            
            if params:
                important_keys = [
                    'Объем двигателя, л', 'Объем двигателя', 'Пробег', 
                    'Коробка передач', 'Цвет', 'Вид топлива', 'Кузов', 
                    'Состояние краски', 'Привод'
                ]
                
                has_other_params = any(key in params for key in important_keys)
                
                if has_other_params:
                    msg += "📋 <b>Ma'lumotlar:</b>\n"
                    if year:
                        msg += f"▫️ <b>Yili:</b> {year}\n"
                    
                    for key in important_keys:
                        if key in params:
                            uz_key = {
                                'Объем двигателя, л': 'Hajm',
                                'Объем двигателя': 'Hajm',
                                'Пробег': 'Probeg',
                                'Коробка передач': 'Korobka',
                                'Цвет': 'Rangi',
                                'Состояние краски': 'Kraska holati',
                            }.get(key, key)
                            value = params[key].replace('\n', ' ').strip()
                            msg += f"▫️ {uz_key}: {value}\n"

                    
                    msg += "\n"

        
        if 'description' in details:
            desc = details['description']
            if len(desc) > 500:
                desc = desc[:497] + '...'
            msg += f"📝 {desc}\n\n"

        msg += f"🔗 <a href='{url}'>E'lonni to'liq ko'rish</a>"
        
        return msg