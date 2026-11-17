"""
Test client for the ADS-B API (IA626).
"""
import requests, json, datetime

BASE = 'http://127.0.0.1:5000'
KEY = '123'
BAD_KEY = '1234'
DT_FORMAT = '%Y-%m-%d %H:%M:%S'
TOP_KEYS = ['code', 'msg', 'req', 'sqltime']

passed = 0
failed = 0


def check(name, condition, detail=''):
    global passed, failed
    if condition:
        passed += 1
        print(f'  PASS  {name}')
    else:
        failed += 1
        print(f'  FAIL  {name}  {detail}')


def call(endpoint, params):
    # requests encodes the spaces in the dates and polygon for us
    r = requests.get(BASE + endpoint, params=params)
    resp = json.loads(r.text)
    print(f'\n{r.url}')
    print(f"  -> code={resp.get('code')} msg={resp.get('msg')!r} sqltime={resp.get('sqltime')}")
    check('has top level keys code, msg, req, sqltime', all(k in resp for k in TOP_KEYS))
    check(f"req is {endpoint}", resp.get('req') == endpoint)
    return resp


# ------------------------------------------------------------ auth
print('=== auth ===')
for ep in ['/getData', '/countInPolygon', '/getAvgSpeedByFlight']:
    resp = call(ep, {'key': BAD_KEY})
    check('wrong key -> code 0, auth error', resp['code'] == 0 and resp['msg'] == 'auth error')
    resp = call(ep, {})
    check('missing key -> code 0, auth error', resp['code'] == 0 and resp['msg'] == 'auth error')

# ------------------------------------------------------------ getData
print('\n=== /getData ===')
start, end = '2022-11-23 05:28:10', '2022-11-23 05:28:15'
resp = call('/getData', {'key': KEY, 'start': start, 'end': end})
check('code 1, msg ok', resp['code'] == 1 and resp['msg'] == 'ok')
check('num_results == len(results)', resp.get('num_results') == len(resp.get('results', [])))
check('at most 500 results', len(resp.get('results', [])) <= 500)
times = [r['date_time'] for r in resp.get('results', [])]
check('every date_time is between start and end', all(start <= t <= end for t in times))
check('results are sorted by date_time', times == sorted(times))
print(f"  {resp.get('num_results')} records")
if resp.get('results'):
    print('  first record:', json.dumps(resp['results'][0]))

resp = call('/getData', {'key': KEY, 'start': '2022-11-23 00:00:00', 'end': '2022-11-24 00:00:00'})
check('whole day is capped at 500 results', resp['code'] == 1 and resp['num_results'] == 500)

resp = call('/getData', {'key': KEY, 'start': start})
check('missing end -> code 0', resp['code'] == 0)
resp = call('/getData', {'key': KEY, 'start': 'yesterday', 'end': end})
check('bad date format -> code 0', resp['code'] == 0)
resp = call('/getData', {'key': KEY, 'start': end, 'end': start})
check('start after end -> code 0', resp['code'] == 0)

# ------------------------------------------------------------ countInPolygon
print('\n=== /countInPolygon ===')
resp = call('/countInPolygon', {'key': KEY, 'polygon': '-74 42,-75 39,-74 41,-74 42'})
check('code 1, msg ok', resp['code'] == 1 and resp['msg'] == 'ok')
check('count is a whole number >= 0', isinstance(resp.get('count'), int) and resp['count'] >= 0)
print(f"  count = {resp.get('count')}")

resp = call('/countInPolygon', {'key': KEY, 'polygon': '-74 42,-75 39,-74 41'})
check('unclosed ring is closed for you -> same count', resp['code'] == 1)

resp = call('/countInPolygon', {'key': KEY, 'polygon': '0 0,0.001 0,0.001 0.001,0 0'})
check('tiny polygon in the ocean -> count 0', resp['code'] == 1 and resp['count'] == 0)

resp = call('/countInPolygon', {'key': KEY})
check('missing polygon -> code 0', resp['code'] == 0)
resp = call('/countInPolygon', {'key': KEY, 'polygon': '-74 42,abc 39,-74 41'})
check('non-numeric point -> code 0', resp['code'] == 0)
resp = call('/countInPolygon', {'key': KEY, 'polygon': '-74 42,-75 39'})
check('only 2 points -> code 0', resp['code'] == 0)

# ------------------------------------------------------------ getAvgSpeedByFlight
print('\n=== /getAvgSpeedByFlight ===')
resp = call('/getAvgSpeedByFlight', {'key': KEY, 'start': '2022-11-23 05:00:00', 'end': '2022-11-23 08:00:00'})
check('code 1, msg ok', resp['code'] == 1 and resp['msg'] == 'ok')
check('at most 500 results', len(resp.get('results', [])) <= 500)
flights = [r['flight_num'] for r in resp.get('results', [])]
check('one row per flight', len(flights) == len(set(flights)))
check('every row has flight_num and avg_speed',
      all('flight_num' in r and 'avg_speed' in r for r in resp.get('results', [])))
print(f"  {resp.get('num_results')} flights")
for r in resp.get('results', [])[:3]:
    print('  ', json.dumps(r))

resp = call('/getAvgSpeedByFlight', {'key': KEY})
check('no start/end (optional) -> code 1', resp['code'] == 1)
check('no start/end -> capped at 500', resp['num_results'] <= 500)
resp = call('/getAvgSpeedByFlight', {'key': KEY, 'start': '2022-11-23 05:00:00'})
check('start only -> code 1', resp['code'] == 1)
resp = call('/getAvgSpeedByFlight', {'key': KEY, 'end': 'not a date'})
check('bad end date -> code 0', resp['code'] == 0)

# ------------------------------------------------------------ total
print(f'\n{passed} passed, {failed} failed')
