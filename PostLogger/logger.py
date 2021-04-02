import string
import praw
import json
import math
import argparse
import os
import time

parser = argparse.ArgumentParser()
parser.add_argument('config_file_name', metavar='C', type=str)
args = parser.parse_args()
config_fname = 'config/' + args.config_file_name
if not os.path.exists("config"):
        os.mkdir("config")

f = open(config_fname, "r")
info = f.read().splitlines()
f.close()

config = {}
for item in info:
        pair = item.split(":")
        config[pair[0]] = pair[1]

subreddit_name = config['subreddit_name']
client_id = config['client_id']
client_secret = config['client_secret']
bot_username = config['bot_username']
bot_password = config['bot_password']

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
	reddit = praw.Reddit(client_id=client_id, client_secret=client_secret, user_agent='Post Logging Bot for ' + subreddit_name + ' v1.0 (by u/RegExr)', username=bot_username, password=bot_password)
	sub = reddit.subreddit(subreddit_name)
	db = get_db(db_fname)
	if subreddit_name not in db:
		db[subreddit_name] = {}
	posts = sub.new(limit=20)
	for post in posts:
		updated = False
		author = post.author.name.lower()
		created = post.created_utc
		title = post.title
		title = ''.join(filter(lambda x: x in set(string.printable), title))
		title = title.replace("'", "").replace('"', "")
		id = post.id
		if author not in db[subreddit_name] or not db[subreddit_name][author]:
			db[subreddit_name][author] = [{"id": id, "created": created, "title": title}]
			updated = True
		if created > db[subreddit_name][author][-1]["created"]:
			db[subreddit_name][author].append({"id": id, "created": created, "title": title})
			updated = True
		for historic_post in db[subreddit_name][author][::]:
			if historic_post["created"] + (7*24*60*60) < current_time:
				db[subreddit_name][author].remove(historic_post)
				updated = True
		if updated:
			wiki_text = "\n\n".join(["[" + x["title"] + "](https://redd.it/" + x["id"] + ") - " + time.ctime(x["created"]) for x in db[subreddit_name][author]])
			page = sub.wiki['user_post_history/'+author]
			page.edit(wiki_text)
	dump(db, db_fname)

main()

