import removal_reasons

debug = False

def remove_reported_posts(sub):
        for item in sub.mod.reports():
                if item.mod_reports:
                        report_reason = item.mod_reports[0][0]
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
	                                continue
				message = "\n\n" + message + "\n\n---\n\nIf you have any questions or can make changes to your post that would allow it to be approved, please reply to this message.\n\n---\n\n"

			try:
	                        item.mod.remove()
			except Exception as e:
				print("Unable to remove post.")
				print(e)
			try:
	                        item.mod.send_removal_message(message, title=title, type='private')
			except Exception as e:
				print("Unable to send removal reason.")
				print(e)
