import time
import praw
from collections import defaultdict

debug = False

def decode(text):
        try:
                return text.encode('utf-8').decode('utf-8').encode('ascii', 'ignore').replace("\u002F", "/")
        except:
                return text.decode('utf-8').encode('ascii', 'ignore').replace("\u002F", "/")

def get_reports(sub, sub_name):
	try:
		return sub.mod.reports()
	except Exception as e:
		print("Unable to read reports for " + sub_name)
#		print(e)
		return []

def get_rule_text(report_reason, sub):
	for rule in sub.rules()['rules']:
		if rule['short_name'] == report_reason:
			return "\n\n" + rule['description']
	return "\n\nYour post has been removed."

def get_submission_text(item):
	if "poll_data" in dir(item):  # Submission Post
		return "Title: " + item.title + "\n\nBody: " + item.selftext + "\n\nPoll Options: \n\n* " + "\n\n* ".join([option['text'] for option in item.poll_data['options']])
	elif isinstance(item, praw.models.Submission):
		if item.is_self:  # Text Post
			return "Title: " + item.title + "\n\nBody: " + item.selftext
		else:  # Link post
			return "Title: " + item.title + "\n\nLink: " + item.url
	else:  # Comment
		return "Comment: " + item.body

def remove_post(item, lock_post):
	try:
		item.mod.remove()
	except:
		print("Unable to remove post.")
		print(e)
		return False
	if lock_post:
		try:
			item.mod.lock()
		except:
			print("Unable to lock offender: " + str(item))
	return True

def send_removal_reason(item, message, title, mod_name, ids_to_mods, sub_name):
	title = title[:50]
	removal_reason_sent = False
	message = message[:8096]  # Reddit has a hard limit of 8096 characters for messages, so ensure we cap it here.
	for i in range(3):  # Take three attempts at sending removal reason
		if removal_reason_sent:
			break
		try:
			item.mod.send_removal_message(message, title=title, type='private')
			removal_reason_sent = True
		except Exception as e:
			if i == 2:
				print("Unable to send removal reason for sub " + sub_name + ":\nTitle: " + title + "\nMessage: \n" + str(message))
				print(e)
			else:
				print("Failed to send removal message to " + sub_name +  "\nSleeping for 3 seconds and trying again...")
				time.sleep(3)
	ids_to_mods[title].append(mod_name)

def truncate_text(text, limit):
	if len(text) >= limit:
		return text[:limit] + "\n\nTruncated..."
	return text

def remove_reported_posts(sub, sub_name, lock_post):
	ids_to_mods = defaultdict(lambda: [])
        for item in get_reports(sub, sub_name):
                if not item.mod_reports:
			continue
		if item.approved:
			continue
		report_reason = item.mod_reports[0][0]
		# This is technically not a report even though it appears as one so we want to ignore it.
		if report_reason == "It's abusing the report button":
			continue
		if report_reason == "It's targeted harassment at me":
			report_reason = "Review the rules"
		title = report_reason
		message = get_rule_text(report_reason, sub)
		submission_text = get_submission_text(item)
		submission_text = truncate_text(submission_text, 7800)

		message += "\n\n---\n\n" + submission_text
		message += "\n\n---\n\nIf you can make changes to your post that would allow it to be approved, please do so, then reply to this message. If the issue with your post is in the title, please make a new post following the rules of the sub as post titles cannot be changed..\n\n---\n\n"
		message = decode(message)

		if remove_post(item, lock_post):
			send_removal_reason(item, message, title, item.mod_reports[0][1], ids_to_mods, sub_name)

	return ids_to_mods

