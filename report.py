import time
import removal_reasons
from collections import defaultdict

debug = False

def remove_reported_posts(sub, sub_name):
	ids_to_mods = defaultdict(lambda: [])
	try:
		reports = sub.mod.reports()
	except Exception as e:
		print("Unable to read reports for " + sub_name)
		print(e)
		return
        for item in reports:
                if item.mod_reports:
                        report_reason = item.mod_reports[0][0]
			mod_name = item.mod_reports[0][1]
                        try:
                                message = removal_reasons.removal_reasons[report_reason]['message']
                                title = removal_reasons.removal_reasons[report_reason]['title']
                        except Exception as e:  # If we were not able to get this information, it means that there is no removal reason set up and I should fix that
				message = ""
				title = report_reason
				for rule in sub.rules()['rules']:
					if rule['short_name'] == report_reason:
						message = rule['description']
				if not message:
	                                messasge = "Your post has been removed."
				message = "\n\n" + message + "\n\n---\n\nIf you have any questions or can make changes to your post that would allow it to be approved, please reply to this message.\n\n---\n\n"

			try:
	                        item.mod.remove()
			except Exception as e:
				print("Unable to remove post.")
				print(e)
				continue
			# Take three attempts at sending removal reason
			removal_reason_sent = False
			for i in range(3):
				if removal_reason_sent:
					break
				try:
		                        item.mod.send_removal_message(message, title=title, type='private')
					removal_reason_sent = True
					ids_to_mods[title].append(mod_name)
				except Exception as e:
					if i == 2:
						print("Unable to send removal reason.")
						print(e)
					else:
						time.sleep(3)
	return ids_to_mods

