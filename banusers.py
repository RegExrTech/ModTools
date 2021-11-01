"""
    This program is free software: you can redistribute it and/or modify
    it under the terms of the GNU General Public License as published by
    the Free Software Foundation, either version 3 of the License, or
    (at your option) any later version.

    This program is distributed in the hope that it will be useful,
    but WITHOUT ANY WARRANTY; without even the implied warranty of
    MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
    GNU General Public License for more details.

    You should have received a copy of the GNU General Public License
    along with this program.  If not, see <https://www.gnu.org/licenses/>.
"""

import praw
import json

def getbanned (r: praw.Reddit, subreddit: str) -> list :
    """
    Fetch banned users from a subreddit.

    Due to a Reddit API limitation this will fetch at most 100 users.
    """
    bannedlist = []
    for user in r.subreddit(subreddit).banned() :
        bannedlist.append(user.name)
    return bannedlist

def banusers (r : praw.Reddit, list: list, subreddit: str) -> None :
    """
    Mass-ban a list of users from a subreddit. Skips users that are already banned.
    """
    for user in list :
        if user not in r.subreddit(subreddit).banned() :
            r.subreddit('c4crep').banned.add(user)
            print ("Banned", user)

def writebanned (list: list, filename: str = 'banned.json') -> None :
    """
    Write the list of banned users to the disk

    This will overwrite the file if it exists.
    """
    try :
        with open(filename, 'x') as f :
            json.dump(list, f)
    except FileExistsError : #janky but functional solution to avoid importing the os library
        with open(filename, 'w') as f :
            json.dump(list, f)

def readbanned (filename: str = 'banned.json') -> list :
    """
    Read the list of banned users from the disk
    """
    with open(filename, "r") as f :
        return json.load(f)