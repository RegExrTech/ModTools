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
import unidecode

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
refresh_token = config['refresh_token']
hours_between_posts = int(round(float(config['days_per_post'])*24))
lock_post = config['lock_post'].lower() == "true"
whitelisted_words = [x.lower() for x in config['whitelisted_words'].split(',')]
num_minutes_flair = float(config['minutes_no_flair'])
imgur_freshness_days = float(config['imgur_freshness_days'])
imgur_client = config['imgur_client']
imgur_secret = config['imgur_secret']
copy_bans_to = [x for x in config['copy_bans_to'].split(",") if x]
remove_from_reports = config['remove_from_reports'].lower() == "true"

debug = False

PERM_BANNED = "PERM-BANNED"
current_time = time.time()
num_messages = 10
num_posts_to_check = 100

def save_report_data(mod_name, report_reason, sub_name):
	f = open('database/report_log-' + sub_name + ".txt", 'a')
	f.write(str(datetime.datetime.now()).split(" ")[0] + " - " + mod_name + " - " + report_reason + "\n")
	f.close()

# Function to load the DB into memory
def get_db(fname):
	if not os.path.exists('database'):
		os.mkdir('database')
	if not os.path.exists(fname):
		f = open(fname, "w")
		f.write("{}")
		f.close()

	if fname.endswith('.json'):
		with open(fname, 'r') as json_data:
			data = json.load(json_data)
	else:
		with open(fname, 'r') as text_data:
			data = text_data.read()
	return data

def dump(data, fname):
	if fname.endswith('.json'):
		with open(fname, 'w') as outfile:  # Write out new data
			outfile.write(json.dumps(data, sort_keys=True, indent=4))
	else:
		with open(fname, 'w') as outfile:  # Write out new data
			outfile.write(data)

def decode(text):
	return unidecode.unidecode(text)

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
		infraction = PERM_BANNED
	elif 'is permanently banned from r/' + subreddit_name in subject:
		infraction = PERM_BANNED
	elif 'is temporarily banned from r/' + subreddit_name in subject:
		try:
			days_banned = message.messages[0].body_markdown.split("r/" + subreddit_name + " for ")[1].split(" ")[0]
			infraction = "BANNED - " + days_banned + " days."
		except:
			infraction = "BANNED - Unknown amount of time."
	elif subject == "Your ban from r/" + subreddit_name + " has changed":
		if 'You have been permanently banned from participating in' in message.messages[0].body_markdown:
			infraction = PERM_BANNED
		else:
			try:
				days_banned = message.messages[0].body_markdown.split("This ban will last for ")[1].split(" ")[0]
				infraction = "CHANGED BAN - " + days_banned + " days."
			except:
				infraction = PERM_BANNED
	return decode(infraction)

def get_username_from_message(message):
	user = ""
	try:
		user = message.user.name
	except Exception as e:
		if not "object has no attribute 'user'" in str(e):
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
	if infraction in ids_to_mods and len(ids_to_mods[infraction]):
		removing_mod = ids_to_mods[infraction][0]
		ids_to_mods[infraction] = ids_to_mods[infraction][1:]
		return removing_mod
	else:
		return mod_conv.messages[-1].author.name


def get_summary_text(user_infraction_db, user, subreddit_name, removing_mod):
	if user == "[deleted]":
		return "This user has deleted their account."
	replies = []
	removal_ids = user_infraction_db[user].keys()
	replies = ["* " + user_infraction_db[user][removal_id] + " - https://mod.reddit.com/mail/all/" + removal_id for removal_id in removal_ids]
	replies.sort()
	removing_mod_text = "This action was performed by u/" + removing_mod + "\n\n---\n\n"
	return removing_mod_text + "History of u/" + user + " on r/" + subreddit_name + ":\n\n" + "\n\n".join(replies)

def send_reply(message, reply):
	if not debug:
		try:
			message.reply(body=reply, internal=True)
		except Exception as e:
			print("Unable to reply to message:\n  " + str(message) + "\nwith error:\n" + str(e))
	else:
		print(reply)

def archive(message):
	if not debug:
		try:
			message.archive()
		except:
			print ("Unable to archive message " + message.body)
	else:
		print("Would have archived message:\n  " + str(message))

def main(subreddit_name):
	reddit = praw.Reddit(client_id=client_id, client_secret=client_secret, user_agent='Mod Bot for ' + subreddit_name + ' v1.0 (by u/RegExr)', refresh_token=refresh_token)
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
	if remove_from_reports:
		ids_to_mods = report.remove_reported_posts(sub, subreddit_name, lock_post)
	else:
		ids_to_mods = {}

	# Check posts for various violations
	frequency_fname = 'database/recent_posts-' + subreddit_name + '.json'
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
		post_checker.handle_post_frequency(reddit, submission, author, frequency_database, debug, hours_between_posts, lock_post)

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
			message = reddit.subreddit(subreddit_name).modmail(mod_conv.id)

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

			# Archive if action is from USLBot. Prevents clutter in modmail
			if removing_mod == "USLBot" :
				archive(message)

			if infraction == PERM_BANNED:
				for copy_sub_name in copy_bans_to:
					try:
						reddit.subreddit(copy_sub_name).banned.add(user, ban_message="You have been banned from r/" + copy_sub_name + " due to a ban from r/" + subreddit_name)
						print("Cross banned to r/" + copy_sub_name)
					except Exception as e:
						print("Unable to cross ban to r/" + copy_sub_name + ": " + str(e))

			# Write off some info to the logs
			print(user + " - " + infraction_and_date + " - " + mod_conv.id + " - Removed by: " + removing_mod + " on r/" + subreddit_name)
			print("===========================================")

	if not debug:
		dump(user_infraction_db, infractions_fname)


main(subreddit_name)









