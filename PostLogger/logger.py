import sys
sys.path.insert(0, ".")
import string
import praw
import json
import math
import argparse
import os
import time
import Config

parser = argparse.ArgumentParser()
parser.add_argument('sub_name', metavar='C', type=str)
args = parser.parse_args()
CONFIG = Config.Config(args.sub_name.lower())

debug = False

current_time = time.time()
db_fname = "PostLogger/posts.json"

# required function for getting ASCII from json load
def ascii_encode_dict(data):
        ascii_encode = lambda x: x.encode('ascii') if isinstance(x, unicode) else x
        return dict(map(ascii_encode, pair) for pair in data.items())

# Function to load the DB into memory
def get_db(fname):
        with open(fname) as json_data: # open the funko-shop's data
                data = json.load(json_data, object_hook=ascii_encode_dict)
        return data

def dump(db, fname):
        with open(fname, 'w') as outfile:  # Write out new data
                outfile.write(str(db).replace("'", '"').replace('{u"', '{"').replace(' u"', ' "').encode('ascii','ignore'))

def main():
	db = get_db(db_fname)
	if CONFIG.subreddit_name not in db:
		db[CONFIG.subreddit_name] = {}
	posts = CONFIG.subreddit.new(limit=20)
	for post in posts:
		updated = False
		author = post.author.name.lower()
		created = post.created_utc
		title = post.title
		title = ''.join(filter(lambda x: x in set(string.printable), title))
		title = title.replace("'", "").replace('"', "")
		id = post.id
		if author not in db[CONFIG.subreddit_name] or not db[CONFIG.subreddit_name][author]:
			db[CONFIG.subreddit_name][author] = [{"id": id, "created": created, "title": title}]
			updated = True
		if created > db[CONFIG.subreddit_name][author][-1]["created"]:
			db[CONFIG.subreddit_name][author].append({"id": id, "created": created, "title": title})
			updated = True
		for historic_post in db[CONFIG.subreddit_name][author][::]:
			if historic_post["created"] + (7*24*60*60) < current_time:
				db[CONFIG.subreddit_name][author].remove(historic_post)
				updated = True
		if updated:
			wiki_text = "\n\n".join(["[" + x["title"] + "](https://redd.it/" + x["id"] + ") - " + time.ctime(x["created"]) for x in db[CONFIG.subreddit_name][author]])
			page = CONFIG.subreddit.wiki['user_post_history/'+author]
			page.edit(wiki_text)
	dump(db, db_fname)

main()

