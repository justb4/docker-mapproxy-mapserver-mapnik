# geopackage.py fixes

# What this solves

## Problem: locking errors

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
## Analysis

The lock error is thrown in `_verify_table()`. Think this is the line:

```python
with sqlite3.connect(self.geopackage_file) as db:
    cur = db.execute("""SELECT name FROM sqlite_master WHERE type='table' AND name=?""",

```

Two problems IMHO:

* no `timeout` param is specified like in the conn-caching property function: `self._db_conn_cache.db = sqlite3.connect(self.geopackage_file, timeout=self.timeout)`
* `ensure_gpkg()` is called many times, while `self._db_conn_cache.db` (Thread local storage) may be available

## Fixes

Use timeouts: `with sqlite3.connect(self.geopackage_file, timeout=self.timeout) as db:
`
# Related MapProxy issue/PR

TO BE DONE.
Once available in a version, this patch can be removed.

# Commands

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

