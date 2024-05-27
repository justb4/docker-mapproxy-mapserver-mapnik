# mapnik.py fixes

## Auto-Reloading Mapnik Config

Reload config whenever changed on filestystem.

See #https://github.com/mapproxy/mapproxy/pull/447.
[mapnik.py-pr447](mapnik-pr447.py) is from that PR. 
It implements a very efficient multiprocessing/threading
way to use Mapnik Source.

This enhancement is now in recent versions like 2.0.2.

This file has been further improved by @justb4 to listen to Mapnik config 
changes: [mapnik.py](mapnik.py) using [Watchdog](https://github.com/gorakhargosh/watchdog).
Mapnik will reload config whenever any file changes in the Mapnik config tree.
This allows a quick edit/show result cycle when developing Mapnik styles.

### Results

With/without `mapnik-patched.py` from `mapnik-2.0.2.py` (2.0.2 version) .

Test 1 Config:

- MAPPROXY_PROCESSES=1
- MAPPROXY_THREADS=1
- WMS area: 24 sec met PR, 83 sec zonder

Test 2 Config:

- MAPPROXY_PROCESSES=4
- MAPPROXY_THREADS=4
- WMS area:  20 sec met PR,  75 sec sec zonder

Test 3 Config 
- in python-mapnik direct 0.6 sec! So big improvement

### Listening for config changes - inotify problems

See  
https://github.com/guard/listen/blob/master/README.md#increasing-the-amount-of-inotify-watchers (gaat niet om dit programma, maar deze uitleg en de settings die je kunt doen. )
so:

`cat /proc/sys/fs/inotify/max_user_watches`

is usually 8192, can be increased.
Docker Container takes that setting from the Host.
Similar setting used with Dropbox problems.
So:

```
sudo sh -c "echo fs.inotify.max_user_watches=524288 >> /etc/sysctl.conf"
sudo sysctl -p


```
Added script to show 'watchers': [inotify-consumers.sh](inotify-consumers.sh)

Still did not help. Now using Polling Observer, 
no platform-interaction needed like `inotify`.
Hopefully no issues:

```
# Use Python-based polling Observer, should be ok
from watchdog.observers.polling import PollingObserver as Observer

# This gave issues on Ubuntu, eating to many inotify instances
# from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler


```

## Assign srs to Mapnik pobject

Error: *ERROR - mapproxy.source.mapnik - could not render Mapnik map: failed to initialize projection with: '+init=epsg:28992'*

```python
m.srs = '+init=%s' % str(query.srs.srs_code.lower())

# must become
m.srs = str(query.srs.srs_code.lower())

```
# Related PR

TO BE DONE.
Once this is available in a version, this patch can be removed.

# Commands

The version from `master` fetched on May 24, 2024 which is the version in MapProxy 2.0.2.
Will do this later, too involved now, just copy [mapnik.py](mapnik.py) as here.

So this for later:

The patch generation and how applied:
``` 
diff -u mapnik-2.0.2.py mapnik-patched.py  > mapnik.patch

# to be independent of Python version and MP install location
patch $(find /usr -type f -name mapnik.py) mapnik.patch
```

