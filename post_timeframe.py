from os import mkdir
import os.path
import math
import json
import praw
import argparse

parser = argparse.ArgumentParser()
parser.add_argument('config_file_name', metavar='C', type=str)
args = parser.parse_args()
fname = 'config/' + args.config_file_name
if not os.path.exists("config"):
	mkdir("config")

debug = False

f = open(fname, "r")
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
days_between_posts = int(math.ceil(float(config['hours_per_post'])))
seconds_between_posts = float(config['hours_per_post']) * 24 * 60 * 60
whitelisted_words = config['whitelisted_words'].split(',')

FNAME = 'database/recent_posts-' + subreddit_name + '.txt'
if not os.path.exists('database'):
	os.mkdir('database')

# IDK, I needed this according to stack overflow.
def ascii_encode_dict(data):
        ascii_encode = lambda x: x.encode('ascii') if isinstance(x, unicode) else x
        return dict(map(ascii_encode, pair) for pair in data.items())

# Function to load the swap DB into memory
def get_data():
        if not os.path.exists(FNAME):
                f = open(FNAME, "w")
                f.write("{}")
                f.close()
        with open(FNAME) as json_data: # open the funko-shop's data
                funko_store_data = json.load(json_data, object_hook=ascii_encode_dict)
        return funko_store_data

# Writes the json local file... dont touch this.
def dump(swap_data):
        with open(FNAME, 'w') as outfile:  # Write out new data
                outfile.write(str(json.dumps(swap_data))
                        .replace("'", '"')
                        .replace(', u"', ', "')
                        .replace('[u"', '["')
                        .replace('{u"', '{"')
                        .encode('ascii','ignore'))

def main():
	reddit = praw.Reddit(client_id=client_id, client_secret=client_secret, user_agent='UserAgent', username=bot_username, password=bot_password)
	sub = reddit.subreddit(subreddit_name)

	db = get_data()
	mods = [str(x) for x in sub.moderator()]

	for submission in sub.new(limit=10):
		if submission.distinguished:
			continue

		if whitelisted_words[0] and any([word in submission.title.lower() for word in whitelisted_words]):
			continue

		author = str(submission.author)
		if author in mods:
			continue

		timestamp = submission.created_utc
		if author not in db:
			db[author] = 0

		last_timestamp = db[author]
		if last_timestamp == timestamp:
			continue

		if timestamp - last_timestamp < seconds_between_posts and not submission.approved:
			if not debug:
				submission.mod.remove()
				reply = submission.reply("This post has been removed because you have made more than one post in " + str(days_between_posts) +" days. Please message the mods if you have any questions.")
				reply.mod.distinguish(sticky=True)
			else:
				print("Would have removed post " + submission.id)
		else:
			if timestamp > last_timestamp:
				db[author] = timestamp

	dump(db)

if not os.path.exists(fname):
        print("config file does not exist. Please create a configuration file at path " + fname)
else:
        main()
