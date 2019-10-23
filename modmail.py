import os.path
import datetime
import sys
import praw
import report
from collections import defaultdict
import json
import argparse

parser = argparse.ArgumentParser()
parser.add_argument('config_file_name', metavar='C', type=str)
args = parser.parse_args()
fname = 'config/' + args.config_file_name
if not os.path.exists("config"):
        os.mkdir("config")

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

debug = False

num_messages = 10

def ascii_encode_dict(data):
	ascii_encode = lambda x: x.encode('ascii') if isinstance(x, unicode) else x
	return dict(map(ascii_encode, pair) for pair in data.items())

# Function to load the DB into memory
def get_db(FNAME):
	with open(FNAME) as json_data: # open the funko-shop's data
		funko_store_data = json.load(json_data, object_hook=ascii_encode_dict)
	return funko_store_data

def main(subreddit_name):
	FNAME = 'database/userbans-' + subreddit_name + '.json'
	if not os.path.exists('database'):
		os.mkdir('database')
	if not os.path.exists(FNAME):
		f = open(FNAME, "w")
		f.write("{}")
		f.close()

	reddit = praw.Reddit(client_id=client_id, client_secret=client_secret, user_agent='UserAgent', username=bot_username, password=bot_password)
	sub = reddit.subreddit(subreddit_name)

	# Want to run this script to handle mod reporting for easier mobile modding
	report.remove_reported_posts(sub, subreddit_name)

	queries = []
	queries.append(sub.modmail.conversations(state='all', limit=num_messages))
	queries.append(sub.modmail.conversations(state='archived', limit=num_messages))

	users = get_db(FNAME)

	for query in queries:
		i = 0
		mod_conv = None
		for mod_conv in query:
			i += 1
			if mod_conv.subject == 'Your post from ' + subreddit_name + ' was removed' or mod_conv.subject == 'Your comment from ' + subreddit_name + ' was removed' or mod_conv.subject == "Your submission was removed from /r/" + subreddit_name or mod_conv.subject == "Your comment was removed from /r/" + subreddit_name:
				message = reddit.subreddit('redditdev').modmail(mod_conv.id)
				try:
					user = message.user.name
				except Exception as e:  #  Sometimes, the message is valid but any operations return a 404. Skip and continue if we see this.
					print("Error for Mod Mail Message: " + str(message))
					print(str(e))
					print("===========================================")
					continue
				if "Your submission was removed from /r/" + subreddit_name == mod_conv.subject or "Your comment was removed from /r/" + subreddit_name == mod_conv.subject:
					removal_reason = message.messages[0].body_markdown.split(" - ")[0]
					if len(removal_reason) > 50:
						removal_reason= "Mod Tool Box Removal"
				else:
					removal_reason = message.messages[0].body_markdown.split("'")[1]
			elif mod_conv.subject == "You've been temporarily banned from participating in r/" + subreddit_name:
				message = reddit.subreddit('redditdev').modmail(mod_conv.id)
				days_banned = message.messages[0].body_markdown.split("This ban will last for ")[1].split(" ")[0]
				user = message.user.name
				removal_reason = "BANNED - " + days_banned + " days."
			elif mod_conv.subject == "You've been permanently banned from participating in r/" + subreddit_name:
				message = reddit.subreddit('redditdev').modmail(mod_conv.id)
				user = message.user.name
				removal_reason = "PERM-BANNED"
			elif mod_conv.subject == "Your ban from r/" + subreddit_name + " has changed":
				message = reddit.subreddit('redditdev').modmail(mod_conv.id)
				if 'You have been permanently banned from participating in' in message.messages[0].body_markdown:
					removal_reason = "PERM-BANNED"
				else:
					days_banned = message.messages[0].body_markdown.split("This ban will last for ")[1].split(" ")[0]
					removal_reason = "CHANGED BAN - " + days_banned + " days."
				user = message.user.name
			else:
				continue

			removal_reason = str(datetime.datetime.now()).split(" ")[0] + " - " + removal_reason

			if user not in users:
				users[user] = {}

			new = False
			if mod_conv.id not in users[user]:
				users[user][mod_conv.id] = removal_reason
				new = True

			if new:
				print(user + " - " + removal_reason + " - " + mod_conv.id)
				print("===========================================")
				replies = []
				removal_ids = users[user].keys()
				removal_ids.sort()
				for removal_id in removal_ids:
					replies.append("* " + users[user][removal_id] + " - https://mod.reddit.com/mail/all/" + removal_id)
				reply = "History of u/" + user + " on r/" + subreddit_name + ":\n\n" + "\n\n".join(replies)
				# Comment this line if searching through the past
				if not debug:
					try:
						message.reply(reply, internal=True)
					except:
						print("Unable to reply to message " + str(message))
				else:
					print(reply)

		# Uncomment this section to search all of mod mail
#		if i > 0:
#			queries.append(reddit.subreddit(subreddit_name).modmail.conversations(after=mod_conv.id, state='archived', limit=100))

	if not debug:
		with open(FNAME, 'w') as outfile:  # Write out new data
				outfile.write(str(json.dumps(users))
					.replace("'", '"')
					.replace(', u"', ', "')
					.replace('[u"', '["')
					.replace('{u"', '{"')
					.encode('ascii','ignore'))


if not os.path.exists(fname):
	print("config file does not exist. Please create a configuration file at path " + fname)
else:
	main(subreddit_name)









