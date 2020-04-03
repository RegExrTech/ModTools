import re
import report

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
	gallery = client.get_album_images(hash)
	return client.get_image(gallery[0].id)

def check_date(imgur, url, post_time, imgur_freshness_days):
	check_time = post_time - (imgur_freshness_days*24*60*60)
	url = url.split("?")[0]
	if url[-1] == "/":
		url = url[:-1]
	if url[-4] == ".":
		url = url [:-4]

	items = url.split("/")
	hash = items[-1]
	type = items[-2].lower()

	if type in ['gallery', 'a']:
		img = get_image_from_album(imgur, hash)
	else:
		img = imgur.get_image(hash)

	if img.datetime < check_time:
		return False
	return True

def extract_imgur_urls(text):
	match = re.compile("([\w_-]+(?:(?:\.[\w_-]+)+))([\w.,@?^=%&:/~+#-]*[\w@?^=%&/~+#-])?")
	return ["".join(x) for x in match.findall(text) if 'imgur' in x[0].lower()]

def check_imgur_freshness(imgur, sub, submission, imgur_freshness_days):
	text = submission.selftext
	imgur_urls = list(set(extract_imgur_urls(text)))
	if not imgur_urls:
		return
	if not any([check_date(imgur, url, submission.created_utc, imgur_freshness_days) for url in imgur_urls]):
		if report.remove_post(submission):
			removal_message = "This post has been removed because the following links contain out of date timestamps: \n\n" + "\n\n".join("* https://www." + url for url in imgur_urls + "\n\n---\n\n")
			report.send_removal_reason(submission, removal_message, "Timestamp out of date", "RegExrBot", {}, "FunkoSwap")

## OTHER

def get_submissions(sub, num_posts_to_check):
	return [x for x in sub.new(limit=num_posts_to_check)][::-1]

def handle_post_frequency(submission, author, frequency_database, debug, days_between_posts, seconds_between_posts):
	# Get timestamp info and make sure we have seen posts from this author before
	timestamp = submission.created_utc
	if author not in frequency_database:
		frequency_database[author] = 0

	# If this post was the most recent post from this author, then we have checked it before
	last_timestamp = frequency_database[author]
	if last_timestamp == timestamp:
		return

	# If we manage to see an older post after a newer post, skip the older post
	if last_timestamp > timestamp:
		return

	# If this post was made too recently
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
			frequency_database[author] = timestamp

def handle_imgur_freshness(imgur, submission, sub, subreddit_name, imgur_freshness_days, current_time):
	# Check for Imgur freshness
	last_imgur_post_check_timestamp = get_last_reddit_post_time_for_imgur_check(subreddit_name, current_time)
	if imgur_freshness_days > 0 and submission.created_utc > last_imgur_post_check_timestamp:
		check_imgur_freshness(imgur, sub, submission, imgur_freshness_days)
		update_last_reddit_post_time_for_imgur_check(subreddit_name, submission.created_utc)


def handle_post_flair(submission, current_time, num_minutes_flair):
	# Checks if flaired within time range
	missing_flair = submission.link_flair_text == None
	time_diff = current_time - submission.created_utc
	past_time_limit = time_diff > num_minutes_flair*60
	if missing_flair and past_time_limit:
		try:
			submission.mod.remove()
		except Exception as e:
			print("Unable to remove - " + str(e))
			return True
		try:
			reply = submission.reply("Hi there! Unfortunately your post has been removed as all posts must be flaired within " + str(num_minutes_flair) + " minutes of being posted.\n\nIf you're unfamiliar with how to flair please check the wiki on [how to flair your posts](https://www.reddit.com/r/funkopop/wiki/flairing) then feel free to repost.\n\n***\nI am a bot and this comment was left automatically and as a courtesy to you. \nIf you have any questions, please [message the moderators](https://www.reddit.com/message/compose?to=%2Fr%2Ffunkopop).")
			reply.mod.lock()
			reply.mod.distinguish(how="yes", sticky=True)
		except Exception as e:
			print("Unable to reply, lock, and distinguish - " + str(e))
		return  True
	return False
