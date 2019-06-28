## Mod Tools

These are handy little mod tools for reddit moderators. Each tool will be described below. Please follow the setup guide if you wish to  run this on your own. If you wish to have your subreddit included in these tools, please contact [u/RegExr](https://www.reddit.com/r/regexr) on reddit.

### Setting up

First off, create a reddit account and give it full mod permissions in your sub. Then, create a script and generate the secret keys needed to log into PRAW.

Then, you'll need to make a config.txt file in a config directory. 

If no config directory exists, run `mkdir config`.

Once you have a directory, run `nano config/<your-sub-name>-config.txt` and enter the following information:

* Your subreddit name

* Your bot's client_id

* Your bot's secret_id

* Your bot's username

* Your bot's password

* The number of hours before a user can make consecutive posts (only if using the post_timeframe.py script)

With this config file set, you're ready to start running the scripts.

### modmail.py

This script parses through modmail and builds a database of removals and bans. The key features are as follows:

* Any mod report will result in a post removal and a removal reason sent in modmail.

  * By default, the removal reason will be equal to whatever the text is for your "rules" in your subreddit.

  * This feature is optional and won't run if mods never report posts on their own sub.

  * The usefullness of this feature comes into play for mobile moderating as you cannot send removal reasons easily from mobile reddit.

* Removal reasons and bans are parsed in mod mail and stored in a database.

* A private note is left on any new removal reasons or bans with a list of previous removals and bans with the following information:

  * The date of the removalor ban

  * The type of removal or ban

  * A link to the modmail message that came from that removal or ban

* New Reddit Removal Reasons and the Mod Toolbox (Web Extension) Removal Reasons are supporetd.

  * If using the mod toolbox, please add `<removal reason> - ` before each removal reason you configure with the name of the removal reason replacing <removal reason>


### post_timeframe.py

This script checks recent posts on your sub to see if anyone has been posting too frequently. Many subs only allow people to post every X days. Running this script will prevent people from making too many posts in your chosen timeframe. The key features are as follows:

* Any post made within the designated timeframe will be removed.

  * This does **NOT** reset the counter, so if a user posts too soon, the do not have to wait another full X days before posting again.

* Any post that is approved by a moderator will be ignored by the bot to give moderators control in special cases.

* Posts made by mods will be ignored by default.


### Suggested crontab Expressions

Run this using the crontab on your machine using `crontab -e`. The suggested expressions are as follows:

* `*/10 * * * * cd ~/ModTools && python post_timeframe.py <your-sub-name>-config.txt;`

* `*/2 * * * * cd ~/ModTools && python modmail.py <your-sub-name>-config.txt;`
