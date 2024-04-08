import sys
sys.path.insert(0, ".")
import Config
import praw
from prawcore.exceptions import NotFound
import argparse



def main():
	parser = argparse.ArgumentParser()
	parser.add_argument('sub_name', metavar='C', type=str)
	args = parser.parse_args()
	config = Config.Config(args.sub_name.lower())

	# get recent sub comments
	comments_to_check = []
	try:
		new_comments = config.subreddit.comments(limit=50)
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
