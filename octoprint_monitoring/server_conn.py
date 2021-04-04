import websocket
import time

class ServerConnection:
	def __init__(self, url, on_server_ws_msg):

		# Funkce která se vyvolá při přijetí zprávy
		def on_message(ws, msg):
			on_server_ws_msg(ws, msg)

		# Chybová hláška
		def on_error(ws, error):
			print(error)

		# Navázaní spojení se serverem na specifikované url adrese
		self.ws = websocket.WebSocketApp(url,
								on_message=on_message,
								on_error=on_error
								)

	# Spouštěcí funkce která udržuje spojení v běhu
	def run(self):
		self.ws.run_forever()

	# Funkce pro odeslání zprávy hostiteli
	def send_text(self, data):
		# Pouze jestli je navázané spojení
		if self.connected():
			self.ws.send(data)

	# Vrací informaci jestli je spojení navázané či nikoliv
	def connected(self):
		return self.ws.sock and self.ws.sock.connected

	# Odpojení od serveru
	def disconnect(self):
		self.ws.keep_running = False;
		self.ws.close()
