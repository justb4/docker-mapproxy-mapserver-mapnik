# geopackage.py fixes

See issue #3.

## Problem 1: locking errors

During seeding sometimes this error and seeder worker process dies/becomes zombie:

```
Process TileSeedWorker-1:
Traceback (most recent call last):
  File "/usr/lib/python3.7/multiprocessing/process.py", line 297, in _bootstrap
    self.run()
  File "/usr/local/lib/python3.7/dist-packages/mapproxy/seed/seeder.py", line 143, in run
    self.work_loop()
  File "/usr/local/lib/python3.7/dist-packages/mapproxy/seed/seeder.py", line 158, in work_loop
    exceptions=(SourceError, IOError), ignore_exceptions=(LockTimeout, ))
  File "/usr/local/lib/python3.7/dist-packages/mapproxy/seed/util.py", line 189, in exp_backoff
    result = func(*args, **kw)
  File "/usr/local/lib/python3.7/dist-packages/mapproxy/cache/tile.py", line 141, in load_tile_coords
    rescale_till_zoom=rescale_till_zoom, rescaled_tiles={},
  File "/usr/local/lib/python3.7/dist-packages/mapproxy/cache/tile.py", line 162, in _load_tile_coords
    self.cache.load_tiles(tiles, with_metadata)
  File "/usr/local/lib/python3.7/dist-packages/mapproxy/cache/geopackage.py", line 569, in load_tiles
    return self._get_level(level).load_tiles(tiles, with_metadata=with_metadata, dimensions=dimensions)
  File "/usr/local/lib/python3.7/dist-packages/mapproxy/cache/geopackage.py", line 447, in load_tiles
    cursor = self.db.cursor()
  File "/usr/local/lib/python3.7/dist-packages/mapproxy/cache/geopackage.py", line 52, in db
    self.ensure_gpkg()
  File "/usr/local/lib/python3.7/dist-packages/mapproxy/cache/geopackage.py", line 102, in ensure_gpkg
    if not self.check_gpkg():
  File "/usr/local/lib/python3.7/dist-packages/mapproxy/cache/geopackage.py", line 107, in check_gpkg
    if not self._verify_table():
  File "/usr/local/lib/python3.7/dist-packages/mapproxy/cache/geopackage.py", line 118, in _verify_table
    (self.table_name,))
sqlite3.OperationalError: database is locked

```
### Analysis

The lock error is thrown in `_verify_table()`. Think this is the line:

```python
with sqlite3.connect(self.geopackage_file) as db:
    cur = db.execute("""SELECT name FROM sqlite_master WHERE type='table' AND name=?""",

```

Two problems IMHO:

* no `timeout` param is specified like in the conn-caching property function: `self._db_conn_cache.db = sqlite3.connect(self.geopackage_file, timeout=self.timeout)`
* `ensure_gpkg()` is called many times, while `self._db_conn_cache.db` (Thread local storage) may be available

### Fixes

Use timeouts: `with sqlite3.connect(self.geopackage_file, timeout=self.timeout) as db:
`
### Related MapProxy issue/PR

TO BE DONE.
Once available in a version, this patch can be removed.

## Problem 2: seeding performance

Too slow often like 1500-5000 tiles/minute (with Mapnik and PostGIS). 

### Analysis
Apart from disabling cache lock (remove `--use-cache-lock`) in MP seeder script, some simple sqlite `PRAGMA` settings increased speed enormously:

```python
self._db_conn_cache.db.execute('PRAGMA synchronous=OFF')
self._db_conn_cache.db.execute('PRAGMA journal_mode=MEMORY')
```

Small areas (muiden) tests
```
Timing Muiden Seed
24-05-30 12:49:09 12:56:22 7 min 
24-05-30 13:14:26 13:20:08 6 min - leave out --use-cache-lock
24-05-30 13:22:53 13:27:51 5 min - leave out --use-cache-lock+full CPU usage for workers (doubled) lock error
24-05-30 13:37:14 13:42:14 5 min - with --use-cache-lock + full CPU usage for workers (doubled) lock error

New geopackage locking error fix

24-05-30 16:32:48 16:37:48 5 min - leave out --use-cache-lock+full CPU usage for workers (doubled) lock error
24-05-30 17:38:36 17:41:48 3 min  - ditto geopackage.py with PRAGMAs: synchronous=OFF journal_mode=MEMORY
```

Full Netherlands tests. 
```
12 workers all CPUs - but all in 100% load load average around 12: 5% in about 5 mins, about 60000 tiles/min
[17:48:23]  0   0.00% -20000.00000, 275000.00000, 300000.00000, 650000.00000 (0 tiles)
[17:48:53] 12   1.71% -4989.76000, 641913.28000, -3269.44000, 643633.60000 (32896 tiles)
[17:49:23] 12   2.08% -8430.40000, 628150.72000, -6710.08000, 629871.04000 (66576 tiles)
[17:49:53] 12   2.33% 15654.08000, 629871.04000, 17374.40000, 631591.36000 (94560 tiles)
[17:50:23] 12   2.79% 25976.00000, 638472.64000, 27696.32000, 640192.96000 (128496 tiles)
[17:50:53] 12   3.04% 36297.92000, 633311.68000, 38018.24000, 635032.00000 (156480 tiles)
[17:51:24] 12   3.74% -20000.00000, 604066.24000, -18752.32000, 605786.56000 (190176 tiles)
[17:51:54] 11   4.64% -17032.00000, 573100.48000, -13591.36000, 576541.12000 (226560 tiles)
[17:52:24] 12   4.81% 8772.80000, 621269.44000, 10493.12000, 622989.76000 (256272 tiles)
[17:52:54] 12   4.92% -1549.12000, 609227.20000, 171.20000, 610947.52000 (281536 tiles)
[17:53:24] 12   5.03% 15654.08000, 607506.88000, 17374.40000, 609227.20000 (305408 tiles)

6 workers half of CPUs load average around 6: 5% in about 7 mins, about 45000 tiles/min
[17:59:12]  0   0.00% -20000.00000, 275000.00000, 300000.00000, 650000.00000 (0 tiles)
[17:59:42] 12   1.50% -15311.68000, 628150.72000, -13591.36000, 629871.04000 (23760 tiles)
[18:00:12] 11   1.93% 10493.12000, 641913.28000, 13933.76000, 645353.92000 (49184 tiles)
[18:00:43] 12   2.13% -3269.44000, 628150.72000, -1549.12000, 629871.04000 (71696 tiles)
[18:01:13] 12   2.31% 15654.08000, 633311.68000, 17374.40000, 635032.00000 (91840 tiles)
[18:01:43] 10   2.69% 38018.24000, 641913.28000, 44899.52000, 648794.56000 (116560 tiles)
[18:02:13] 12   2.88% 22535.36000, 628150.72000, 24255.68000, 629871.04000 (138032 tiles)
[18:02:44] 12   3.06% 31136.96000, 628150.72000, 32857.28000, 629871.04000 (158176 tiles)
[18:03:14] 12   3.54% -20000.00000, 610947.52000, -18752.32000, 612667.84000 (182240 tiles)
[18:03:44] 12   4.21% -17032.00000, 590303.68000, -15311.68000, 592024.00000 (208624 tiles)
[18:04:14] 12   4.71% -4989.76000, 621269.44000, -3269.44000, 622989.76000 (234432 tiles)
[18:04:45] 11   4.80% 7052.48000, 621269.44000, 10493.12000, 624710.08000 (255264 tiles)
[18:05:15]  9   4.88% -10150.72000, 600625.60000, 3611.84000, 614388.16000 (273024 tiles)
[18:05:45] 12   4.98% 171.20000, 600625.60000, 1891.52000, 602345.92000 (294144 tiles)
[18:06:16] 12   5.05% 5332.16000, 600625.60000, 7052.48000, 602345.92000 (309504 tiles)
```

Latter gives nice view with `htop`, all busy but not too, memory ok:

![image](https://github.com/justb4/docker-mapproxy-mapserver-mapnik/assets/582630/c8c4710e-8aa2-49bf-b7dd-2e31e842ce95)

So about a 10-fold performance improvement. Question: how safe are these `PRAGMA`s?

## Commands

The version from `master` fetched on May 30, 2024 which is the version in MapProxy 2.0.2.
Will do real patch later.
Now just copy [geopackage.py](geopackage.py) as is into Dockerfile MapProxy installation.

So this for later:

The patch generation and how applied:
``` 
diff -u geopackage-2.0.2.py geopackage-patched.py  > geopackage.patch

# to be independent of Python version and MP install location
patch $(find /usr -type f -name geopackage.py | grep mapproxy/cache) geopackage.patch
```

