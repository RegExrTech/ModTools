from datetime import datetime
from collections import defaultdict

cutoff_date = datetime.strptime("2019-10-01", "%Y-%m-%d")
#sub_name = "pkmntcgtrades"
sub_name= 'funkoswap'
sub_name = "Watchexchange"
#sub_name = "funkopop"
report_file_name = "database/report_log-" + sub_name + ".txt"

f = open(report_file_name, 'r')
lines = f.read().splitlines()
f.close()

reasons = defaultdict(lambda: 0)
mods = defaultdict(lambda: 0)
for line in lines:
	items = line.split(" - ")
	date = datetime.strptime(items[0], "%Y-%m-%d")
	mod = items[1]
	reason = items[2]

	if date < cutoff_date:
		continue

	print(str(date) + " - " + mod + " - " + reason)
	mods[mod] += 1
	reasons[reason] += 1

print("\nTotal removals: " + str(sum([mods[x] for x in mods])))
print("\n=====\n")
print("\n".join([str(x[0]) + " - " + str(x[1]) for x in sorted(mods.items(), key=lambda x: x[1], reverse=True)]))
print("\n=====\n")
print("\n".join([str(x[0]) + " - " + str(x[1]) for x in sorted(reasons.items(), key=lambda x: x[1], reverse=True)]))
