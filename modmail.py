import time
import math
import os.path
from os import mkdir
import datetime
import sys
import praw
from imgurpython import ImgurClient
import report
import post_checker
from collections import defaultdict
import json
import argparse

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
days_between_posts = int(math.ceil(float(config['days_per_post'])))
lock_post = config['lock_post'] == "True"
seconds_between_posts = float(config['days_per_post']) * 24 * 60 * 60
whitelisted_words = [x.lower() for x in config['whitelisted_words'].split(',')]
num_minutes_flair = float(config['minutes_no_flair'])
imgur_freshness_days = float(config['imgur_freshness_days'])
imgur_client = config['imgur_client']
imgur_secret = config['imgur_secret']

debug = False

current_time = time.time()
num_messages = 10
num_posts_to_check = 100

def save_report_data(mod_name, report_reason, sub_name):
        f = open('database/report_log-' + sub_name + ".txt", 'a')
        f.write(str(datetime.datetime.now()).split(" ")[0] + " - " + mod_name + " - " + report_reason + "\n")
        f.close()

def ascii_encode_dict(data):
	ascii_encode = lambda x: x.encode('ascii') if isinstance(x, unicode) else x
	return dict(map(ascii_encode, pair) for pair in data.items())

# Function to load the DB into memory
def get_db(fname):
	if not os.path.exists('database'):
		os.mkdir('database')
	if not os.path.exists(fname):
		f = open(fname, "w")
		f.write("{}")
		f.close()

	with open(fname) as json_data:
		data = json.load(json_data, object_hook=ascii_encode_dict)
	return data

def dump(data, fname):
	with open(fname, 'w') as outfile:  # Write out new data
		outfile.write(str(json.dumps(data))
		.replace("'", '"')
		.replace(', u"', ', "')
		.replace('[u"', '["')
		.replace('{u"', '{"')
		.encode('ascii','ignore'))

def decode(text):
        try:
		return text.encode('utf-8').decode('utf-8').encode('ascii', 'ignore').replace("\u002F", "/")
        except:
              	return text.decode('utf-8').encode('ascii', 'ignore').replace("\u002F", "/")

def get_mod_mail_messages(sub, num_messages):
	queries = []
	queries.append(sub.modmail.conversations(state='all', limit=num_messages))
	queries.append(sub.modmail.conversations(state='archived', limit=num_messages))
	return queries

def build_infraction_text(message, subject, subreddit_name, reddit):
	infraction = ""
	if subject == 'Your post from ' + subreddit_name + ' was removed' or subject == 'Your comment from ' + subreddit_name + ' was removed' or subject == "Your submission was removed from /r/" + subreddit_name or subject == "Your comment was removed from /r/" + subreddit_name:
		infraction = build_removal_reason_text(reddit, message, subject)
	elif subject == "You've been temporarily banned from participating in r/" + subreddit_name:
		try:
			days_banned = message.messages[0].body_markdown.split("This ban will last for ")[1].split(" ")[0]
			infraction = "BANNED - " + days_banned + " days."
		except:
			infraction = "BANNED - Unknown amount of time."
	elif subject == "You've been permanently banned from participating in r/" + subreddit_name:
		infraction = "PERM-BANNED"
	elif subject == "Your ban from r/" + subreddit_name + " has changed":
		if 'You have been permanently banned from participating in' in message.messages[0].body_markdown:
			infraction = "PERM-BANNED"
		else:
			days_banned = message.messages[0].body_markdown.split("This ban will last for ")[1].split(" ")[0]
			infraction = "CHANGED BAN - " + days_banned + " days."
	return decode(infraction)

def get_username_from_message(message):
	user = ""
	try:
		user = message.user.name
	except Exception as e:
		# Sometimes, the message is valid but any operations return a 404. Skip and continue if we see this.
		# Also, sometimes a message literally doesn't have a user attribute. See https://mod.reddit.com/mail/all/immhx
		print("Error for Mod Mail Message: " + str(message))
		print(str(e))
		print("======================================================================")
	return user

def build_removal_reason_text(reddit, message, subject):
	if "Your submission was removed from /r/" + subreddit_name == subject or "Your comment was removed from /r/" + subreddit_name == subject:
		infraction = message.messages[0].body_markdown.split(" - ")[0]
		if len(infraction) > 50:
			infraction = "Mod Tool Box Removal"
	else:
		infraction = "".join(message.messages[0].body_markdown.split("\n")[0].split("'")[1:])
	return infraction

def get_removing_mod(ids_to_mods, infraction, mod_conv):
	if infraction in ids_to_mods:
		removing_mod = ids_to_mods[infraction][0]
		ids_to_mods[infraction] = ids_to_mods[infraction][1:]
		return removing_mod
	else:
		return mod_conv.authors[-1].name


def get_summary_text(user_infraction_db, user, subreddit_name, removing_mod):
	replies = []
	removal_ids = user_infraction_db[user].keys()
	removal_ids.sort()
	replies = ["* " + user_infraction_db[user][removal_id] + " - https://mod.reddit.com/mail/all/" + removal_id for removal_id in removal_ids]
	removing_mod_text = "This action was performed by u/" + removing_mod + "\n\n---\n\n"
	return removing_mod_text + "History of u/" + user + " on r/" + subreddit_name + ":\n\n" + "\n\n".join(replies)

def send_reply(message, reply):
	if not debug:
		try:
			message.reply(reply, internal=True)
		except:
			print("Unable to reply to message " + str(message))
	else:
		print(reply)


def main(subreddit_name):
	reddit = praw.Reddit(client_id=client_id, client_secret=client_secret, user_agent='Mod Bot for ' + subreddit_name + ' v1.0 (by u/RegExr)', username=bot_username, password=bot_password)
	sub = reddit.subreddit(subreddit_name)
	if imgur_client and imgur_secret:
		try:
			imgur = ImgurClient(imgur_client, imgur_secret)
		except:
			imgur = None
	else:
		imgur = None
	try:
		mods = [str(x) for x in sub.moderator()]
	except Exception as e:
		print("Unable to get list of moderators from " + subreddit_name + " with error: " + str(e))
		return
	# Remove all submissions with mod reports and send removal reasons. Return a dict of who handeled each report.
	ids_to_mods = report.remove_reported_posts(sub, subreddit_name, lock_post)

	# Check posts for various violations
	frequency_fname = 'database/recent_posts-' + subreddit_name + '.txt'
	frequency_database = get_db(frequency_fname)
	submissions = post_checker.get_submissions(sub, num_posts_to_check)
	for submission in submissions:
		missing_flair = post_checker.handle_post_flair(submission, current_time, num_minutes_flair, subreddit_name)
		if missing_flair:  # We already removed so no need to check anything else
			continue

		# Ignore posts with whitelisted words
		title_and_flair = submission.title.lower()
		if submission.link_flair_text:
			title_and_flair += " - flair=" + submission.link_flair_text.lower()
		if whitelisted_words[0] and any([word in title_and_flair for word in whitelisted_words]):
			continue
		# Ignore posts made by mods
		author = str(submission.author)
		if author in mods:
			continue

		post_checker.handle_imgur_freshness(imgur, submission, sub, subreddit_name, imgur_freshness_days, current_time, bot_username, lock_post)
		post_checker.handle_post_frequency(submission, author, frequency_database, debug, days_between_posts, seconds_between_posts, lock_post)

	if not debug:
		dump(frequency_database, frequency_fname)

	# Begin handling modmail related actions
	infractions_fname = 'database/userbans-' + subreddit_name + '.json'
	try:
		user_infraction_db = get_db(infractions_fname)
	except:
		print("Unable to load database for " + infractions_fname)
		return
	queries = get_mod_mail_messages(sub, num_messages)

	for query in queries:
		try:
			mod_convs = [x for x in query]
		except Exception as e:
			print("Unable to read mod conversations from query on r/" + subreddit_name + " with error: " + str(e))
			continue
		for mod_conv in mod_convs:
			message = reddit.subreddit('redditdev').modmail(mod_conv.id)

			# Get the text of the infraction to store in the database
			infraction = build_infraction_text(message, mod_conv.subject, subreddit_name, reddit)

			# If no infracion was detected, we don't want to do anything
			if not infraction:
				continue
			infraction_and_date = str(datetime.datetime.now()).split(" ")[0] + " - " + infraction

			# Determine the username of the person in question
			user = get_username_from_message(message)

			# If we were unable to parse a username, just skip for now
			if not user:
				continue

			# If this is the user's first infraction, give them an entry in the db
			if user not in user_infraction_db:
				user_infraction_db[user] = {}

			# If we have seen this exact infraction before, skip it
			if mod_conv.id in user_infraction_db[user]:
				continue

			# Store the infraction in the database
			user_infraction_db[user][mod_conv.id] = infraction_and_date

			# Get the name of the mod who recorded the infraction
			removing_mod = get_removing_mod(ids_to_mods, infraction, mod_conv)

			# Save off the record of who handeled this infraction
			save_report_data(removing_mod, infraction, subreddit_name)

			# Handle replying to the message with our private summary
			reply = get_summary_text(user_infraction_db, user, subreddit_name, removing_mod)
			send_reply(message, reply)

			# Write off some info to the logs
			print(user + " - " + infraction_and_date + " - " + mod_conv.id + " - Removed by: " + removing_mod)
			print("===========================================")

	if not debug:
		dump(user_infraction_db, infractions_fname)


main(subreddit_name)









