import aiohttp
from bs4 import BeautifulSoup


async def get_soup(url):
    async with aiohttp.ClientSession() as session:
        async with session.get(f"{url}") as r:
            if r.status == 200:
                return BeautifulSoup(await r.read(), 'html.parser')
            else:
                return None


def web_scrape(guild_id, url):
    soup = get_soup(url)