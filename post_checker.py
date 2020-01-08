import time
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
days_between_posts = int(math.ceil(float(config['days_per_post'])))
seconds_between_posts = float(config['days_per_post']) * 24 * 60 * 60
whitelisted_words = config['whitelisted_words'].split(',')
num_minutes_flair = float(config['minutes_no_flair'])

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

	for submission in [x for x in sub.new(limit=100)][::-1]: # reverse the list to view oldest first.
		# Checks if flaired within time range
		missing_flair = submission.link_flair_text == None
		time_diff= time.time() - submission.created_utc
		print(time_diff)
		past_time_limit = time_diff > num_minutes_flair*60
		if missing_flair and past_time_limit:
			reply = submission.reply("Hi there! Unfortunately your post has been removed as all posts must be flaired within " + str(num_minutes_flair) + " minutes of being posted.\n\nIf you're unfamiliar with how to flair please check the wiki on [how to flair your posts](https://www.reddit.com/r/funkopop/wiki/flairing) then feel free to repost.\n\n***\nI am a bot and this comment was left automatically and as a courtesy to you. \nIf you have any questions, please [message the moderators](https://www.reddit.com/message/compose?to=%2Fr%2Ffunkopop).")
			reply.mod.lock()
			reply.mod.distinguish(how="yes", sticky=True)
			submission.mod.remove()
			continue

		# Ignore posts with whitelisted words
		if whitelisted_words[0] and any([word in submission.title.lower() for word in whitelisted_words]):
			continue

		# Ignore posts made by mods
		author = str(submission.author)
		if author in mods:
			continue

		# Get timestamp info and make sure we have seen posts from this author before
		timestamp = submission.created_utc
		if author not in db:
			db[author] = 0

		# If this post was the most recent post from this author, we're good
		last_timestamp = db[author]
		if last_timestamp == timestamp:
			continue

		# If we manage to see an older post after a newer post, skip the older post
		if last_timestamp > timestamp:
			continue

		# If this postt was made too recently
		if timestamp - last_timestamp < seconds_between_posts and not submission.approved:
			if not debug:
				submission.mod.remove()
				if days_between_posts == 1:
					time_string = "24 hours"
				else:
					time_string = str(days_between_posts) + " days"
				reply = submission.reply("This post has been removed because you have made more than one post in " + time_string + ". Please message the mods if you have any questions.")
				reply.mod.distinguish(sticky=True)
			else:
				print("Would have removed post " + submission.id)
		else: # If this is a new post and is valid, update the saved timestamp
			if timestamp > last_timestamp:
				db[author] = timestamp

	dump(db)

if not os.path.exists(fname):
        print("config file does not exist. Please create a configuration file at path " + fname)
else:
        main()
