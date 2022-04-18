import praw
from prawcore.exceptions import NotFound
import argparse


def create_reddit_and_sub(subreddit_name, client_id, client_secret, bot_username, bot_password):
	reddit = praw.Reddit(client_id=client_id, client_secret=client_secret, user_agent='Swap Bot for ' + subreddit_name + ' v1.0 (by u/RegExr)', username=bot_username, password=bot_password)
	sub = reddit.subreddit(subreddit_name)
	return reddit, sub

def main():
	parser = argparse.ArgumentParser()
	parser.add_argument('sub_name', metavar='C', type=str)
	args = parser.parse_args()

	config_fname = 'config/' + args.sub_name + "-config.txt"
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

	reddit, sub = create_reddit_and_sub(subreddit_name, client_id, client_secret, bot_username, bot_password)

	# get recent sub comments
	comments_to_check = []
	try:
		new_comments = sub.comments(limit=50)
		for new_comment in new_comments:
			try:
				new_comment.refresh()
			except: # if we can't refresh a comment, ignore it.
				continue
			if new_comment.banned_by:
				continue  # Skip comments that were already removed
			if new_comment.author.name.lower() == "automoderator":
				comments_to_check.append(new_comment)
	except Exception as e:
		print("Failed to get new comments with error " + str(e))

	for comment in comments_to_check:
		if '#***X5***' not in comment.body:
			continue
		parent_comment = comment.parent()
		author = parent_comment.author
		should_remove = False
		try:
			author.id
		except NotFound:
			should_remove = True
		except AttributeError:
			should_remove = True
		if should_remove:
			comment.mod.remove()
			parent_post = comment
			top_level_comment = comment
			while parent_post.__class__.__name__ == "Comment":
				top_level_comment = parent_post
				parent_post = parent_post.parent()
			print("Removed automod comment reddit.com/comments/"+str(parent_post)+"/-/"+str(comment))

if __name__ == "__main__":
	main()
