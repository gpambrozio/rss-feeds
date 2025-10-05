import requests
from bs4 import BeautifulSoup
from datetime import datetime
import pytz
from feedgen.feed import FeedGenerator
import logging
from pathlib import Path
import json
import os

# Set up logging
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)


def get_project_root():
    """Get the project root directory."""
    return Path(__file__).parent.parent


def ensure_feeds_directory():
    """Ensure the feeds directory exists."""
    feeds_dir = get_project_root() / "feeds"
    feeds_dir.mkdir(exist_ok=True)
    return feeds_dir


def get_article_cache_file():
    """Get the path to the article cache file."""
    feeds_dir = ensure_feeds_directory()
    return feeds_dir / "anthropic_engineering_article_cache.json"


def load_article_cache():
    """Load the article cache from disk."""
    cache_file = get_article_cache_file()
    if cache_file.exists():
        try:
            with open(cache_file, "r") as f:
                cache = json.load(f)
                # Convert date strings back to datetime objects
                for link, data in cache.items():
                    data["date"] = datetime.fromisoformat(data["date"])
                return cache
        except Exception as e:
            logger.warning(f"Failed to load article cache: {e}")
    return {}


def save_article_cache(cache):
    """Save the article cache to disk."""
    cache_file = get_article_cache_file()
    try:
        # Convert datetime objects to strings for JSON serialization
        cache_to_save = {}
        for link, data in cache.items():
            cache_to_save[link] = {"title": data["title"], "date": data["date"].isoformat()}

        with open(cache_file, "w") as f:
            json.dump(cache_to_save, f, indent=2)
    except Exception as e:
        logger.warning(f"Failed to save article cache: {e}")


def fetch_engineering_content(url="https://www.anthropic.com/engineering"):
    """Fetch engineering page content from Anthropic's website."""
    try:
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"
        }
        response = requests.get(url, headers=headers, timeout=10)
        response.raise_for_status()
        return response.text
    except requests.RequestException as e:
        logger.error(f"Error fetching engineering content: {str(e)}")
        raise


def extract_title(card):
    """Extract title using multiple fallback selectors."""
    selectors = ["h2", "h3", "h1", "h4[class*='headline']", "h3[class*='title']", "h2[class*='title']"]
    for selector in selectors:
        elem = card.select_one(selector)
        if elem and elem.text.strip():
            return elem.text.strip()
    return None


def extract_date(card, article_cache, link):
    """Extract date using multiple fallback selectors and cache."""
    # Check cache first
    if link in article_cache:
        return article_cache[link]["date"], False

    selectors = [
        "div.ArticleList_date__2VTRg",
        "div[class*='date']",
        "p[class*='date']",
        "time",
        ".detail-m.agate",
    ]

    date_formats = [
        "%b %d, %Y",
        "%B %d, %Y",
        "%b %d %Y",
        "%B %d %Y",
        "%Y-%m-%d",
        "%m/%d/%Y",
    ]

    for selector in selectors:
        elem = card.select_one(selector)
        if elem:
            date_text = elem.text.strip()
            for date_format in date_formats:
                try:
                    date = datetime.strptime(date_text, date_format)
                    return date.replace(hour=0, minute=0, second=0, tzinfo=pytz.UTC), True
                except ValueError:
                    continue

    # Use current time as "first seen" date if not found
    return datetime.now(pytz.UTC), True


def extract_link(card):
    """Extract link using multiple fallback selectors."""
    selectors = [
        "a.ArticleList_cardLink__VWIzl",
        "a[href*='/engineering/']",
        "a[class*='cardLink']",
        "a[class*='link']",
    ]

    for selector in selectors:
        elem = card.select_one(selector)
        if elem and elem.get("href"):
            href = elem["href"]
            return "https://www.anthropic.com" + href if href.startswith("/") else href

    return None


def validate_article(article):
    """Validate article has required fields."""
    if not article.get("title") or len(article["title"]) < 5:
        return False
    if not article.get("link") or not article["link"].startswith("http"):
        return False
    if not article.get("date"):
        return False
    return True


def parse_engineering_html(html_content):
    """Parse the engineering HTML content and extract article information."""
    try:
        soup = BeautifulSoup(html_content, "html.parser")
        articles = []
        seen_links = set()

        # Load existing article cache
        article_cache = load_article_cache()
        cache_updated = False

        # Find all engineering article links using flexible selector
        all_eng_links = soup.select('a[href*="/engineering/"]')
        logger.info(f"Found {len(all_eng_links)} potential engineering article links")

        # Also look for article elements
        article_elements = soup.select("article")

        for element in article_elements + all_eng_links:
            try:
                # Extract link
                link = extract_link(element)
                if not link or link in seen_links:
                    continue

                # Skip the main engineering page
                if link.endswith("/engineering") or link.endswith("/engineering/"):
                    continue

                seen_links.add(link)

                # Extract title
                title = extract_title(element)
                if not title:
                    logger.debug(f"Could not extract title for link: {link}")
                    continue

                # Extract date (with caching)
                date, needs_cache = extract_date(element, article_cache, link)

                # Update cache if needed
                if needs_cache:
                    article_cache[link] = {"title": title, "date": date}
                    cache_updated = True

                # Extract description
                desc_selectors = ["p.ArticleList_summary__G96cV", "p[class*='summary']", "p[class*='description']"]
                description = title
                for sel in desc_selectors:
                    desc_elem = element.select_one(sel)
                    if desc_elem and desc_elem.text.strip():
                        description = desc_elem.text.strip()
                        break

                article = {
                    "title": title,
                    "link": link,
                    "description": description,
                    "date": date,
                    "category": "Engineering",
                }

                if validate_article(article):
                    articles.append(article)
                    logger.info(f"Found article: {title}")

            except Exception as e:
                logger.warning(f"Error parsing element: {str(e)}")
                continue

        # Save the updated cache if needed
        if cache_updated:
            save_article_cache(article_cache)
            logger.info("Updated article cache with new articles")

        logger.info(f"Successfully parsed {len(articles)} articles")
        return articles

    except Exception as e:
        logger.error(f"Error parsing HTML content: {str(e)}")
        raise


def generate_rss_feed(articles, feed_name="anthropic_engineering"):
    """Generate RSS feed from engineering articles."""
    try:
        fg = FeedGenerator()
        fg.title("Anthropic Engineering Blog")
        fg.description("Latest engineering articles and insights from Anthropic's engineering team")
        fg.link(href="https://www.anthropic.com/engineering")
        fg.language("en")

        # Set feed metadata
        fg.author({"name": "Anthropic Engineering Team"})
        fg.logo("https://www.anthropic.com/images/icons/apple-touch-icon.png")
        fg.subtitle("Inside the team building reliable AI systems")
        fg.link(href="https://www.anthropic.com/engineering", rel="alternate")
        fg.link(href=f"https://anthropic.com/engineering/feed_{feed_name}.xml", rel="self")

        # Sort articles by date (newest first)
        articles.sort(key=lambda x: x["date"], reverse=True)

        # Add entries
        for article in articles:
            fe = fg.add_entry()
            fe.title(article["title"])
            fe.description(article["description"])
            fe.link(href=article["link"])
            fe.published(article["date"])
            fe.category(term=article["category"])
            fe.id(article["link"])

        logger.info("Successfully generated RSS feed")
        return fg

    except Exception as e:
        logger.error(f"Error generating RSS feed: {str(e)}")
        raise


def save_rss_feed(feed_generator, feed_name="anthropic_engineering"):
    """Save the RSS feed to a file in the feeds directory."""
    try:
        # Ensure feeds directory exists and get its path
        feeds_dir = ensure_feeds_directory()

        # Create the output file path
        output_filename = feeds_dir / f"feed_{feed_name}.xml"

        # Save the feed
        feed_generator.rss_file(str(output_filename), pretty=True)
        logger.info(f"Successfully saved RSS feed to {output_filename}")
        return output_filename

    except Exception as e:
        logger.error(f"Error saving RSS feed: {str(e)}")
        raise


def main(feed_name="anthropic_engineering"):
    """Main function to generate RSS feed from Anthropic's engineering page."""
    try:
        # Fetch engineering content
        html_content = fetch_engineering_content()

        # Parse articles from HTML
        articles = parse_engineering_html(html_content)

        if not articles:
            logger.warning("No articles found on the engineering page")
            return False

        # Generate RSS feed
        feed = generate_rss_feed(articles, feed_name)

        # Save feed to file
        output_file = save_rss_feed(feed, feed_name)

        logger.info(f"Successfully generated RSS feed with {len(articles)} articles")
        return True

    except Exception as e:
        logger.error(f"Failed to generate RSS feed: {str(e)}")
        return False


if __name__ == "__main__":
    main()
