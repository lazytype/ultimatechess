from chesstools import Board
from chesstools import Move

import tornado.ioloop
import tornado.web
import tornado.websocket
import tornado.escape

from tornado.options import define, options

from collections import namedtuple

define("port", default=8888, help="Run the server on the given port", type=int)

STATIC_PATH = 'ultimatechess'


def  _fen_layout_fixed(self):
	pieces = []
	for row in self.position:
		c = 0
		rstring = ''
		for piece in row:
			if piece:
				if c:
					rstring += str(c)
					c = 0
				rstring += str(piece)
			else:
				c += 1
		if c:
			rstring += str(c)
		pieces.append(rstring)
	return '/'.join(pieces)

Board._fen_layout = _fen_layout_fixed


games = {}

class Game(object):
	def __init__(self, name, white_player):
		self.has_black = False
		self.white_player = white_player
		self.name = name
		self.boards = []
		self.state = []
		for i in xrange(4):
			self.boards.append(Board())
			# self.boards[i].move(self.boards[i].all_legal_moves()[0])
			self.state.append(self.boards[i].fen())
		games[name] = self

	def move(self, index, move):
		print 'called with move: ', move
		source = move['from']
		target = move['to']
		movement = Move(source, target)

		if self.boards[index].is_legal(movement):
			self.boards[index].move(movement)
			self.state[index] = self.boards[index].fen()
			return True
		return False

	def found_black(self, black_player):
		self.has_black = True
		self.black_player = black_player
		self.white_player.write_message(tornado.escape.json_encode({'response_type': 'opponent_found'}))

	def write_message(self, player, raw_message):
		raw_message['player'] = 'white' if self.white_player is player else 'black'
		message = tornado.escape.json_encode(raw_message)
		self.white_player.write_message(message)
		self.black_player.write_message(message)

	@staticmethod
	def parse_position(pos):
		column = 'abcdefgh'.index(pos[0].lower())
		row = int(pos[1]) - 1
		return (row, column)

	@staticmethod
	def get_quadrant(move):
		target = move['to']
		if target[0] in 'abcd' and target[1] in '5678':
			return 1
		elif target[0] in 'abcd':
			return 3
		elif target[1] in '5678':
			return 2
		else:
			return 4

	@classmethod
	def create_and_register(cls, name, white_player):
		game = cls(name, white_player)
		games[name] = game
		return game

# class MainHandler(tornado.web.RequestHandler):
# 	def get(self):
# 		self.write('hello, world')

class WebSocketHandler(tornado.websocket.WebSocketHandler):
	
	def open(self):
		print 'new connection'

	def on_message(self, message):
		print 'message received %s' % message

		try:
			data = tornado.escape.json_decode(message)
		except:
			return

		if 'create' in data:
			name = data['create']
			if name in games:
				if games[name].has_black:
					self.write_message(tornado.escape.json_encode({
						'response_type': 'creation',
						'success': False,
						'created': False}))
				else:
					self.name = name
					games[name].found_black(self)
					self.write_message(tornado.escape.json_encode({
						'response_type': 'creation',
						'success': True, 
						'created': False, 
						'state': games[name].state,
						'player': 'black'
						}))
			else:
				try:
					game = Game.create_and_register(name, self)
					self.write_message(tornado.escape.json_encode({
						'response_type': 'creation',
						'success': True,
						'created': True, 
						'state': game.state,
						'player': 'white'}))
					self.name = name
				except Exception, e:
					print e
					self.write_message(tornado.escape.json_encode({
						'response_type': 'creation',
						'success': False, 
						'created': False}))

		elif 'move' in data and 'name' in data and data['name'] in games:
			game = games[data['name']]
			try:
				index = data['index']
				move = data['move']
				moved = game.move(index, move)
				quadrant = Game.get_quadrant(move)
				player = game.write_message(self, {
					'response_type': 'movement',
					'moved': moved, 
					'index': index,
					'source': move['from'],
					'target': move['to'],
					'quadrant': quadrant})
			except:
				self.write_message(tornado.escape.json_encode({
					'response_type': 'movement',
					'moved': False}))

			if moved:
				pass

	def on_close(self):
		if self.name in games:
			del games[self.name]
		print 'connection closed'


if __name__ == '__main__':
	tornado.options.parse_command_line()
	application = tornado.web.Application([
		(r'/static/(.*)',   tornado.web.StaticFileHandler, {'path': STATIC_PATH}),
		(r'/ws', WebSocketHandler),
	])

	application.listen(options.port)
	tornado.ioloop.IOLoop.instance().start()