# coding=utf-8
from __future__ import absolute_import
import octoprint.plugin
import threading
import time
import json

from .server_conn import ServerConnection

class MonitoringPlugin(octoprint.plugin.SettingsPlugin,
                     octoprint.plugin.AssetPlugin,
                     octoprint.plugin.EventHandlerPlugin,
                     octoprint.plugin.TemplatePlugin,
                     octoprint.plugin.StartupPlugin,
                     octoprint.plugin.ShutdownPlugin,
                     octoprint.plugin.SimpleApiPlugin,
                     octoprint.plugin.WizardPlugin):

	def on_after_startup(self):
		self._logger.info("Hello, this is monitoring from zahradka")
		self.ss = ServerConnection(
					url = "ws://127.0.0.1:8765",
					on_server_ws_msg=self.__on_server_ws_msg__)

		wst = threading.Thread(target=self.ss.run)
		wst.daemon = True
		wst.start()

		data = {
			"source": "octoprint"
		}

		time.sleep(2)
		if self.ss.connected():
			self.ss.send_text(json.dumps(data))
		while self.ss.connected():
			self.send_data()
			time.sleep(2)

	def __on_server_ws_msg__(self, ws, msg):
		msg_dict = json.loads(msg)
		for k, v in msg_dict.items():
			if k == 'source':
				files = self._file_manager.list_files();
				files['origin'] = 'octoprint';
				self.ss.send_text(json.dumps(files))
		if cmd == 'pause':
			self._printer.pause_print()
		elif cmd == 'cancel':
			self._printer.cancel_print()
		elif cmd == 'resume':
			self._printer.resume_print()

	def send_data(self):
		try:
			data = self._printer.get_current_data()
			data['temps'] = self._printer.get_current_temperatures()
			data['origin'] = 'octoprint'
			self.ss.send_text(json.dumps(data))
		except:
			import traceback;
			traceback.print_exc()

	# def on_event(self, event, payload):
	# 	if event.startswith("Print"):
	# 		self._logger.info("neco se deje s tiskarnou")
	# 		try:
	# 			data = self._printer.get_current_data()
	# 			data['temps'] = self._printer.get_current_temperatures()
	# 		except:
	# 			import traceback;
	# 			traceback.print_exc()
	#
	# 		self._logger.info(format(data))

	# websocket.enableTrace(True)
	# self.ws = websocket.WebSocketApp(url="ws://127.0.0.1:8765",
	# 								 on_message=self.on_message,
	# 								 on_error=self.on_error)
	# self.ws.on_open = self.on_open(event)
	# self.ws.run_forever()



	##~~ SettingsPlugin mixin

	def get_settings_defaults(self):
		return dict(
			# put your plugin's default settings here
		)

	##~~ AssetPlugin mixin

	def get_assets(self):
		# Define your plugin's asset files to automatically include in the
		# core UI here.
		return dict(
			js=["js/monitoring.js"],
			css=["css/monitoring.css"],
			less=["less/monitoring.less"]
		)

	##~~ Softwareupdate hook

	def get_update_information(self):
		# Define the configuration for your plugin to use with the Software Update
		# Plugin here. See https://docs.octoprint.org/en/master/bundledplugins/softwareupdate.html
		# for details.
		return dict(
			monitoring=dict(
				displayName="Monitoring Plugin",
				displayVersion=self._plugin_version,

				# version check: github repository
				type="github_release",
				user="jkudlacek",
				repo="OctoPrint-Monitoring",
				current=self._plugin_version,

				# update method: pip
				pip="https://github.com/jkudlacek/OctoPrint-Monitoring/archive/{target_version}.zip"
			)
		)


#Plugin declarations
__plugin_name__ = "Printer Monitor"
__plugin_pythoncompat__ = ">=3,<4" # only python 3
#__plugin_pythoncompat__ = ">=2.7,<4" # python 2 and 3

def __plugin_load__():
	global __plugin_implementation__
	__plugin_implementation__ = MonitoringPlugin()

	global __plugin_hooks__
	__plugin_hooks__ = {
		"octoprint.plugin.softwareupdate.check_config": __plugin_implementation__.get_update_information
	}

