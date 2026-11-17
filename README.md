# ADS-B Flight Data API (IA626)
**Author:** nesarar

## Files

| File | What it is |
| --- | --- |
| `main.py` | The API (Flask). Run it and leave it running. |
| `test-client.py` | Calls every endpoint and checks the answers (PASS/FAIL). |
| `setup_tables.sql` | Creates the `nesarar_auth` and `nesarar_api_logs` tables and adds key `123`. |
| `schemas/*.schema.json` | A JSON schema for each endpoint's response. |
| `config.example.yml` | Template for `config.yml` (the database login). |
| `requirements.txt` | Python packages. |

`config.yml` holds the database password, so it is listed in `.gitignore` and is **not** in this repo. 

## Setup

```bash
pip install -r requirements.txt
cp config.example.yml config.yml      # then put in the real host / user / password
```

Run `setup_tables.sql` once on the database (for example in phpMyAdmin's SQL tab). It creates the two tables below and inserts the key `123`.

## Running it

Use two terminals, one for the server and one for the client:

```bash
# terminal 1: start the API. It keeps running and waits for requests.
python main.py

# terminal 2: run the tests
python test-client.py
```

The API listens on `http://127.0.0.1:5000`, so only your own computer can call it.

## Requests

Base URL: `http://127.0.0.1:5000`

Every request needs `key=123`. A missing or wrong key gets `"code": 0, "msg": "auth error"`.

Dates use the format `YYYY-MM-DD HH:MM:SS`, e.g. `2022-11-23 05:28:10`. Browsers and `requests` encode the space for you (`%20`).

| Endpoint | Method | Arguments | What it returns |
| --- | --- | --- | --- |
| `/getData` | GET | `key`, `start` (**required**), `end` (**required**) | Data points with `date_time` from `start` to `end`, ordered by time. At most 500. |
| `/countInPolygon` | GET | `key`, `polygon` (**required**) | How many data points are inside the polygon. |
| `/getAvgSpeedByFlight` | GET | `key`, `start` (optional), `end` (optional) | Each flight's average ground speed (`gs`) over the period, ordered by flight number. At most 500. |

Example calls:

```
/getData?key=123&start=2022-11-23 05:28:10&end=2022-11-23 05:28:15
/countInPolygon?key=123&polygon=-74 42,-75 39,-74 41,-74 42
/getAvgSpeedByFlight?key=123&start=2022-11-23 05:00:00&end=2022-11-23 08:00:00
/getAvgSpeedByFlight?key=123
```

### Argument rules

- **`start` / `end`** must be valid date-times in the format above, and `start` cannot be after `end`.
  - For `/getAvgSpeedByFlight`, you can send both, only one, or neither. With `start` only, the period runs from `start` onwards. With `end` only, it runs up to `end`. With neither, all the data is used.
- **`polygon`** is a list of `x y` points (longitude, then latitude) separated by commas.
  - Every point must be two numbers, and you need at least 3 different points.
  - If the last point is not the same as the first, the API closes the ring for you.
  - The API checks every point is numeric before it builds the SQL. The polygon is then passed to MySQL as a query parameter, never pasted into the SQL text.

## Responses

Every response is JSON with these top-level keys:

| Key | Type | Meaning |
| --- | --- | --- |
| `code` | integer | `1` = successful, `0` = request failed |
| `msg` | string | `ok`, or why the request failed |
| `req` | string | Which method was requested, e.g. `/getData` |
| `sqltime` | number | Seconds the SQL query took, measured with `time.time()`. `0` if the request failed before the query ran. |

Successful responses add these keys:

| Endpoint | Extra keys |
| --- | --- |
| `/getData` | `start`, `end`, `num_results`, `results` (list of data points) |
| `/countInPolygon` | `polygon` (as WKT), `count` |
| `/getAvgSpeedByFlight` | `start`, `end` (`null` if not given), `num_results`, `results` (list of `fid`, `flight_num`, `avg_speed`, `num_points`) |

In `/getData` results, every column of `class_datapoints` is returned (`dpid`, `date_time`, `hex`, `flight_num`, `squawk`, `lat`, `lon`, `fid`, `gs`, `alt_gps`, `alt_baro`, `cat`, `track`, `nav_heading`) except `geo_point`, which is binary and can't go into JSON. Its values are already in `lat` and `lon`.

The full JSON schemas (draft-07) are in [`schemas/`](schemas/):
[getData](schemas/getData.schema.json) ·
[countInPolygon](schemas/countInPolygon.schema.json) ·
[getAvgSpeedByFlight](schemas/getAvgSpeedByFlight.schema.json)

### Example responses

`/getData?key=123&start=2022-11-23 05:28:10&end=2022-11-23 05:28:15`

```json
{
    "req": "/getData",
    "sqltime": 0.0006,
    "code": 1,
    "msg": "ok",
    "start": "2022-11-23 05:28:10",
    "end": "2022-11-23 05:28:15",
    "num_results": 1,
    "results": [
        {
            "dpid": 5112,
            "date_time": "2022-11-23 05:28:13",
            "hex": "a11d63",
            "squawk": "1573",
            "fid": 369,
            "lat": 40.919486,
            "lon": -73.637249,
            "gs": 273.02,
            "alt_gps": 37097,
            "alt_baro": 37097,
            "cat": "A3",
            "track": 141.8,
            "nav_heading": 141.8,
            "flight_num": "UAL1633"
        }
    ]
}
```

`/countInPolygon?key=123&polygon=-74 42,-75 39,-74 41,-74 42`

```json
{
    "req": "/countInPolygon",
    "sqltime": 0.0198,
    "code": 1,
    "msg": "ok",
    "polygon": "POLYGON((-74.0 42.0,-75.0 39.0,-74.0 41.0,-74.0 42.0))",
    "count": 1419
}
```

`/getAvgSpeedByFlight?key=123&start=2022-11-23 05:00:00&end=2022-11-23 08:00:00`

```json
{
    "req": "/getAvgSpeedByFlight",
    "sqltime": 0.0100,
    "code": 1,
    "msg": "ok",
    "start": "2022-11-23 05:00:00",
    "end": "2022-11-23 08:00:00",
    "num_results": 500,
    "results": [
        { "fid": 7, "flight_num": "AAL1009", "avg_speed": 229.08, "num_points": 6 },
        { "fid": 156, "flight_num": "AAL1015", "avg_speed": 375.16, "num_points": 4 }
    ]
}
```

A failed request (wrong key):

```json
{
    "req": "/getData",
    "sqltime": 0,
    "code": 0,
    "msg": "auth error"
}
```

*(The example numbers above come from a local test copy of the table. The real `class_datapoints` gives different values.)*

## Error messages

| Situation | `msg` |
| --- | --- |
| Missing or wrong key | `auth error` |
| `/getData` without `start` or `end` | `start and end are mandatory (format YYYY-MM-DD HH:MM:SS)` |
| Date in the wrong format | `start and end must be in the format YYYY-MM-DD HH:MM:SS` |
| `start` after `end` | `start must be before end` |
| No polygon | `polygon is mandatory, e.g. polygon=-74 42,-75 39,-74 41,-74 42` |
| Bad polygon point | `bad polygon: '<point>' is not an 'x y' point` / `is not numeric` |
| Fewer than 3 points | `bad polygon: polygon needs at least 3 distinct points` |

## Auth and logging

**Auth.** `auth(token)` looks up the request's `key` in `nesarar_auth`. The request is allowed only if exactly one row matches. Keys live in a table, not in the code, so they never end up on GitHub, and keys can be added or removed without changing the code.

```sql
CREATE TABLE `nesarar_auth` (
    `uid`   INT NOT NULL AUTO_INCREMENT PRIMARY KEY,
    `token` VARCHAR(64) NOT NULL UNIQUE,
    `email` VARCHAR(255) NULL
);
```

**Logging.** `log(token, endpoint, response)` adds one row to `nesarar_api_logs` for **every** request, both successes and failures. The date-time is set inside `log()`, so the endpoints don't have to pass it.

```sql
CREATE TABLE `nesarar_api_logs` (
    `logid`    INT NOT NULL AUTO_INCREMENT PRIMARY KEY,
    `endpoint` VARCHAR(100) NOT NULL,
    `token`    VARCHAR(64) NULL,
    `response` VARCHAR(50) NOT NULL,
    `dt`       DATETIME NOT NULL
);
```

The `response` column holds an HTTP-style status:

| Value | Meaning |
| --- | --- |
| `200` | Success |
| `400` | Bad or missing arguments |
| `401` | Auth error (missing or wrong key) |

The log is what rate limiting would be built on: count a token's rows in the last minute and refuse requests over the limit. The index on (`token`, `dt`) keeps that count fast.

## Test client

`test-client.py` checks every endpoint and prints PASS/FAIL for each check, then a total. It checks:

- A wrong or missing key gets `auth error` on all three endpoints.
- Every response has `code`, `msg`, `req` and `sqltime`, and `req` names the right endpoint.
- **`/getData`:** results fall between `start` and `end`, are sorted by time and are capped at 500 (a whole-day request returns exactly 500). A missing `end`, a bad date, or `start` after `end` all fail with `code` 0.
- **`/countInPolygon`:** the example polygon returns a whole-number count. An unclosed ring still works. A polygon with no aircraft in it returns 0. A missing polygon, a non-numeric point, or only 2 points all fail.
- **`/getAvgSpeedByFlight`:** one row per flight, at most 500. It also works with no dates or with only `start`. A bad date fails.

## The SQL behind each endpoint

All queries use `%s` parameters instead of pasted-in values.

```sql
-- /getData  (every column except the binary geo_point)
SELECT dpid, date_time, hex, flight_num, squawk, lat, lon, fid,
       gs, alt_gps, alt_baro, cat, track, nav_heading
FROM class_datapoints WHERE date_time BETWEEN %s AND %s
ORDER BY date_time, dpid LIMIT 0,500;

-- /countInPolygon
SELECT COUNT(*) FROM class_datapoints
WHERE ST_Within(geo_point, ST_GeomFromText(%s, 0));

-- /getAvgSpeedByFlight  (WHERE only includes the dates that were given)
SELECT fid, flight_num, AVG(gs) AS avg_speed, COUNT(*) AS num_points
FROM class_datapoints WHERE date_time >= %s AND date_time <= %s
GROUP BY fid, flight_num ORDER BY flight_num LIMIT 0,500;
```
