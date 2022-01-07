"""
sentinel for explorer

Cron sentinel / @bitsignal
To be run every minute.
Updated for Python3.7 by default
add to crontab: '* * * * * cd /path/to/explorer/directory/html;python3.7 sentinel.py'
"""
import subprocess

# Edit this if you are not using the standard invocation
PYTHON_EXECUTABLE='python3.7'

list_ = subprocess.getoutput("screen -ls")
try:
    if ".explorer\t" not in list_:
        print("Restarting stopped explorer...")
        data = subprocess.getoutput('screen -d -S explorer -m bash -c "{} explorebis.py" -X quit'.format(PYTHON_EXECUTABLE))
        print("started")
except:
    pass