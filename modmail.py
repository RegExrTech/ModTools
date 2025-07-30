import sys
sys.path.insert(0, '.')
import time
import math
import os.path
from os import mkdir
import datetime
import sys
import praw
import report
import post_checker
import discord
from collections import defaultdict
import json
import argparse
import unidecode
import Config
import traceback
import requests

class Image(object):
	def __init__(self, *initial_data, **kwargs):
		for dictionary in initial_data:
			for key in dictionary:
				setattr(self, key, dictionary[key])
		for key in kwargs:
			setattr(self, key, kwargs[key])
def mock_get_image(hash, client_id):
	resp = requests.get("https://api.imgur.com/3/image/" + hash, headers={'Authorization': 'Client-ID ' + client_id}, proxies={'http': 'http://3.23.85.80:8888', 'https': 'https://3.23.85.80:8888'})
	return Image(resp.json()['data'])

debug = False

PERM_BANNED = "PERM-BANNED"
current_time = time.time()
num_messages = 10
num_posts_to_check = 20

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

def get_mod_mail_messages(config, num_messages, after):
	queries = []
	try:
		queries += [x for x in config.subreddit.modmail.conversations(state='all', limit=num_messages)]
		# TODO Fix the `after` param doing nothing here.
		queries += [x for x in config.subreddit.modmail.conversations(state='archived', limit=num_messages)]
	except Exception as e:
		discord.log("Unable to read mod conversations from query on r/" + config.subreddit_name, e)
	return queries

def build_infraction_text(config, message):
	subject = message.subject.lower()
	infraction = ""
	if any([subject in [x.lower() for x in ['Your post from ' + config.subreddit_name + ' was removed', 'Your comment from ' + config.subreddit_name + ' was removed', "Your submission was removed from /r/" + config.subreddit_name, "Your comment was removed from /r/" + config.subreddit_name]]]):
		infraction = build_removal_reason_text(config, message, subject)
	elif subject == ("You've been temporarily banned from participating in r/" + config.subreddit_name).lower():
		try:
			days_banned = message.messages[0].body_markdown.split("This ban will last for ")[1].split(" ")[0]
			infraction = "BANNED - " + days_banned + " days."
		except:
			infraction = "BANNED - Unknown amount of time."
	elif subject == ("You've been permanently banned from participating in r/" + config.subreddit_name).lower():
		infraction = PERM_BANNED
	elif ('is permanently banned from r/' + config.subreddit_name).lower() in subject:
		infraction = PERM_BANNED
	elif ('is temporarily banned from r/' + config.subreddit_name).lower() in subject:
		try:
			days_banned = message.messages[0].body_markdown.lower().split("r/" + config.subreddit_name + " for ")[1].split(" ")[0]
			infraction = "BANNED - " + days_banned + " days."
		except:
			infraction = "BANNED - Unknown amount of time."
	elif subject == ("Your ban from r/" + config.subreddit_name + " has changed").lower():
		if 'You have been permanently banned from participating in' in message.messages[0].body_markdown:
			infraction = PERM_BANNED
		else:
			try:
				days_banned = message.messages[0].body_markdown.split("This ban will last for ")[1].split(" ")[0]
				infraction = "CHANGED BAN - " + days_banned + " days."
			except:
				infraction = PERM_BANNED
	return unidecode.unidecode(infraction)

def get_username_from_message(message):
	user = ""
	try:
		if not message.user:
			user = ""
		else:
			user = message.user.name
	except Exception as e:
		if not "object has no attribute 'user'" in str(e):
			# Sometimes, the message is valid but any operations return a 404. Skip and continue if we see this.
			# Also, sometimes a message literally doesn't have a user attribute. See https://mod.reddit.com/mail/all/immhx
			discord.log("Error for Mod Mail Message: " + str(message), e, traceback.format_exc())
	return user

def build_removal_reason_text(config, message, subject):
	subject = subject.lower()
	if "your submission was removed from /r/" + config.subreddit_name == subject or "your comment was removed from /r/" + config.subreddit_name == subject:
		infraction = message.messages[0].body_markdown.split(" - ")[0]
		if len(infraction) > 50:
			infraction = "Mod Tool Box Removal"
	else:
		try:
			infraction = "".join(message.messages[0].body_markdown.split("\n")[0].split("'")[1:])
		except Exception as e:
			discord.log("Failed to build infraction for r/" + config.subreddit_name + " for message subject " + subject, e)
			infraction = ""
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

def send_reply(message, reply, internal=True):
	if not debug:
		try:
			message.reply(body=reply, internal=internal)
		except Exception as e:
			discord.log("Unable to reply to message: " + str(message), e, traceback.format_exc())
	else:
		print(reply)

def archive(message):
	if not debug:
		try:
			message.archive()
		except Exception as e:
			discord.log("Unable to archive message " + message.body, e, traceback.format_exc())
	else:
		print("Would have archived message:\n  " + str(message))

def main(config):
	try:
		mods = [str(x) for x in config.subreddit.moderator()]
	except Exception as e:
		discord.log("Unable to get list of moderators from " + config.subreddit_name, e)
		return
	# Remove all submissions with mod reports and send removal reasons. Return a dict of who handeled each report.
	if config.remove_from_reports:
		ids_to_mods = report.remove_reported_posts(config.subreddit, config.subreddit_name, config.lock_post)
	else:
		ids_to_mods = {}

	# Check posts for various violations
	frequency_fname = 'database/recent_posts-' + config.subreddit_name + '.json'
	frequency_database = get_db(frequency_fname)
	try:
		submissions = post_checker.get_submissions(config.subreddit, num_posts_to_check)
	except Exception as e:
		discord.log("Unable to get recent posts from r/" + config.subreddit_name, e)
		submissions = []
	for submission in submissions:
		missing_flair = post_checker.handle_post_flair(submission, current_time, config.num_minutes_flair, config.subreddit_name)
		if missing_flair:  # We already removed so no need to check anything else
			continue

		# Ignore posts with whitelisted words
		title_and_flair = submission.title.lower()
		if submission.link_flair_text:
			title_and_flair += " - flair=" + submission.link_flair_text.lower()
		if config.whitelisted_words and any([word in title_and_flair for word in config.whitelisted_words]):
			continue
		# Ignore posts made by mods
		author = str(submission.author)
		if author in mods:
			continue

		post_checker.handle_imgur_freshness(config.imgur, submission, config.subreddit, config.subreddit_name, config.imgur_freshness_days, current_time, config.bot_username, config.lock_post)
		post_checker.handle_post_frequency(config.reddit, submission, author, frequency_database, debug, config.hours_between_posts, config.lock_post, config.cooldown_hours)

	if not debug:
		dump(frequency_database, frequency_fname)

	# Begin handling modmail related actions
	infractions_fname = 'database/userbans-' + config.subreddit_name + '.json'
	try:
		user_infraction_db = get_db(infractions_fname)
	except Exception as e:
		discord.log("Unable to load database for " + infractions_fname, e, traceback.format_exc())
		return

	# Get the last-read mod mail ID so we don't do duplicate work.
	last_mod_mail_id_fname = "database/last_mod_mail_id_" + config.subreddit_name + ".txt"
	if not os.path.exists(last_mod_mail_id_fname):
		last_mod_mail_id = None
		last_mod_mail_time = 0
	else:
		with open("database/last_mod_mail_id_" + config.subreddit_name + ".txt") as f:
			t = f.read()
			last_mod_mail_id = t.split(" - ")[0]
			last_mod_mail_time = float(t.split(" - ")[1])
	most_recent_mod_mail_id = last_mod_mail_id
	mod_convs = get_mod_mail_messages(config, num_messages, last_mod_mail_id)
	failed = False
	for mod_conv in mod_convs:
		try:
			mod_conv_date = mod_conv.messages[0].date
		except Exception as e:
			if "500 HTTP response" in str(e):
				continue
			time.sleep(5)
			try:
				mod_conv_date = mod_conv.messages[0].date
			except Exception as e:
				discord.log("Unable to parse mod conv for r/" + config.subreddit_name + " - " + str(mod_conv) + " - Skipping iteration.", e)
				failed = True
				break
		# Handle updating the most recent mod mail stamp.
		mod_conv_time = float(datetime.datetime.strptime(mod_conv.messages[0].date, "%Y-%m-%dT%H:%M:%S.%f%z").timestamp())
		if mod_conv_time > last_mod_mail_time:
			last_mod_mail_time = mod_conv_time
			most_recent_mod_mail_id = mod_conv.id

		# Get the text of the infraction to store in the database
		infraction = build_infraction_text(config, mod_conv)

		# Determine the username of the person in question
		user = get_username_from_message(mod_conv)

		# If we were unable to parse a username, just skip for now
		if not user:
			continue

		# Handle infraction message
		if infraction:
			infraction_and_date = str(datetime.datetime.now()).split(" ")[0] + " - " + infraction

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
			save_report_data(removing_mod, infraction, config.subreddit_name)

			# Handle replying to the message with our private summary
			reply = get_summary_text(user_infraction_db, user, config.subreddit_name, removing_mod)
			send_reply(mod_conv, reply)

			# Archive if action is from USLBot. Prevents clutter in modmail
			if removing_mod == "USLBot" :
				archive(mod_conv)

			if infraction == PERM_BANNED:
				for copy_sub_name in config.copy_bans_to:
					try:
						config.reddit.subreddit(copy_sub_name).banned.add(user, ban_message="You have been banned from r/" + copy_sub_name + " due to a ban from r/" + config.subreddit_name)
						discord.log("Cross banned u/" + user + " from r/" + config.subreddit_name + " to r/" + copy_sub_name)
					except Exception as e:
						discord.log("Unable to cross ban u/" + user + " from r/" + config.subreddit_name + " to r/" + copy_sub_name, e, traceback.format_exc())

			# Write off some info to the logs
			print(user + " - " + infraction_and_date + " - " + mod_conv.id + " - Removed by: " + removing_mod + " on r/" + config.subreddit_name)
			print("===========================================")
		# Handle all other messages
		else:
			# If the message is a single mod mail message sent by a mod
			authors = [a.name for a in mod_conv.authors]
			if mod_conv.num_messages == 1 and any([x in authors for x in mods]):
				continue

			if not config.modmail_replies:
				continue
			# Should only reply to user inqueries once
			if len(mod_conv.messages) > 1:
				continue
			normalized_text = mod_conv.subject.lower() + " " + mod_conv.messages[0].body_markdown
			normalized_text = normalized_text.lower()
			normalized_text = " " + "".join([x if x.isalpha() else " " for x in normalized_text]) + " "
			normalized_text = normalized_text.replace(" * ", " ")
			replies = []
			for reply, keywords in config.modmail_replies.items():
				if any([(" " + x + " " in normalized_text) or x == '.' for x in keywords]):
					replies += [reply, "---"]
			if replies:
				generic_replies = [x for x in config.modmail_replies if "*" in config.modmail_replies[x]]
				for generic_reply in generic_replies:
					replies += [generic_reply, "---"]
				replies += ["If you require more information, or if this did not answer your question, please reply back to this message and a moderator will help you as quickly as possible!"]
				send_reply(mod_conv, "\n\n".join(replies), internal=False)
				archive(mod_conv)

	if not debug:
		dump(user_infraction_db, infractions_fname)
		if most_recent_mod_mail_id != last_mod_mail_id and not failed:
			with open(last_mod_mail_id_fname, 'w') as f:
				f.write(most_recent_mod_mail_id + " - " + str(last_mod_mail_time))

if __name__ == "__main__":
	try:
		parser = argparse.ArgumentParser()
		parser.add_argument('sub_name', metavar='C', type=str)
		args = parser.parse_args()
		CONFIG = Config.Config(args.sub_name.lower())
		if CONFIG.imgur:
			CONFIG.imgur.get_image = mock_get_image
		main(CONFIG)
	except Exception as e:
		discord.log("modmail.py failed with an uncaught exception for r/" + CONFIG.subreddit_name, e, traceback.format_exc())









