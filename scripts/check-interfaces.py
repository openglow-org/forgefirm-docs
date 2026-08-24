#!/usr/bin/env python3
"""Interface coverage lint.

Will check out the kernel module and forgectrl at the revisions declared in
mkdocs.yml (extra.sources), extract every sysfs attribute, HTTP route, and
settings key, and fail if any lacks an anchor on the site. Placeholder until
the Technical section lands: passes unconditionally.
"""

import sys


def main() -> int:
    print("interfaces: placeholder, nothing checked yet")
    return 0


if __name__ == "__main__":
    sys.exit(main())
