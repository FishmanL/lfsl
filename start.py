#C:\Users\leorf\Miniconda2\python.exe

import os
import sys
import shutil

def main(args):
    if len(args) != 2:
        print("Usage: start.py TEAMNAME")

        sys.exit(1)

    teamname = args[1].lower()

    src = 'dummy.py'
    files = ['std', 'tyrant', 'propshare', 'tourney']

    
    for f in files:
        dst = "{}{}.py".format(teamname, f)
        print("Copying {} to {}...".format(src, dst))
        shutil.copyfile(src, dst)

    print("All done.  Code away!")

if __name__ == "__main__":
    main(sys.argv)
