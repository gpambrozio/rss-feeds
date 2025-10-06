#!/usr/bin/env python3
"""
RSS Feed Generator for Surge AI Blog
Scrapes https://www.surgehq.ai/blog and generates an RSS feed
"""

import requests
from bs4 import BeautifulSoup
from feedgen.feed import FeedGenerator
from datetime import datetime
import pytz

def generate_blogsurgeai_feed():
    """Generate RSS feed for Surge AI blog"""

    # Initialize feed generator
    fg = FeedGenerator()
    fg.id('https://www.surgehq.ai/blog')
    fg.title('Surge AI Blog')
    fg.author({'name': 'Surge AI', 'email': 'team@surgehq.ai'})
    fg.link(href='https://www.surgehq.ai/blog', rel='alternate')
    fg.link(href='https://raw.githubusercontent.com/olshansky/rss-feeds/main/feeds/feed_blogsurgeai.xml', rel='self')
    fg.language('en')
    fg.description('New methods, current trends & software infrastructure for NLP. Articles written by our senior engineering leads from Google, Facebook, Twitter, Harvard, MIT, and Y Combinator')

    # Fetch the blog page
    url = 'https://www.surgehq.ai/blog'
    headers = {
        'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36'
    }

    try:
        response = requests.get(url, headers=headers, timeout=30)
        response.raise_for_status()
    except Exception as e:
        print(f"Error fetching blog page: {e}")
        return

    # Parse HTML
    soup = BeautifulSoup(response.content, 'html.parser')

    # Find all blog post items
    blog_items = soup.find_all('div', class_='research-v2-item')

    print(f"Found {len(blog_items)} blog posts")

    # Process each blog post
    for item in blog_items:
        try:
            # Find the link and title
            link_element = item.find('a', class_='research-v2-item-txt')
            if not link_element:
                continue

            title = link_element.get_text(strip=True)
            link = link_element.get('href')

            if not link.startswith('http'):
                link = 'https://www.surgehq.ai' + link

            # Create feed entry
            fe = fg.add_entry()
            fe.id(link)
            fe.title(title)
            fe.link(href=link)

            # Use current time as published date (since dates aren't in the listing)
            # In a real implementation, we could fetch each article to get the actual date
            fe.published(datetime.now(pytz.UTC))

            # Set description to the title (could be enhanced by fetching full article)
            fe.description(title)

            print(f"Added: {title}")

        except Exception as e:
            print(f"Error processing blog item: {e}")
            continue

    # Generate RSS feed
    output_path = 'feeds/feed_blogsurgeai.xml'
    fg.rss_file(output_path, pretty=True)
    print(f"\nRSS feed generated successfully: {output_path}")

if __name__ == '__main__':
    generate_blogsurgeai_feed()
