import datetime
from collections import defaultdict
import re
import report
import time

######################
##                  ##
## Helper Functions ##
##                  ##
######################

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
	try:
		gallery = client.get_album_images(hash)
		return client.get_image(gallery[0].id)
	except:
		return None

def check_date(imgur, url, post_time, imgur_freshness_days, newest_timestamp):
	check_time = post_time - (imgur_freshness_days*24*60*60)
	url = url.split("?")[0]
	if url[-1] == "/":
		url = url[:-1]
	if url[-4] == ".":
		url = url [:-4]

	items = url.split("/")
	hash = items[-1].replace("~", "")
	hash = hash.split("/comment")[0]  # if someone links to a comment on their imgur post, we get fucked
	type = items[-2].lower()

	try:
		if type in ['gallery', 'a']:
			img = get_image_from_album(imgur, hash)
		else:
			img = imgur.get_image(hash)
	except Exception as e:
		print("Failed to get images with the following hash: " + hash)
		print("    url: " + url)
		return True

	# If we can't find the hash for whatever reason, just skip this one.
	if not img:
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
	if not any([check_date(imgur, url, submission.created_utc, imgur_freshness_days, newest_timestamp) for url in imgur_urls]):
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

def get_submissions(sub, num_posts_to_check):
	return [x for x in sub.new(limit=num_posts_to_check)][::-1]

def handle_post_frequency(reddit, submission, author, frequency_database, debug, days_between_posts, seconds_between_posts, lock_post):
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

	# Filter out posts that were removed by automod
	# Do this AFTER checking timestamps above so we avoid making extranious reddit API calls
	new_post_data_list = []
	for post_data in frequency_database[author]:
		if not post_data['post_id']:
			new_post_data_list.append(post_data)
			continue
		if not reddit.submission(post_data['post_id']).banned_by == "AutoModerator":
			new_post_data_list.append(post_data)
	frequency_database[author] = new_post_data_list
	if len(frequency_database[author]) == 0:
		frequency_database[author] = [{'timestamp': timestamp, 'post_id': submission.id}]

	# Reset the last_timestamp variable as it might have changed after filtering out automod removed posts
	last_timestamp = frequency_database[author][-1]['timestamp']
	last_post_id = frequency_database[author][-1]['post_id']

	# If this post was made too recently and it was not previously approved
	delta = timestamp - last_timestamp
	if delta < seconds_between_posts and not submission.approved:
		if not debug:
			# Remove post
			submission.mod.remove()

			# Inform when user can post again: total_seconds_allowed - amount_of_time_between_post_attempts
			if days_between_posts == 1:
				time_string = "24 hours"
			else:
				time_string = str(days_between_posts) + " days"
			delta_string = str(datetime.timedelta(seconds=seconds_between_posts-delta))
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
				print("Unable to reply to post: redd.it/" + (submission.id) + " with error " + str(e))

			# Lock post
			if lock_post:
				submission.mod.lock()

			# Log some fun stuff
			print(author + " - " + datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")  + " - https://redd.it/" + submission.id + " - Violated posting frequency rule.")
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
		if time.time() - timestamp <= seconds_between_posts:
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
			print("Unable to remove - " + str(e))
			return True
		# Inform post removed
		try:
			reply = submission.reply("Hi there! Unfortunately your post has been removed as all posts must be flaired within " + str(num_minutes_flair) + " minutes of being posted.\n\nPlease feel free to repost with flair added to your post. Adding flair to yoir original post will do nothing.\n\n***\nI am a bot and this comment was left automatically and as a courtesy to you. \nIf you have any questions, please [message the moderators](https://www.reddit.com/message/compose?to=%2Fr%2F)" + subreddit_name + ".")
			reply.mod.lock()
			reply.mod.distinguish(how="yes", sticky=True)
		except Exception as e:
			print("Unable to reply, lock, and distinguish - " + str(e))
		return  True
	return False
