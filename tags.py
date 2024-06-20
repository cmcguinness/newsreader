#    ┌────────────────────────────────────────────────────────────────────┐
#    │    Tags                                                            │
#    │                                                                    │
#    │    This manages the tags which are used in conjunction with the    │
#    │    stories.  We CRUD 'em, we like 'em, we dislike 'em.             │
#    │                                                                    │
#    └────────────────────────────────────────────────────────────────────┘

import datamodel


class Tags:
    _instance = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def __init__(self):
        if "tags" not in self.__dict__:
            self.tags = {}
            self.read_tags()

    def read_tags(self):
        d = datamodel.DataModel()
        d.fetch_all_tags()
        self.tags = d.get_tags()

    def write_tags(self):
        d = datamodel.DataModel()
        d.upsert_tags(self.tags)

    def get_tag(self, tag):
        tag = tag.lower()
        # Yeah, yeah, yeah, I know this is O(n) and could be O(1) with a dict
        # Improving it is an exercise left for the reader
        for known_tag in self.tags:
            if known_tag["text"] == tag:
                return known_tag

        return None

    def add_tag(self, tag: str):
        d = datamodel.DataModel()
        tag = tag.lower()
        if self.get_tag(tag) is None:
            d.upsert_tag({"text": tag, "score": 0, "count": 0})
            self.read_tags()

    def like_or_dislike_tag(self, tag: str, like: int):
        d = datamodel.DataModel()
        tag = tag.lower()
        full_tag = self.get_tag(tag)
        if full_tag is None:
            self.add_tag(tag)
            full_tag = self.get_tag(tag)
        full_tag["score"] = (like + full_tag["score"] * full_tag["count"]) / (full_tag["count"] + 1)
        full_tag["count"] += 1
        d.upsert_tag(full_tag)

    def like_tags(self, tags):
        for tag in tags:
            self.like_or_dislike_tag(tag, 1)

    def dislike_tags(self, tags):
        for tag in tags:
            self.like_or_dislike_tag(tag, -1)

    def get_score(self, tag):
        if type(tag) is dict:
            tag = tag["text"]
        tag = tag.lower()
        full_tag = self.get_tag(tag)
        if full_tag is None:
            self.add_tag(tag)
            full_tag = self.get_tag(tag)
        return full_tag["score"]
