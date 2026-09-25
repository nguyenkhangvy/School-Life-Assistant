"""Secrets live only in the OS credential store (Windows Credential Manager).

Nothing here writes a secret to a file, a log, the command line or our server.
"""

import keyring
from keyring.errors import PasswordDeleteError

from sla_agent.log import protect

EDUSOFT_SERVICE = "SchoolLifeAssistant-EduSoft"  # username = student ID
DEVICE_KEY_SERVICE = "SchoolLifeAssistant-DeviceKey"  # username = web app address


def save_edusoft(student_id, password):
    protect(password)
    keyring.set_password(EDUSOFT_SERVICE, student_id, password)


def load_edusoft(student_id):
    password = keyring.get_password(EDUSOFT_SERVICE, student_id)
    protect(password)
    return password


def save_device_key(server_url, key):
    protect(key)
    keyring.set_password(DEVICE_KEY_SERVICE, server_url, key)


def load_device_key(server_url):
    key = keyring.get_password(DEVICE_KEY_SERVICE, server_url)
    protect(key)
    return key


def forget(student_id, server_url):
    for service, username in ((EDUSOFT_SERVICE, student_id), (DEVICE_KEY_SERVICE, server_url)):
        if username:
            try:
                keyring.delete_password(service, username)
            except PasswordDeleteError:
                pass
