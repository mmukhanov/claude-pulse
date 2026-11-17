# Start Claude Pulse from source without a console window: pyw claude_pulse.pyw
# pythonw has nowhere to show errors, so a failed start is written to
# %LOCALAPPDATA%\claude-pulse\error.log instead of vanishing.
import os
import sys
import time
import traceback

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
try:
    from claude_pulse.app import main

    main()
except SystemExit:
    raise
except BaseException:
    folder = os.path.join(os.environ.get("LOCALAPPDATA") or os.path.expanduser("~"), "claude-pulse")
    os.makedirs(folder, exist_ok=True)
    with open(os.path.join(folder, "error.log"), "a", encoding="utf-8") as log:
        log.write(time.strftime("%Y-%m-%d %H:%M:%S ") + " ".join(sys.argv) + "\n" + traceback.format_exc() + "\n")
    raise
