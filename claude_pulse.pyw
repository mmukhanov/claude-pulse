# Start Claude Pulse from source without a console window: pythonw claude_pulse.pyw
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from claude_pulse.app import main  # noqa: E402

main()
