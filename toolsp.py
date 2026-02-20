"""

Bismuth Explorer Proceedures Module

Version 2.1.0

"""

import sqlite3, time, json, requests, re, socks, connections, logging, os

import configparser as cp
from bs4 import BeautifulSoup

_BASE58_ALPHABET = "123456789ABCDEFGHJKLMNPQRSTUVWXYZabcdefghijkmnopqrstuvwxyz"
_BASE58_INDEX = {c: i for i, c in enumerate(_BASE58_ALPHABET)}

# Read config
config = cp.ConfigParser()
with open('explorer.ini', 'r') as cfg_file:
	config.read_file(cfg_file)

try:
	db_root = config.get('My Explorer', 'dbroot')
except:
	db_root = "static/"
try:
	bis_root = config.get('My Explorer', 'bisroot')
except:
	bis_root = "static/ledger.db"
try:
	hyper_root = config.get('My Explorer', 'hyperroot')
except:
	hyper_root = "static/hyper.db"
try:
	ip = config.get('My Explorer', 'nodeip')
except:
	ip = "127.0.0.1"
try:
	port = config.get('My Explorer', 'nodeport')
except:
	port = "5658"
try:
	circ_cache_path = config.get('My Explorer', 'circ_cache')
except:
	circ_cache_path = "static/circ_cache.json"

db_hyper = True

_CACHE_MISS = object()
_alias_cache = {}
_latest_cache = {}
_circ_cache = {}
_details_cache = {}
_custom_cache = {"ts": 0.0, "alias_by_address": {}, "address_by_alias": {}}

_ALIAS_TTL_SECONDS = 600
_LATEST_TTL_SECONDS = 1.5
_CIRC_TTL_SECONDS = 900
_CUSTOM_TTL_SECONDS = 60
_SLOW_TOOLSP_CALL_MS = 300
_DETAILS_TTL_SECONDS = 60

_toolsp_log = logging.getLogger("toolsp")

def _cache_get(cache, key, ttl_seconds):
	now = time.time()
	entry = cache.get(key)
	if not entry:
		return _CACHE_MISS
	ts, value = entry
	if now - ts > ttl_seconds:
		cache.pop(key, None)
		return _CACHE_MISS
	return value

def _cache_set(cache, key, value):
	cache[key] = (time.time(), value)

def _load_custom_cache():
	now = time.time()
	if now - _custom_cache["ts"] <= _CUSTOM_TTL_SECONDS:
		return
	alias_by_address = {}
	address_by_alias = {}
	try:
		with open('custom.txt', 'r') as infile:
			for line in infile:
				parts = line.split(':')
				if len(parts) < 2:
					continue
				alias = parts[0].strip()
				address = parts[1].strip()
				if address:
					alias_by_address[address] = alias
				if alias:
					address_by_alias[alias] = address
	except:
		alias_by_address = {}
		address_by_alias = {}
	_custom_cache["alias_by_address"] = alias_by_address
	_custom_cache["address_by_alias"] = address_by_alias
	_custom_cache["ts"] = now

def get_one_arg(gcom,arg1):

	s = socks.socksocket()
	s.settimeout(10)
	s.connect((ip, int(port)))
	connections.send(s, gcom, 10)
	connections.send(s, arg1)
	response = connections.receive(s, 10)
	s.close()

	return response
	
def get_two_arg(gcom,arg1,arg2):

	s = socks.socksocket()
	s.settimeout(10)
	s.connect((ip, int(port)))
	connections.send(s, gcom, 10)
	connections.send(s, arg1)
	connections.send(s, arg2)
	response = connections.receive(s, 10)
	s.close()

	return response
	
def get_no_arg(gcom):

	s = socks.socksocket()
	s.settimeout(10)
	s.connect((ip, int(port)))
	connections.send(s, gcom, 10)
	response = connections.receive(s, 10)
	s.close()

	return response

def getcirc():

	cached = _cache_get(_circ_cache, "circ", _CIRC_TTL_SECONDS)
	if cached is not _CACHE_MISS:
		return cached
	try:
		if circ_cache_path and os.path.isfile(circ_cache_path):
			with open(circ_cache_path, "r") as infile:
				data = json.load(infile)
			ts = float(data.get("timestamp", 0))
			if time.time() - ts <= _CIRC_TTL_SECONDS:
				total = data.get("total")
				circulating = data.get("circulating")
				if total is not None and circulating is not None:
					result = (str(total), str(circulating))
					_cache_set(_circ_cache, "circ", result)
					return result
	except Exception:
		pass

	t0 = time.time()
	conn = sqlite3.connect(bis_root)
	conn.text_factory = str
	c = conn.cursor()
	
	c.execute("SELECT sum(reward) FROM transactions;")

	allcirc = c.fetchone()[0]
	
	c.execute("SELECT sum(amount) FROM transactions WHERE address = 'Development Reward';")
	
	alldev = c.fetchone()[0]

	c.execute("SELECT sum(amount) FROM transactions WHERE address = 'Hyperblock';")
	
	allhyp = c.fetchone()[0]
	
	c.execute("SELECT sum(amount) FROM transactions WHERE address = 'Hypernode Payouts';")
	
	allmno = c.fetchone()[0]
	
	if not allhyp:
		allhyp = 0
	if not alldev:
		alldev = 0
	if not allmno:
		allmno = 0

	total = float(allcirc) + float(alldev) + float(allhyp) + float(allmno)
	circulating = float(allcirc) + float(allhyp) + float(allmno)
	
	total = "{:.8f}".format(total)
	circulating = "{:.8f}".format(circulating)

	c.close()
	conn.close()
	dt_ms = (time.time() - t0) * 1000.0
	if dt_ms >= _SLOW_TOOLSP_CALL_MS:
		_toolsp_log.warning("slow call %dms toolsp.getcirc", int(dt_ms))
	
	result = (total, circulating)
	_cache_set(_circ_cache, "circ", result)
	return result

def rev_alias(tocheck):

	a_addy = tocheck.split(":")
	t_addy = str(a_addy[1])
	
	try:
		rev_alias = get_one_arg("addfromalias",t_addy)
		
		if rev_alias:
			r_addy = rev_alias
		else:
			r_addy = "0"
		
	except:
		r_addy = "0"
		
	_load_custom_cache()
	r_addy = _custom_cache["address_by_alias"].get(t_addy, r_addy)
		
	#print(r_addy)
	return str(r_addy)

def display_time(seconds, granularity=2):

	intervals = (
		('weeks', 604800),  # 60 * 60 * 24 * 7
		('days', 86400),    # 60 * 60 * 24
		('hours', 3600),    # 60 * 60
		('minutes', 60),
		('seconds', 1),
		)

	result = []

	for name, count in intervals:
		value = seconds // count
		if value:
			seconds -= value * count
			if value == 1:
				name = name.rstrip('s')
			result.append("{} {}".format(value, name))
	return ', '.join(result[:granularity])

def latest():

	cached = _cache_get(_latest_cache, "latest", _LATEST_TTL_SECONDS)
	if cached is not _CACHE_MISS:
		return cached

	block_get = get_no_arg("blocklast")
	diff = get_no_arg("difflast")
	
	db_block_height = str(block_get[0])
	db_timestamp_last = block_get[1]
	db_block_finder = block_get[2]
	db_block_hash = block_get[7]
	db_block_txid = block_get[5][:56]
	db_block_open = block_get[11]
	time_now = str(time.time())
	last_block_ago = (float(time_now) - float(db_timestamp_last))#/60
	#last_block_ago = '%.2f' % last_block_ago
	diff_block_previous = diff[1]

	result = (db_block_height, last_block_ago, diff_block_previous, db_block_finder, db_timestamp_last, db_block_hash, db_block_open, db_block_txid)
	_cache_set(_latest_cache, "latest", result)
	return result

	
def get_block_time(my_hist):

	lb_tick = latest()
	lb_height = lb_tick[0]
	lb_stamp = lb_tick[4]
	sb_height = int(lb_height) - my_hist
	
	conn = sqlite3.connect(bis_root)
	conn.text_factory = str
	c = conn.cursor()
	try:
		c.execute("SELECT timestamp,block_height FROM transactions WHERE reward !=0 and block_height >= ?;",(str(sb_height),))
		result = c.fetchall()

		l = []
		y = 0
		for x in result:
			if y == 0:
				ts_difference = 0
			else:
				ts_difference = float(x[0]) - float(y)
			ts_block = x[1]
			#print(str(x[1])+" "+str(ts_difference))
			tx = (ts_block,ts_difference)
			l.append(tx)
			y = x[0]
		return l
	finally:
		c.close()
		conn.close()


def get_the_details(getdetail, get_addy):

	t0 = time.time()
	m_stuff = "{}%".format(str(getdetail))
	cache_key = (getdetail, get_addy or "")
	cached = _cache_get(_details_cache, cache_key, _DETAILS_TTL_SECONDS)
	if cached is not _CACHE_MISS:
		return cached
	
	if db_hyper:
	
		conn = sqlite3.connect(hyper_root)
		conn.text_factory = str
		c = conn.cursor()
		try:
			c.execute("PRAGMA case_sensitive_like=ON;")
			c.execute("SELECT * FROM transactions WHERE signature LIKE ?;", (m_stuff,))
			m_detail = c.fetchone()
			#print(m_detail)
		finally:
			c.close()
			conn.close()
		
		if not m_detail:
		
			if get_addy:
		
				conn = sqlite3.connect(bis_root)
				conn.text_factory = str
				c = conn.cursor()
				try:
					c.execute(
						"""
						SELECT * FROM transactions
						WHERE (address = ? OR recipient = ?)
						  AND signature LIKE ?;
						""",
						(get_addy, get_addy, m_stuff)
					)
					m_detail = c.fetchone()
				finally:
					c.close()
					conn.close()
				if not m_detail:
					m_detail = None
				
			else:
				
				m_detail = get_two_arg("api_gettransaction",m_stuff,False)

	else:

		m_detail = None

	if not m_detail:
		conn = sqlite3.connect(bis_root)
		conn.text_factory = str
		c = conn.cursor()
		try:
			c.execute("PRAGMA case_sensitive_like=ON;")
			if get_addy:
				c.execute(
					"""
					SELECT * FROM transactions
					WHERE (address = ? OR recipient = ?)
					  AND signature LIKE ?;
					""",
					(get_addy, get_addy, m_stuff)
				)
			else:
				c.execute("SELECT * FROM transactions WHERE signature LIKE ?;", (m_stuff,))
			m_detail = c.fetchone()
		finally:
			c.close()
			conn.close()
		if not m_detail:
			m_detail = get_two_arg("api_gettransaction", m_stuff, False)
	
	dt_ms = (time.time() - t0) * 1000.0
	if dt_ms >= _SLOW_TOOLSP_CALL_MS:
		_toolsp_log.warning("slow call %dms toolsp.get_the_details", int(dt_ms))
	_cache_set(_details_cache, cache_key, m_detail)
	return m_detail

def test(testString):

	test_result = 3

	if len(testString) == 56:
		test_result = 1

	if testString.isalnum() == True:
	
		try:
			validate_result = get_one_arg("addvalidate",testString)
		except:
			validate_result = ""
		
		if validate_result == "valid":
			test_result = 1

	if testString.isdigit() == True:
		test_result = 2
	
	#print(test_result)
	return test_result
	
def s_test(testString):

	if not testString:
		return False
	if testString.isalnum() == True:

		try:
			validate_result = get_one_arg("addvalidate",testString)
		except:
			validate_result = ""
		
		if validate_result == "valid":
			return True
		else:
			return False
	else:
		return False
		
def d_test(testString):

	if len(testString) == 56:
		if bool(BeautifulSoup(testString,"html.parser").find()):
			return False
		else:
			return True
	else:
		return False

def _base58_encode(data):
	if not data:
		return ""
	n = int.from_bytes(data, "big")
	encoded = ""
	while n > 0:
		n, rem = divmod(n, 58)
		encoded = _BASE58_ALPHABET[rem] + encoded
	pad = 0
	for b in data:
		if b == 0:
			pad += 1
		else:
			break
	return ("1" * pad) + encoded

def _base58_decode(value):
	if not value:
		return b""
	n = 0
	for ch in value:
		idx = _BASE58_INDEX.get(ch)
		if idx is None:
			raise ValueError("invalid base58 character")
		n = n * 58 + idx
	if n == 0:
		decoded = b""
	else:
		decoded = n.to_bytes((n.bit_length() + 7) // 8, "big")
	pad = 0
	for ch in value:
		if ch == "1":
			pad += 1
		else:
			break
	return (b"\x00" * pad) + decoded

def decode_base58_txid(value):
	if not value:
		return None
	if len(value) <= 56:
		return None
	if any(ch not in _BASE58_INDEX for ch in value):
		return None
	try:
		decoded = _base58_decode(value)
		text = decoded.decode("utf-8")
	except Exception:
		return None
	if len(text) != 56:
		return None
	return text

def normalize_txid_input(value):
	decoded = decode_base58_txid(value)
	return decoded if decoded else value

def txid_to_base58(value):
	if not value:
		return value
	decoded = decode_base58_txid(value)
	if decoded:
		return _base58_encode(decoded.encode("utf-8"))
	return _base58_encode(str(value).encode("utf-8"))

def miners():

	conn = sqlite3.connect('tools.db')
	conn.text_factory = str
	c = conn.cursor()
	c.execute("SELECT * FROM minerlist ORDER BY blockcount DESC;")
	miner_result = c.fetchall()
	c.close()
	conn.close()

	return miner_result

def richones():

	conn = sqlite3.connect('tools.db')
	conn.text_factory = str
	c = conn.cursor()
	c.execute("SELECT * FROM richlist ORDER BY balance DESC;")
	rich_result = c.fetchall()
	c.close()
	conn.close()

	return rich_result
	
def bgetvars(myaddress):

	try:
		conn = sqlite3.connect('tools.db')
		conn.text_factory = str
		c = conn.cursor()
		c.execute("SELECT * FROM minerlist WHERE address = ?;",(myaddress,))
		miner_details = c.fetchone()
		c.close()
		conn.close()
	except:
		miner_details = None
		
	return miner_details
	
def get_cmc_val(y_data):

	global cmc_vals
	
	l = ["BTC","USD","EUR","GBP","CNY","AUD"]
	p = []
	
	#t = "https://api.coingecko.com/api/v3/coins/bismuth?localization=false&tickers=false&market_data=true&community_data=false&developer_data=false"
	#r = requests.get(t)
	#x = r.text
	#y = json.loads(x)
	y = y_data
	
	for curr in l:
	
		ch = curr.lower()
	
		try:
			s = float(y['market_data']['current_price'][ch])
		
		except:
			s = 0.00000001
			
		p.append(s)
		
		time.sleep(1)
		
	s = dict(zip(l, p))
		
	return s

def get_alias(address):

	cached = _cache_get(_alias_cache, address, _ALIAS_TTL_SECONDS)
	if cached is not _CACHE_MISS:
		return cached

	try:
		
		t_alias = get_one_arg("aliasget",address)
		
		try:
			r_alias = t_alias[-1][-1]
		except:
			r_alias = ""
			
		if r_alias == address:
			r_alias = ""
				
		if not r_alias:
			r_alias = ""
	except:
		r_alias = ""
	
	_load_custom_cache()
	r_alias = _custom_cache["alias_by_address"].get(address, r_alias)

	_cache_set(_alias_cache, address, r_alias)
	return r_alias

	
def get_tokens(address):

	try:
		conn = sqlite3.connect('{}index.db'.format(db_root))
		conn.text_factory = str
		c = conn.cursor()
		c.execute("SELECT * FROM tokens WHERE address=? ORDER BY block_height DESC;", (address,))
		r_tokens = c.fetchall()
		c.close()
		conn.close()

	except:
		r_tokens = None

	return r_tokens
	
def query_tkaddy(this_tkaddy):

	try:
		conn = sqlite3.connect('{}index.db'.format(db_root))
		conn.text_factory = str
		c = conn.cursor()
		c.execute("SELECT * FROM tokens WHERE address=? or recipient=? ORDER BY block_height DESC;", (this_tkaddy,this_tkaddy))
		tx_tokens = c.fetchall()
		c.close()
		conn.close()

	except:
		tx_tokens = None

	return tx_tokens
	
def query_token(this_token):

	try:
		conn = sqlite3.connect('{}index.db'.format(db_root))
		conn.text_factory = str
		c = conn.cursor()
		c.execute("SELECT * FROM tokens WHERE token=? ORDER BY block_height DESC;", (this_token,))
		q_tokens = c.fetchall()
		c.close()
		conn.close()

	except:
		q_tokens = None

	return q_tokens


def refresh(testAddress,typical):

	#bal_all = get_one_arg("balancegetjson",testAddress)

	#print(bal_all)

	if typical == 1:
		conn = sqlite3.connect(bis_root)
		conn.text_factory = str
		c = conn.cursor()
	elif typical == 2:
		conn = sqlite3.connect(bis_root)
		conn.text_factory = str
		c = conn.cursor()
	else:
		pass
		
	credit = float(0)
	try:
		c.execute("SELECT sum(amount) FROM transactions WHERE recipient = ?;", (testAddress,))
		row = c.fetchone()
		credit = row[0] if row and row[0] is not None else 0
	except:
		credit = 0

	c.execute("SELECT sum(amount),sum(fee),sum(reward) FROM transactions WHERE address = ?;", (testAddress,))
	tester = c.fetchone() or (0, 0, 0)

	debit = tester[0]
	fees = tester[1]
	rewards = tester[2]
	
	if not rewards:
		rewards = 0
	
	if rewards > 0:		
		c.execute("SELECT count(*) FROM transactions WHERE address = ? AND (reward != 0);", (testAddress,))
		row = c.fetchone()
		b_count = row[0] if row and row[0] is not None else 0
		c.execute("SELECT MAX(timestamp), MIN(timestamp) FROM transactions WHERE recipient = ? AND (reward !=0);", (testAddress,))
		row = c.fetchone()
		t_max = row[0] if row and row[0] is not None else 0
		t_min = row[1] if row and row[1] is not None else 0

		t_min = str(time.strftime("at %H:%M:%S on %d/%m/%Y", time.gmtime(float(t_min)))) if t_min else 0
		t_max = str(time.strftime("at %H:%M:%S on %d/%m/%Y", time.gmtime(float(t_max)))) if t_max else 0
	else:
		b_count = 0
		t_min = 0
		t_max = 0
	
	if not debit:
		debit = 0
	if not fees:
		fees = 0
	if not rewards:
		rewards = 0
	if not credit:
		credit = 0

	balance = (credit + rewards) - (debit + fees)

	c.close()
	conn.close()
	
	if typical == 1:
		conn.close()
		
	r_alias = get_alias(testAddress)
	
	get_stuff = ["{:.8f}".format(credit),"{:.8f}".format(debit),"{:.8f}".format(rewards),"{:.8f}".format(fees),"{:.8f}".format(balance),t_max, t_min, b_count, r_alias]
		
	return get_stuff
	
def mem_html(b):

	send_back = ""
	
	if b != "":
		#print("Realmem: TXs in mempool: " + str(len(b)))
		for response in b:
			address = response['address']
			m_alias = get_alias(address)
			if m_alias != "":
				address = m_alias
			recipient = response['recipient']
			m_alias = get_alias(recipient)
			if m_alias != "":
				recipient = m_alias
			amount = response['amount']
			txid = response['signature'][:56]
			
			timestamp = str(time.strftime("%H:%M:%S, %d/%m/%Y", time.gmtime(float(response['timestamp']))))
			send_back = send_back + '<tr><th scope="row"> {} </th>\n'.format(timestamp)
			send_back = send_back + '<td>{}</td><td>{}</td><td>{}</td><td>{}</td></tr>'.format(address,recipient,amount,txid)
			
	else:
		timestamp = address = recipient = amount = txid = "-"
		#print("Realmem: No TXs in mempool")
		send_back = send_back + '<tr><th scope="row"> {} </th>\n'.format(timestamp)
		send_back = send_back + '<td>{}</td><td>{}</td><td>{}</td><td>{}</td></tr>'.format(address,recipient,amount,txid)

	return send_back
	
def xws(): # list of live wallet servers

	try:

		rep = requests.get("https://bismuth.world/api/legacy.json", timeout=10)
		if rep.status_code == 200:
			wallets = rep.json()
							
		x = sorted([wallet for wallet in wallets if wallet['active']], key=lambda k: (k['clients']+1)/(k['total_slots']+2))
		
	except:
		
		x = ""
		
	return x
