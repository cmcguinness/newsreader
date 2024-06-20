import datetime
import sqlite3
import threading


# For PyCharm:
# noinspection SqlResolve


class DataModel:
    _instance = {}

    # This is a per-thread singleton, as threads will have their own database connections
    # SQLite does not support multiple threads writing to the same database using the same connection
    def __new__(cls):
        if threading.get_ident() not in cls._instance:
            cls._instance[threading.get_ident()] = super().__new__(cls)
        return cls._instance[threading.get_ident()]

    def __init__(self):
        if "db" not in self.__dict__:
            self.db = "tags-stories.db"
            self.conn = sqlite3.connect(self.db)
            self.cur = self.conn.cursor()

            # Check if the "stories" table exists
            self.cur.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='stories'")
            if self.cur.fetchone() is None:
                # If not, create the "stories" table
                self.cur.execute('CREATE TABLE "stories" (\n'
                                 '     "id"	INTEGER NOT NULL UNIQUE,\n'
                                 '     "headline"	TEXT,\n'
                                 '     "url"	TEXT,\n'
                                 '     "read"	INTEGER,\n'
                                 '     "date"	TEXT,\n'
                                 '     "tags"	TEXT,\n'
                                 '     PRIMARY KEY("id"))')

            # Do the same for the "tags" table
            self.cur.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='tags'")
            if self.cur.fetchone() is None:
                self.cur.execute('CREATE TABLE "tags" (\n'
                                 '  "text"	TEXT NOT NULL UNIQUE,\n'
                                 '  "score"	REAL NOT NULL,\n'
                                 '  "count"	INTEGER NOT NULL,\n'
                                 '   PRIMARY KEY("text"))')

            self.conn.commit()

            self.tags = []
            self.stories = []
            self.fetch_all_tags()
            self.fetch_all_stories()

    #    ┌──────────────────────────────────────────────────────────┐
    #    │                      Tag Management                      │
    #    └──────────────────────────────────────────────────────────┘

    def fetch_all_tags(self):
        self.cur.execute("SELECT * FROM tags")
        rows = self.cur.fetchall()
        self.tags = [{'text': row[0], 'score': row[1], 'count': row[2]} for row in rows]

    def get_tags(self):
        return self.tags

    def get_tag(self, tag_name):
        for tag in self.tags:
            if tag['text'] == tag_name:
                return tag
        return {'text': tag_name, 'score': 0, 'count': 0}

    def upsert_tag(self, tag_dict):
        self.cur.execute("SELECT * FROM tags WHERE text = ?", (tag_dict['text'],))
        row = self.cur.fetchone()
        if row is None:
            self.cur.execute("INSERT INTO tags (text, score, count) VALUES (?, ?, ?)",
                             (tag_dict['text'], tag_dict['score'], tag_dict['count']))
        else:
            self.cur.execute("UPDATE tags SET score = ?, count = ? WHERE text = ?",
                             (tag_dict['score'], tag_dict['count'], tag_dict['text']))
        self.conn.commit()
        self.fetch_all_tags()  # Update the in-memory list of tags

    def upsert_tags(self, tags_list):
        for tag_dict in tags_list:
            self.upsert_tag(tag_dict)

        self.fetch_all_tags()

    #    ┌──────────────────────────────────────────────────────────┐
    #    │                Story (Article) Management                │
    #    └──────────────────────────────────────────────────────────┘

    @staticmethod
    def split_topics(topics):
        if topics is None:
            return []
        if topics == '':
            return []
        return topics.split(',')

    def fetch_all_stories(self):
        self.delete_old_stories()
        self.cur.execute("SELECT * FROM stories")
        rows = self.cur.fetchall()
        self.stories = [{'id': row[0], 'headline': row[1], 'url': row[2], 'read': row[3],
                         'date': row[4], 'tags': self.split_topics(row[5])
                         } for row in rows]

    def delete_old_stories(self):
        two_days_ago = datetime.datetime.now() - datetime.timedelta(days=2)
        self.cur.execute("DELETE FROM stories WHERE date < ?", (two_days_ago,))
        self.conn.commit()

    def get_story_by_headline_url(self, headline, url):
        for story in self.stories:
            if story['headline'] == headline and story['url'] == url:
                return story
        return None

    def get_story_by_id(self, story_id):
        for story in self.stories:
            if int(story['id']) == int(story_id):
                return story
        return None

    def get_stories(self):
        self.fetch_all_stories()
        return self.stories

    def upsert_story(self, story_dict):
        if 'id' not in story_dict:
            self.cur.execute("SELECT id FROM stories WHERE headline = ? AND url = ?",
                             (story_dict['headline'], story_dict['url']))
            row = self.cur.fetchone()
            if row is None:
                self.cur.execute("SELECT MAX(id) FROM stories")
                max_id = self.cur.fetchone()[0]
                story_dict['id'] = max_id + 1 if max_id is not None else 1
            else:
                story_dict['id'] = row[0]

        self.cur.execute("SELECT * FROM stories WHERE id = ?", (story_dict['id'],))
        row = self.cur.fetchone()
        if row is None:
            self.cur.execute(
                "INSERT INTO stories (id, headline, url, read, date, tags) VALUES (?, ?, ?, ?, ?, ?)",
                (story_dict['id'], story_dict['headline'], story_dict['url'], story_dict['read'],
                 datetime.datetime.now(), ','.join(story_dict['tags']))
            )
        else:
            self.cur.execute(
                "UPDATE stories SET headline = ?, url = ?, read = ?, date = ?, tags = ? WHERE id = ?",
                (story_dict['headline'], story_dict['url'], story_dict['read'], datetime.datetime.now(),
                 ','.join(story_dict['tags']), story_dict['id']))
        self.conn.commit()

        return story_dict['id']

    def upsert_stories(self, stories_list):
        for story_dict in stories_list:
            self.upsert_story(story_dict)

        self.fetch_all_stories()  # Update the in-memory list of stories

    def story_exists(self, headline, url):
        for story in self.stories:
            if story['headline'] == headline and story['url'] == url:
                return story['id']
        return -1

    def mark_story_as_read(self, story_i9d):
        for story in self.stories:
            if int(story['id']) == int(story_i9d):
                story['read'] = 1
                self.cur.execute("UPDATE stories SET read = ? WHERE id = ?", (1, story_i9d))
                self.conn.commit()
                break

    def get_article_tags(self, article_id):
        story = self.get_story_by_id(article_id)
        if story is not None:
            return story['tags']
        return []
