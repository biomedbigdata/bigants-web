#!/usr/bin/env python
import os
import sys

if __name__ == "__main__":
    os.environ.get('C_FORCE_ROOT', 'true')
    os.environ.get("DJANGO_SETTINGS_MODULE", "BiCoN_web.settings.development")
    try:
        from django.core.management import execute_from_command_line
    except ImportError:
        raise ImportError(
            "Couldn't import Django. Are you sure it's installed and "
            "available on your PYTHONPATH environment variable? Did you "
            "forget to activate a virtual environment?"
        )
    execute_from_command_line(sys.argv)
