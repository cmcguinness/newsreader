#    ┌───────────────────────────────────────────────────────────────────┐
#    │                                                                   │
#    │                             CNN Lite                              │
#    │                                                                   │
#    │    Handle the retrieval of headlines from CNN, generating tags    │
#    │    for them, scoring them for pertinence, and persisting them.    │
#    │                                                                   │
#    │        Lot o' Stuff this class does, so it's a bit messy.         │
#    │                                                                   │
#    └───────────────────────────────────────────────────────────────────┘

from bs4 import BeautifulSoup
import requests
import time
import llm
import json
from tags import Tags
from datamodel import DataModel
import utilities
import csv
import os


u = utilities.Utilities()


class CNNLite:
    _instance = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def __init__(self):
        if "last_refresh" not in self.__dict__:

            self.last_refresh = 0
            self.refresh_time = 300     # seconds, CNN doesn't update headlines that fast

            # This is a debugging log that will be used to store the headlines and tags in case
            # something looks suspicious in the UI
            if not os.path.exists('temp'):
                os.mkdir('temp')

            with open('temp/articles.csv', 'w', newline='') as f:
                cw = csv.writer(f, delimiter=',', quotechar='"', quoting=csv.QUOTE_MINIMAL)
                cw.writerow(['headline', 'url', 'tags'])

            self.headline_size_cutoff = 10
            self.headline_suspicious_cutoff = 30

            ol = llm.LLM()
            self.batch_size = ol.get_batch_size()
            self.max_tags = 5

            #    ┌──────────────────────────────────────────────────────────┐
            #    │        Since we want to be a responsible user, if        │
            #    │     debugging is set we will use a cached version of     │
            #    │           cnnlite instead of fetching it live            │
            #    └──────────────────────────────────────────────────────────┘
            self.debugging = False

            self.refresh_list()

    # Call this to see if there's anything new posted on CNN
    def refresh_list(self):
        self.fetch_new_articles()
        self.score_articles()

    # The UI wants to know if it's time to refresh when the user reloads the page
    def time_for_refresh(self):
        ttr = time.time() - self.last_refresh >= self.refresh_time

        if ttr:
            print('*** Time to refresh CNN ***', flush=True)

        return ttr

    # Some of the links are internal CNN site links, but they are usually shorter than
    # real headlines, so we can use a heuristic to cull them
    def skip_headline(self, headline: str, url: str) -> bool:
        if url.startswith('https://'):
            print(f'Skipping non-article link {headline}: {url}')
            return True

        if len(headline) <= self.headline_size_cutoff:
            print(f'Skipping short headline {headline}: {url}')
            return True

        if headline == 'Go to the full CNN experience':
            return True

        if headline == 'Cookie Settings':
            return True

        if len(headline) < self.headline_suspicious_cutoff:
            print(f'Suspicious headline: {headline}: {url}')

        return False

    def fetch_new_articles(self):

        database = DataModel()

        # Only refresh the list every n minutes, we don't want to annoy CNN
        if time.time() - self.last_refresh < self.refresh_time:
            return

        if self.debugging:
            print("\u250C" + ("\u2500"*38) + "\u2510")
            print("\u2502              DEBUG MODE              \u2502")
            print("\u2502                                      \u2502")
            print("\u2502     We are reading from a cached     \u2502")
            print("\u2502    file, not live data from CNN.     \u2502")
            print("\u2514"+("\u2500"*38)+"\u2518")

        self.last_refresh = time.time()

        u.update_status("working", "Fetching articles from CNN Lite")

        # Pull down the latest list of stories
        base_url = 'https://lite.cnn.com'
        if self.debugging:
            with open('cached_cnnlite_response.html', 'r') as f:
                html_content = f.read()
        else:
            # Fetch the HTML content
            print('*** Fetchihng from CNN ***')
            response = requests.get(base_url)
            html_content = response.text
            # save it for use in debugging
            with open('cached_cnnlite_response.html', 'w') as f:
                f.write(html_content)

        # Parse the HTML content using BeautifulSoup
        soup = BeautifulSoup(html_content, 'html.parser')

        u.update_status("working", "Parsing articles from CNN Lite.  Find 0 new articles.")

        new_count = 0

        # The CNN Lite page is basically a list of headlines as hyperlinks, so it's easy
        # to pull them out
        for a_tag in soup.find_all('a', href=True):
            headline = a_tag.get_text(strip=True)

            if self.skip_headline(headline, a_tag['href']):
                continue

            url = base_url + a_tag['href']

            story_id = database.story_exists(headline, url)

            if story_id == -1:
                database.upsert_story({"headline": headline, "url": url, "tags": [], "score": 0, "read": 0})
                new_count += 1

            u.update_status("working", f"Parsing articles from CNN Lite.  Find {new_count} new articles.")

    @staticmethod
    def llama_news(count):

        llamas = [
            "Larry doesn't want to tarry with headline",
            "Lou likes headline",
            "Lenny has seen so many, but still is looking at headline",
            "Lucky feels plucky with headline",
            "Lane is like vane with headline"
        ]
        w = int(time.time() * 1000) % len(llamas)

        u.update_status("working", llamas[w] + f" #{count+1}")

    def score_articles(self):
        chat_engine = llm.LLM()
        database = DataModel()

        u.update_status("working", "Tagging articles from CNN Lite.")

        print('Tagging articles: 0', flush=True)
        articles = database.get_stories()

        new_articles = []
        for article in articles:
            if len(article['tags']) == 0:
                new_articles.append(article)

        count = 0

        while len(new_articles) > 0:
            self.llama_news(count)
            print(f"There are {len(new_articles)} articles left to tag", flush=True)

            batch = new_articles[:self.batch_size]
            del new_articles[:self.batch_size]

            # We only want to send in the id and headline to the LLM
            if len(batch) > 0:
                headlines = []
                for story in batch:
                    headlines.append({"headline": story['headline']})
                tags = chat_engine.chat(None, json.dumps(headlines), [])

                # If there's just one article, it's likely to not be in an array
                if type(tags) is dict:
                    tags = [tags]

                # Sometimes, an LLM will stick a "headline" in the mix
                # or add extra keys.  This filters them out
                new_tags = []
                for tag in tags:
                    if "tags" in tag:
                        # Some LLMs will generate way too many tags.  This is a fail-safe to limit the # of tags
                        new_tags.append({"tags": tag["tags"][:self.max_tags]})

                tags = new_tags

                for i in range(len(tags)):
                    batch[i]['tags'] = tags[i]['tags']
                    batch[i]['read'] = 0
                    with open('temp/articles.csv', 'a', newline='') as f:
                        cw = csv.writer(f, delimiter=',', quotechar='"', quoting=csv.QUOTE_MINIMAL)
                        cw.writerow([batch[i]['headline'], batch[i]['url'], ' '.join(batch[i]['tags'])])

                    database.upsert_story(batch[i])

            count += self.batch_size

            # Save us the time in tagging all the articles
            if self.debugging:
                break

    @staticmethod
    def get_article_url(article_id):

        database = DataModel()

        story = database.get_story_by_id(article_id)
        if story is not None:
            return story['url']
        return None

    @staticmethod
    def mark_article_read(article_id):

        database = DataModel()

        database.mark_story_as_read(article_id)

    @staticmethod
    def get_scored_articles():

        database = DataModel()
        tag_hist = Tags()
        articles = []
        database.fetch_all_stories()

        for story in database.stories:
            if story['read'] == 0:
                score = 0
                story['score'] = score
                for t in story['tags']:
                    score += tag_hist.get_score(t)
                    story['score'] = score
                articles.append(story)

        articles.sort(key=lambda x: x['score'], reverse=True)
        return articles

    def get_top_stories(self, count=25):
        self.refresh_list()
        top_stories = self.get_scored_articles()[:count]
        return top_stories
