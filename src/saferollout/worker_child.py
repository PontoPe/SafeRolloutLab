"""Only this short-lived process executes backtracking regular expressions."""
import json
import re
import resource
import sys

resource.setrlimit(resource.RLIMIT_CPU, (1, 1))
resource.setrlimit(resource.RLIMIT_AS, (96 * 1024 * 1024,) * 2)
resource.setrlimit(resource.RLIMIT_CORE, (0, 0))
resource.setrlimit(resource.RLIMIT_NOFILE, (16, 16))
resource.setrlimit(resource.RLIMIT_NPROC, (0, 0))
pattern, text = json.loads(sys.stdin.read(30000))
print(json.dumps({'matched': bool(re.search(pattern, text))}))
