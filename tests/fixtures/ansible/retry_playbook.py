"""Run real Ansible with short backoffs only for synthetic I/O retry tests."""

import json
import os
import sys
import time
from pathlib import Path


class RetryClock:
    def __getattr__(self, name):
        return getattr(time, name)

    def sleep(self, seconds):
        with Path(os.environ["ANSIBLE_TEST_RETRY_LOG"]).open("a") as stream:
            stream.write(json.dumps(seconds) + "\n")
        time.sleep(min(seconds, 0.001))


if __name__ == "__main__":
    import ansible.executor.task_executor as executor
    from ansible.cli.playbook import main

    # Replace only this executor module's clock reference. Real lock tests,
    # remote processes, deadlines and monotonic time continue using real time.
    executor.time = RetryClock()
    sys.argv[0] = "ansible-playbook"
    main()
