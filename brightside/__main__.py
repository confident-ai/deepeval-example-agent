import sys

from brightside.agent import respond

print(respond(" ".join(sys.argv[1:]) or "Do you open on Saturdays?"))
