import tornado.ioloop
import tornado.web
import tornado.httpserver

import json
import requests

import os
import re
import ratelimit


# your local account_name to transfer token
ACCOUNT = "test-net"

# your local wallet unlock password
PASSWD = "caochong"

# local wallet api url
WALLET_URL = "http://127.0.0.1:8091"
#WALLET_URL = "http://127.0.0.1:8091"


IS_ACCOUNT_DATA = '{"jsonrpc": "2.0", "method": "is_account_registered", "params": ["%s"], "id": 1}'
IS_LOCKED_DATA = '{"jsonrpc": "2.0", "method": "is_locked", "params": [], "id": 2}'
UNLOCK_DATA = '{"jsonrpc": "2.0", "method": "unlock", "params": ["%s"], "id": 3}'
TRANSFER_DATA='{"jsonrpc": "2.0", "method": "transfer2", "params": ["%s", "%s", "%s", "%s", "%s", "true"], "id": 4}'

# ------------------------------------------------------------------------------------------
# ------ token transfer limiter

def token_limit_exceed(handler):
    write_json_response(handler, {'msg': 'reach 24 hours max token amount'}, 403)

def account_limit_exceed(handler):
    write_json_response(handler, {'msg': 'reach 24 hours max account amount'}, 403)

single_get_token_call_amount = 200

ip_24h_token_amount_limiter = ratelimit.RateLimitType(
  name = "ip_24h_token_amount",
  amount = 1000,         # 24 hours amount
  expire = 3600*24,      # 24 hours
  identity = lambda h: h.request.remote_ip,
  on_exceed = token_limit_exceed)


account_24h_token_amount_limiter = ratelimit.RateLimitType(
  name = "account_24h_token_amount",
  amount = 3,         # 24 hours amount
  expire = 3600*24,      # 24 hours
  identity = lambda h: h.request.arguments.keys()[1] if len(h.request.arguments.keys()) == 2 else '',
  on_exceed = account_limit_exceed)

# ------------------------------------------------------------------------------------------
# ------ common functions

def write_json_response(handler, msg, code=200):
  handler.set_status(code)
  handler.set_header('Content-Type', 'application/json; charset=UTF-8')
  handler.write(msg)

def get_first_arg_name_from_request(request):
  args = request.arguments.keys()
  if len(args) == 1:
    return args[0]
  else:
    return ''

def get_second_arg_name_from_request(request):
  args = request.arguments.keys()
  if len(args) == 2:
    return args[1]
  else:
    return ''

def is_valid_symbol(symbol):
  param = IS_SYMBOL_DATA % symbol
  response = requests.request("POST", WALLET_URL, data=param)
  js = json.loads(response.text)
  try:
    error = js['error']
    return False
  except:
    return true

def is_valid_account_name(account_name):
  param = IS_ACCOUNT_DATA % account_name
  response = requests.request("POST", WALLET_URL, data=param)
  js = json.loads(response.text)
  return js['result']

def unlock_wallet():
  param = UNLOCK_DATA % PASSWD
  response = requests.request("POST", WALLET_URL, data=param)
  return response.status_code == 200

def is_wallet_locked():
  response = requests.request("POST", WALLET_URL, data=IS_LOCKED_DATA)
  js = json.loads(response.text)
  return js['result']

def get_first_arg_name_from_request(request):
  args = request.arguments.keys()
  if len(args) == 1:
    return args[0]
  else:
    return ''

def unlock_wallet_if_locked():
  unlocked = False
  if is_wallet_locked():
    print 'wallet is locked, try to unlock...'
    if unlock_wallet():
      unlocked = True
      print 'wallet unlocked!'
    else:
      print 'wallet  unlock failed'
  else:
    unlocked = True
  return unlocked


# ------------------------------------------------------------------------------------------
# ------ Get Token Handler

class GetTokenHandler(tornado.web.RequestHandler):

  def __init__(self, application, request, **kwargs):
    tornado.web.RequestHandler.__init__(self, application, request, **kwargs)

  def _assembly_args(self, data):
    symbol = "GXC"
    if data.has_key('symbol') and is_valid_symbol(data['symbol']):
      symbol = data['symbol']

    if data.has_key('account') and is_valid_account_name(data['account']):
      p = {}
      p['from']     = ACCOUNT
      p['to']       = data['account']
      p['quantity'] = single_get_token_call_amount
      p['symbol']   = symbol
      if data.has_key('memo'): p['memo']   = data['memo']
      else:                    p['memo']   = ''
      return p
    else:
      return None

  def _os_cmd_transfer(self, param):
    param = TRANSFER_DATA % (ACCOUNT, param['to'], param['quantity'], param['symbol'], param['memo'])
    response = requests.request("POST", WALLET_URL, data=param)
    print response.text
    js = json.loads(response.text)
    return js['result']

  def _make_transfer(self, p):
    if unlock_wallet_if_locked():
      return self._os_cmd_transfer(p)
    else:
      return False

  def _handle(self, data):
    param = self._assembly_args(data)
    if param:
      if self._make_transfer(param):
        ip_24h_token_amount_limiter.increase_amount(param['quantity'], self)
        account_24h_token_amount_limiter.increase_amount(1, self)
        write_json_response(self, {'msg': 'succeeded'})
      else:
        failmsg = {'msg': 'transaction failed, possible reason: account does not exist'}
        write_json_response(self, failmsg, 400)
    else:
      fmtmsg = {'msg':'please use request with URL of format: https://testnet.gxchain.org/gxc/get_token?valid_account_name'}
      write_json_response(self, fmtmsg, 400)

  @ratelimit.limit_by(ip_24h_token_amount_limiter)
  @ratelimit.limit_by(account_24h_token_amount_limiter)
  def get(self):
    data = {'symbol': get_first_arg_name_from_request(self.request), 'account': get_second_arg_name_from_request(self,request) }
    self._handle(data)

# --------------------------l---------------------------------------------------------------
# ------ service app

def make_app():
  return tornado.web.Application([
    (r"/get_token", GetTokenHandler),
  ])

if __name__ == "__main__":
  app = make_app()
  server = tornado.httpserver.HTTPServer(app)
  server.bind(8088)
  server.start(0)
  tornado.ioloop.IOLoop.current().start()
