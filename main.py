"""
IA626 - ADS-B Flask API
Author: nesarar

Run with:  python main.py
"""
import json, pymysql, time
from flask import Flask
from flask import request, redirect
import datetime
import yaml

app = Flask(__name__)

USERNAME = 'nesarar'
AUTH_TABLE = f'{USERNAME}_auth'
LOG_TABLE = f'{USERNAME}_api_logs'
DATA_TABLE = 'class_datapoints'   # the table Tyler loaded (400,002 rows)
# every column except geo_point, which is binary and can't go into JSON
COLUMNS = ['dpid', 'date_time', 'hex', 'flight_num', 'squawk', 'lat', 'lon', 'fid',
           'gs', 'alt_gps', 'alt_baro', 'cat', 'track', 'nav_heading']
DT_FORMAT = '%Y-%m-%d %H:%M:%S'
LIMIT = 500

db_config = None
with open("config.yml", "r") as file:
    config = yaml.safe_load(file)
    db_config = config['mysql']


# ---------------------------------------------------------------- helpers

def auth(token):
    """True if the token is in the auth table (exactly one row)."""
    if token is None:
        return False
    conn = pymysql.connect(**db_config)  # setup our credentials
    cur = conn.cursor(pymysql.cursors.DictCursor)
    sql = f'SELECT * FROM `{AUTH_TABLE}` WHERE `token` = %s;'
    cur.execute(sql, (token,))
    results = cur.fetchall()
    conn.close()
    if len(results) == 1:
        return True
    return False


def log(token, endpoint, response):
    """Insert one row into the request log. The date-time is set here, once."""
    conn = pymysql.connect(**db_config)  # setup our credentials
    cur = conn.cursor(pymysql.cursors.DictCursor)
    sql = f'INSERT INTO `{LOG_TABLE}` (`endpoint`,`token`,`response`,`dt`) VALUES (%s,%s,%s,%s)'
    dt = datetime.datetime.now().strftime(DT_FORMAT)
    cur.execute(sql, (endpoint, token, response, dt))
    conn.commit()  # in case autocommit is off in config.yml
    conn.close()


def fail(res, msg, http_code='400'):
    """Fill in a failed response, log it, and return the JSON string."""
    res['code'] = 0
    res['msg'] = msg
    log(request.args.get('key'), res['req'], http_code)
    return json.dumps(res, indent=4)


def parse_dt(value):
    """'2022-11-23 05:28:10' -> datetime, or None if it is not a valid date-time."""
    try:
        return datetime.datetime.strptime(value.strip(), DT_FORMAT)
    except Exception:
        return None


def parse_polygon(text):
    """'-74 42,-75 39,-74 41,-74 42' -> WKT 'POLYGON((-74.0 42.0, ...))'.
    Every point must be two numbers. The ring is closed if the last point
    is not the same as the first. Returns (wkt, None) or (None, error message)."""
    points = []
    for pair in text.split(','):
        parts = pair.split()
        if len(parts) != 2:
            return None, f"'{pair.strip()}' is not an 'x y' point"
        try:
            x = float(parts[0])
            y = float(parts[1])
        except ValueError:
            return None, f"'{pair.strip()}' is not numeric"
        points.append((x, y))
    if points and points[0] != points[-1]:
        points.append(points[0])  # close the ring
    if len(points) < 4:
        return None, 'polygon needs at least 3 distinct points'
    wkt = 'POLYGON((' + ','.join(f'{x} {y}' for x, y in points) + '))'
    return wkt, None


def clean(value):
    """Make a database value JSON friendly (dates -> strings, Decimal -> float)."""
    if isinstance(value, (datetime.datetime, datetime.date)):
        return value.strftime(DT_FORMAT)
    if isinstance(value, bytes):
        return None
    if hasattr(value, 'is_finite'):  # decimal.Decimal
        return float(value)
    return value


# ---------------------------------------------------------------- endpoints

@app.route("/", methods=['GET', 'POST'])
def root():
    res = {}
    res['code'] = 0
    res['msg'] = 'No endpoint specified'
    res['req'] = '/'
    res['sqltime'] = 0
    return json.dumps(res, indent=4)


@app.route("/getData", methods=['GET'])
def getData():
    res = {}
    res['req'] = '/getData'
    res['sqltime'] = 0
    if not auth(request.args.get('key')):
        return fail(res, 'auth error', '401')

    start = request.args.get('start')
    end = request.args.get('end')
    if start is None or end is None:
        return fail(res, 'start and end are mandatory (format YYYY-MM-DD HH:MM:SS)')
    start_dt = parse_dt(start)
    end_dt = parse_dt(end)
    if start_dt is None or end_dt is None:
        return fail(res, 'start and end must be in the format YYYY-MM-DD HH:MM:SS')
    if start_dt > end_dt:
        return fail(res, 'start must be before end')

    conn = pymysql.connect(**db_config)  # setup our credentials
    cur = conn.cursor(pymysql.cursors.DictCursor)
    cols = ','.join(f'`{c}`' for c in COLUMNS)
    sql = (f'SELECT {cols} FROM `{DATA_TABLE}` '
           f'WHERE `date_time` BETWEEN %s AND %s '
           f'ORDER BY `date_time`, `dpid` LIMIT 0,{LIMIT};')
    t0 = time.time()
    cur.execute(sql, (start_dt.strftime(DT_FORMAT), end_dt.strftime(DT_FORMAT)))
    rows = cur.fetchall()
    res['sqltime'] = time.time() - t0
    conn.close()

    items = []
    for row in rows:
        item = {}
        for k, v in row.items():
            item[k] = clean(v)
        items.append(item)

    res['code'] = 1
    res['msg'] = 'ok'
    res['start'] = start_dt.strftime(DT_FORMAT)
    res['end'] = end_dt.strftime(DT_FORMAT)
    res['num_results'] = len(items)
    res['results'] = items
    log(request.args.get('key'), res['req'], '200')
    return json.dumps(res, indent=4)


@app.route("/countInPolygon", methods=['GET'])
def countInPolygon():
    res = {}
    res['req'] = '/countInPolygon'
    res['sqltime'] = 0
    if not auth(request.args.get('key')):
        return fail(res, 'auth error', '401')

    polygon = request.args.get('polygon')
    if polygon is None or polygon.strip() == '':
        return fail(res, 'polygon is mandatory, e.g. polygon=-74 42,-75 39,-74 41,-74 42')
    wkt, err = parse_polygon(polygon)
    if err is not None:
        return fail(res, 'bad polygon: ' + err)

    conn = pymysql.connect(**db_config)  # setup our credentials
    cur = conn.cursor(pymysql.cursors.DictCursor)
    # geo_point is POINT(lon lat), the same x y order as the polygon
    sql = (f'SELECT COUNT(*) AS `cnt` FROM `{DATA_TABLE}` '
           f'WHERE ST_Within(`geo_point`, ST_GeomFromText(%s, 0));')
    t0 = time.time()
    try:
        cur.execute(sql, (wkt,))
        row = cur.fetchone()
    except pymysql.MySQLError as e:
        conn.close()
        res['sqltime'] = time.time() - t0
        return fail(res, 'database rejected the polygon: ' + str(e.args[-1]))
    res['sqltime'] = time.time() - t0
    conn.close()

    res['code'] = 1
    res['msg'] = 'ok'
    res['polygon'] = wkt
    res['count'] = int(row['cnt'])
    log(request.args.get('key'), res['req'], '200')
    return json.dumps(res, indent=4)


@app.route("/getAvgSpeedByFlight", methods=['GET'])
def getAvgSpeedByFlight():
    res = {}
    res['req'] = '/getAvgSpeedByFlight'
    res['sqltime'] = 0
    if not auth(request.args.get('key')):
        return fail(res, 'auth error', '401')

    # start and end are optional here; use whichever ones were given
    start = request.args.get('start')
    end = request.args.get('end')
    start_dt = None
    end_dt = None
    if start is not None and start.strip() != '':
        start_dt = parse_dt(start)
        if start_dt is None:
            return fail(res, 'start must be in the format YYYY-MM-DD HH:MM:SS')
    if end is not None and end.strip() != '':
        end_dt = parse_dt(end)
        if end_dt is None:
            return fail(res, 'end must be in the format YYYY-MM-DD HH:MM:SS')
    if start_dt is not None and end_dt is not None and start_dt > end_dt:
        return fail(res, 'start must be before end')

    where = []
    params = []
    if start_dt is not None:
        where.append('`date_time` >= %s')
        params.append(start_dt.strftime(DT_FORMAT))
    if end_dt is not None:
        where.append('`date_time` <= %s')
        params.append(end_dt.strftime(DT_FORMAT))
    where_sql = ('WHERE ' + ' AND '.join(where)) if where else ''

    conn = pymysql.connect(**db_config)  # setup our credentials
    cur = conn.cursor(pymysql.cursors.DictCursor)
    sql = (f'SELECT `fid`, `flight_num`, AVG(`gs`) AS `avg_speed`, COUNT(*) AS `num_points` '
           f'FROM `{DATA_TABLE}` {where_sql} '
           f'GROUP BY `fid`, `flight_num` ORDER BY `flight_num` LIMIT 0,{LIMIT};')
    t0 = time.time()
    cur.execute(sql, params)
    rows = cur.fetchall()
    res['sqltime'] = time.time() - t0
    conn.close()

    items = []
    for row in rows:
        item = {}
        item['fid'] = row['fid']
        item['flight_num'] = row['flight_num']
        item['avg_speed'] = None if row['avg_speed'] is None else round(float(row['avg_speed']), 2)
        item['num_points'] = int(row['num_points'])
        items.append(item)

    res['code'] = 1
    res['msg'] = 'ok'
    res['start'] = None if start_dt is None else start_dt.strftime(DT_FORMAT)
    res['end'] = None if end_dt is None else end_dt.strftime(DT_FORMAT)
    res['num_results'] = len(items)
    res['results'] = items
    log(request.args.get('key'), res['req'], '200')
    return json.dumps(res, indent=4)


if __name__ == "__main__":
    # 127.0.0.1 = only your own computer can call it (what Tyler said to use)
    app.run(host='127.0.0.1', debug=True)
