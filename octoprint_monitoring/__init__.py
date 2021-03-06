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
	# Proměnná představuje připojeného klienta ve webové aplikaci, jestli se nedívá je nastavená na False
	watching = False
	# Možné vzdálenosti jednoho kroku
	steps = ["0.1", "1", "10", "50", "100"]

	def on_after_startup(self):
		self._logger.info("Monitoring started")
		# Hodnoty pro připojení k serveru
		self.ss = ServerConnection(
			url=self._settings.get(["url"]),
			on_server_ws_msg=self.__on_server_ws_msg__)
		# Začne nové vlákno pro běh na pozadí
		wst = threading.Thread(target=self.ss.run)
		wst.daemon = True
		wst.start()

		# Obsah první zprávy, dává serveru vědět adresu zdroje
		data = {"source": "octoprint"}

		# Čas pro navázaní spojení
		time.sleep(2)
		if self.ss.connected():
			# Pošle první zprávu obsahující zdroj odesílatele
			self.ss.send_text(json.dumps(data))
		while self.ss.connected():
			# Aktualizace stavu dokud je websocket spojení navázané
			if (self.watching):
				self.send_data()
			# 	Interval ve kterém se posílají aktualizace
			time.sleep(self._settings.get(["interval"]))

	# Funkce starající se o příchozí zprávy
	def __on_server_ws_msg__(self, ws, msg):
		# Načtení zprávy do pole
		msg_dict = json.loads(msg)
		for k, v in msg_dict.items():
			# První zpráva od klienta nebo žádost o seznam souborů
			if k == "source" or k == "file_reload":
				# Pošle seznam souborů
				files = self._file_manager.list_files()
				files["origin"] = "octoprint"
				self.ss.send_text(json.dumps(files))

				if k == "source":
					# V případě první zprávy pošle seznam možných portů a rychlostí připojení k tiskárně
					connect_opts = self._printer.get_connection_options()
					connect_opts["origin"] = "octoprint"
					self.ss.send_text(json.dumps(connect_opts))
					# Spuštění cyklu zpráv
					self.watching = True

			# Připojení k tiskárně
			if k == "connect":
				self._printer.connect(v["port"], v["baudrate"])

			# Odpojení tiskárny
			if k == "disconnect":
				self._printer.disconnect()

			# Načte soubor a začne tisknout
			if k == "job":
				# Kontrola jestli je tiskárna připravena k tisku
				if self._printer.is_ready():
					self._printer.select_file(v, False, True)

			# Příkazy pro probíhající tiskovou úlohu
			if k == "cmd":
				# Ukončení tisku
				if v == "cancel":
					self._printer.cancel_print()
				if self._printer.is_ready():
					if v == "print":
						# Začne tisknout načtený soubor
						self._printer.start_print()
				if v == "toggle":
					# Pozastaví/rozběhne probíhající tiskovou úlohu
					self._printer.toggle_pause_print()

			# Kod pro tiskovou úlohu s opoždeným startem
			if k == "delay":
				difference = v["difference"]
				name = str(v["file"])
				serial = None
				baud = None
				# Nastavení připojovacích možnosti
				if v["serial"] and v["baud"]:
					serial = v["serial"]
					baud = v["baud"]
				# Časové omezení funkce, proběhne pouze jestli je rozdíl mezi současným a plánovaným časem v tomto rozmezí (1s - ~48h)
				if 1000 <= difference <= 172800000:
					t = threading.Timer(difference / 1000, self.print_job, [name, serial, baud])
					t.start()

			# Pohyb s tiskovou hlavou/podložkou
			if k == "jog":
				# Kontrola obsažených os
				self._logger.info(v)
				if v["axis"][0] in "xyz":
					axes = {}
					axis = str(v["axis"][0])
					if v["axis"][1] in "+-":
						self._logger.info(v["step"])
						if v["step"] in self.steps:
							# Nastavení hodnoty o kterou se osa posune
							amount = str(v["axis"][1] + v["step"])
							axes[axis] = amount
							self._logger.info(axes)
							self._printer.jog(axes)

			# Kalibrace os, všechny specifikované osy se vrátí "domů"
			if k == "home":
				axis = list(v.split(" "))
				self._printer.home(axis)

			# Nastavení teplot trysky a podložky
			if k == "tool0" or k == "bed":
				if k == "tool0":
					# Kontrola hodnoty proti maximální teplotě
					if int(v) <= 300:
						self._printer.set_temperature(k, int(v))
				if k == "bed":
					if int(v) <= 120:
						self._printer.set_temperature(k, int(v))

			# Klient se již nedívá, cyklus zpráv o aktuálním stavu se může pozastavit
			if k == "left":
				if v == True:
					self.watching=False

	# Funkce přes kterou se odesílají data pro monitoring tisku a stavu tiskárny
	def send_data(self):
		try:
			# Získá data právě probíhajícího tisku
			data = self._printer.get_current_data()
			# Získání teplot
			data["temps"] = self._printer.get_current_temperatures()
			# Nastavení zdroje zprávy pro websocket server
			data["origin"] = "octoprint"
			self.ss.send_text(json.dumps(data))
		except:
			import traceback
			traceback.print_exc()

	# Funkce se stará o opožděný start tiskové úlohy
	def print_job(self, file, serial, baud):
		# Pokud je tiskárna připravená, začne tisknout
		if self._printer.is_ready():
			self._printer.select_file(file, False, True)
		# Jestli není Octoprint s tiskárnou spojený pokusí se o připojení
		elif self._printer.get_state_id() == "OFFLINE":
			try:
				self._printer.connect(serial, baud)
				# Čas nutný pro navázaní spojení
				time.sleep(5)
				# Start tisku
				self.print_job(file, serial, baud)
			except:
				# Chybová hláška při problémech s připojením
				self._logger.info("An error occured")

	##~~ SettingsPlugin mixin

	def get_settings_defaults(self):
		# Výchozí nastavení URl adresy a intervalu odesílání zpráv
		return dict(
			interval=2,
			url="ws://127.0.0.1:8765",
		)

	def get_template_configs(self):
		return [
			dict(type="settings", custom_bindings=False)
		]

	##~~ AssetPlugin mixin

	def get_assets(self):
		# Define your plugin"s asset files to automatically include in the
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


# Plugin declarations
__plugin_name__ = "Printer Monitor"
__plugin_pythoncompat__ = ">=3,<4"  # only python 3


def __plugin_load__():
	global __plugin_implementation__
	__plugin_implementation__ = MonitoringPlugin()

	global __plugin_hooks__
	__plugin_hooks__ = {
		"octoprint.plugin.softwareupdate.check_config": __plugin_implementation__.get_update_information
	}
