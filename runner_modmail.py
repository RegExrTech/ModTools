import argparse
import time
import os
import random
import sys
sys.path.insert(0, '.')
import Config

parser = argparse.ArgumentParser()
parser.add_argument('subreddit_name', metavar='C', type=str)
args = parser.parse_args()
subreddit_name = args.subreddit_name.lower()

def main():
	while True:
		config = Config.Config(subreddit_name)
		if not config.enabled:
			return
		os.system('python3 modmail.py ' + subreddit_name)
		time.sleep(random.randint(60, 120))

main()
