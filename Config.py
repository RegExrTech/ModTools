import praw
import os
import json
from imgurpython import ImgurClient

def get_json_data(fname):
	with open(fname) as json_data:
		data = json.load(json_data)
	return data

def dump(db, fname):
	with open(fname, 'w') as outfile:  # Write out new data
		outfile.write(json.dumps(db, sort_keys=True, indent=4))

class Config():

	def __init__(self, sub_name):
		self.fname = "config/" + sub_name.lower() + ".json"
		self.raw_config = get_json_data(self.fname)

		self.subreddit_name = self.raw_config['subreddit_name'].lower()
		self.client_id = self.raw_config['client_id']
		self.client_secret = self.raw_config['client_secret']
		self.bot_username = self.raw_config['bot_username']
		self.bot_password = self.raw_config['bot_password']
		self.refresh_token = self.raw_config['refresh_token']
		self.reddit = praw.Reddit(client_id=self.client_id, client_secret=self.client_secret, user_agent='Swap Bot for ' + self.subreddit_name + ' v1.0 (by u/RegExr)', refresh_token=self.refresh_token)
		self.subreddit = self.reddit.subreddit(self.subreddit_name)
		self.hours_between_posts = self.raw_config['hours_between_posts']
		self.lock_post = self.raw_config['lock_post']
		self.whitelisted_words = self.raw_config['whitelisted_words']
		self.num_minutes_flair = self.raw_config['num_minutes_flair']
		if self.num_minutes_flair <= 0:
			self.num_minutes_flair = float('inf')
		self.imgur_freshness_days = self.raw_config['imgur_freshness_days']
		self.imgur_client = self.raw_config['imgur_client']
		self.imgur_secret = self.raw_config['imgur_secret']
		try:
			if self.imgur_client and self.imgur_secret:
				self.imgur = ImgurClient(self.imgur_client, self.imgur_secret)
			else:
				self.imgur = None
		except:
			self.imgur = None
		self.copy_bans_to = self.raw_config['copy_bans_to']
		self.remove_from_reports = self.raw_config['remove_from_reports']
		self.enabled = self.raw_config['enabled']
