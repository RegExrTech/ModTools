import sys
sys.path.insert(0, '.')
import discord
import datetime
from collections import defaultdict
import re
import report
import time
import traceback

## IMGUR RELATED

def get_last_reddit_post_time_for_imgur_check(sub_name, current_time):
	try:
		f = open("database/imgur_check_" + sub_name + ".txt", "r")
		text = f.read()
		f.close()
		return float(text)
	except:
		update_last_reddit_post_time_for_imgur_check(sub_name, current_time)
		return current_time

def update_last_reddit_post_time_for_imgur_check(sub_name, current_time):
	f = open("database/imgur_check_" + sub_name + ".txt", "w")
	f.write(str(current_time))
	f.close()

def get_image_from_album(client, hash):
	gallery = client.get_album_images(hash.split("-")[-1])
	return client.get_image(gallery[0].id, client.client_id)

def check_date(imgur, url, post_time, imgur_freshness_days, newest_timestamp, submission):
	check_time = post_time - (imgur_freshness_days*24*60*60)
	url = url.split("?")[0]
	if url[-1] == "/":
		url = url[:-1]
	if url[-4] == ".":  # e.g. hash.jpg
		url = url [:-4]
	elif url[-5] == ".":  # e.g. hash.jpeg
		url = url [:-5]

	items = url.split("/")
	if len(items) <= 1:
		discord.log("Found an imgur URL that didn't have enough information to parse: " + url + " - Not checking it.")
		return True
	hash = items[-1].replace("~", "")
	hash = hash.split("/comment")[0]  # if someone links to a comment on their imgur post, we get fucked
	type = items[-2].lower()

	try:
		if type in ['gallery', 'a']:
			img = get_image_from_album(imgur, hash)
		else:
			img = imgur.get_image(hash, imgur.client_id)
	except Exception as e:
		if 'rate-limit' not in str(e).lower():
			discord.log("Failed to get images from https://www.reddit.com" + submission.permalink + " with hash [" + hash + "] and type " + type + " and url https://" + url, e, traceback.format_exc())
		return True

	# If we can't find the hash for whatever reason, just skip this one.
	if not img:
		return True

	try:
		img.datetime
	except Exception as e:
		discord.log("Error parsing submission https://www.reddit.com" + submission.permalink, e)
		return True
	if newest_timestamp[0] < img.datetime:
		newest_timestamp[0] = img.datetime

	if img.datetime < check_time:
		return False
	return True

def extract_imgur_urls(text):
	match = re.compile("([\w_-]+(?:(?:\.[\w_-]+)+))([\w.,@?^=%&:/~+#-]*[\w@?^=%&/~+#-])?")
	return ["".join(x) for x in match.findall(text) if 'imgur' in x[0].lower()]

def check_imgur_freshness(imgur, sub, submission, imgur_freshness_days, subreddit_name, bot_username, lock_post):
	text = submission.selftext
	imgur_urls = list(set(extract_imgur_urls(text)))
	if not imgur_urls:
		return
	newest_timestamp = [0]
	# Check each one at a time and break early to avoid rate limiting from imgur
	found_at_least_one_recent_timestamp = len(imgur_urls) == 0  # If there are no imgur URLs, then set this var to True and skip the rest of the logic
	for url in imgur_urls:
		found_at_least_one_recent_timestamp = check_date(imgur, url, submission.created_utc, imgur_freshness_days, newest_timestamp, submission)
		if found_at_least_one_recent_timestamp:
			break
	if not found_at_least_one_recent_timestamp:
		if report.remove_post(submission, lock_post):
			upload_string = str(datetime.timedelta(seconds=submission.created_utc - newest_timestamp[0]))
			upload_string = upload_string.replace(":", " hours, ", 1)
			upload_string = upload_string.replace(":", " minutes, and ", 1)
			upload_string += " seconds"
			stale_delta_string = str(datetime.timedelta(seconds=submission.created_utc - newest_timestamp[0] - (imgur_freshness_days*24*60*60)))
			stale_delta_string = stale_delta_string.replace(":", " hours, ", 1)
			stale_delta_string = stale_delta_string.replace(":", " minutes, and ", 1)
			stale_delta_string += " seconds"
			removal_message = "This post has been removed because the following links contain out of date timestamps: \n\n" + "\n\n".join("* https://www." + url for url in imgur_urls) + "\n\n"
			removal_message += "The newest image was uploaded " + upload_string  + " before this reddit post was made.\n\n"
			removal_message += "This means that your most recent submission is " + stale_delta_string + " past the allowed limit of " + str(int(imgur_freshness_days)) + " days from when this post was first made.\n\n"
			removal_message += "\n\n---\n\n"
			report.send_removal_reason(submission, removal_message, "Timestamp out of date", bot_username, defaultdict(lambda: []), subreddit_name)

## OTHER

def get_submissions(sub, num_posts_to_check, last_post_id=""):
	posts = []
	# Submissions come in from newest to oldest
	# Once we find the last post ID, anything "older" than that has been checked already
	for submission in sub.new(limit=num_posts_to_check):
		if submission.id != last_post_id:
			posts.append(submission)
		else:
			break
	# Return posts in order from oldest to newest
	return posts[::-1]

def handle_post_frequency(reddit, submission, author, frequency_database, debug, hours_between_posts, lock_post, cooldown_hours):
	# Posts that have been automatically removed by automod shouldn't be counted.
	if submission.banned_by == "AutoModerator":
		return

	# Get timestamp info and make sure we have seen posts from this author before
	timestamp = submission.created_utc
	if author not in frequency_database or frequency_database[author] == []:
		frequency_database[author] = [{'timestamp': timestamp, 'post_id': submission.id}]

	# If this post was the most recent post from this author, then we have checked it before
	last_timestamp = frequency_database[author][-1]['timestamp']
	if last_timestamp == timestamp:
		return

	# If we manage to see an older post after a newer post, skip the older post
	if last_timestamp > timestamp:
		return

	# Filter out posts that were removed by automod or deleted within the cooldown.
	# Do this AFTER checking timestamps above so we avoid making extranious reddit API calls
	new_post_data_list = []
	for post_data in frequency_database[author]:
		if not post_data['post_id']:
			new_post_data_list.append(post_data)
			continue
		_post = reddit.submission(post_data['post_id'])
		# If there is a cooldown and the post was (deleted or removed) during the cooldown, then it does not count against the limits.
		if cooldown_hours and (not _post.author or not _post.is_robot_indexable) and (post_data['timestamp'] + (cooldown_hours * 60 * 60) > time.time()):
			continue
		# If automod never removed OR reported the post, then this counts against the user's posting limit
		try:
			_reporting_mods = [x[1] for x in _post.mod_reports_dismissed]
		except:
			_reporting_mods = []
		if not _post.banned_by == "AutoModerator" and "AutoModerator" not in _reporting_mods:
			new_post_data_list.append(post_data)
	frequency_database[author] = new_post_data_list

	# If the user has no post history after clearing out automod-removed posts,
	# add a dummy post so the rest of the code will work.
	if len(frequency_database[author]) == 0:
		frequency_database[author] = [{'timestamp': 0, 'post_id': submission.id}]

	# Reset the last_timestamp variable as it might have changed after filtering out automod removed posts
	last_timestamp = frequency_database[author][-1]['timestamp']
	last_post_id = frequency_database[author][-1]['post_id']

	# If this post was made too recently and it was not previously approved
	delta = timestamp - last_timestamp
	if delta < (hours_between_posts*60*60) and not submission.approved:
		if not debug:
			# Remove post
			submission.mod.remove()

			# Inform when user can post again: total_seconds_allowed - amount_of_time_between_post_attempts
			if hours_between_posts <= 24:
				time_string = str(hours_between_posts) + " hours"
			else:
				_days = hours_between_posts / 24
				_hours = hours_between_posts % 24
				time_string = str(_days) + " days"
				if _hours > 0:
					time_string += " and " + str(_hours) + " hours"
			delta_string = str(datetime.timedelta(seconds=(hours_between_posts*60*60)-delta))
			delta_string = delta_string.replace(":", " hours, ", 1)
			delta_string = delta_string.replace(":", " minutes, and ", 1)
			delta_string += " seconds"

			reply_text = "This post has been removed because you have made more than one post in " + time_string + ". "
			if last_post_id:
				reply_text += "You can find your most recent post [here](https://redd.it/" + last_post_id  + "). "
			reply_text += "You can make another post in " + delta_string + "."
			reply_text += "\n\nIf you're seeing this message because your previous post was removed for rule violations, please modify the removed post rather than making a new post. Then let the moderators know once you've done so and they will approve your post."
			try:
				reply = submission.reply(reply_text)
				reply.mod.distinguish(sticky=True)
				reply.mod.lock()
			except Exception as e:
				discord.log("Unable to reply to post https://redd.it/" + submission.id, e, traceback.format_exc())

			# Lock post
			if lock_post:
				submission.mod.lock()

			# Log some fun stuff
			print(author + " - " + datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")  + " - https://redd.it/" + submission.id + " - Violated posting frequency rule on r/" + submission.subreddit.display_name)
			print("===========================================")
		else:
			print("Would have removed post " + submission.id)
	else: # If this is a new post and is valid, update the saved timestamp
		if timestamp > last_timestamp:
			frequency_database[author].append({'timestamp': timestamp, 'post_id': submission.id})

	# Remove any posts from the user history that are past the frequency threshold
	new_post_data_list = []
	for post_data in frequency_database[author]:
		timestamp = post_data['timestamp']
		if time.time() - timestamp <= hours_between_posts*60*60:
			new_post_data_list.append(post_data)
	frequency_database[author] = new_post_data_list

def handle_imgur_freshness(imgur, submission, sub, subreddit_name, imgur_freshness_days, current_time, bot_username, lock_post):
	# Check for Imgur freshness
	last_imgur_post_check_timestamp = get_last_reddit_post_time_for_imgur_check(subreddit_name, current_time)
	if imgur_freshness_days > 0 and submission.created_utc > last_imgur_post_check_timestamp:
		check_imgur_freshness(imgur, sub, submission, imgur_freshness_days, subreddit_name, bot_username, lock_post)
		update_last_reddit_post_time_for_imgur_check(subreddit_name, submission.created_utc)


def handle_post_flair(submission, current_time, num_minutes_flair, subreddit_name):
	# Checks if flaired within time range
	missing_flair = submission.link_flair_text == None
	time_diff = current_time - submission.created_utc
	past_time_limit = time_diff > num_minutes_flair*60
	if missing_flair and past_time_limit:
		# Remove post
		try:
			submission.mod.remove()
		except Exception as e:
			discord.log("unable to remove submission https://redd.it/" + submission.id, e, traceback.format_exc())
			return True
		# Inform post removed
		try:
			reply = submission.reply("Hi there! Unfortunately your post has been removed as all posts must be flaired within " + str(num_minutes_flair) + " minutes of being posted.\n\nPlease feel free to repost with flair added to your post. Adding flair to yoir original post will do nothing.\n\n***\nI am a bot and this comment was left automatically and as a courtesy to you. \nIf you have any questions, please [message the moderators](https://www.reddit.com/message/compose?to=%2Fr%2F" + subreddit_name + ").")
			reply.mod.lock()
			reply.mod.distinguish(how="yes", sticky=True)
		except Exception as e:
			discord.log("Unable to reply, lock, and/or distingush on post https://redd.it/" + submission.id, e, traceback.format_exc())
		return  True
	return False
