"""Constants for the Halox Smart integration.

The values below are public client constants shipped inside the vendor's
Android app (package com.livsmartautomation.livsmart). They are identical for
every Halox Smart user and contain no account-specific information. A user only
ever supplies their own email + password.
"""

DOMAIN = "halox"

# REST backend used by the official app (v5+). The earlier AWS API-Gateway
# host (8fhy9ntc6c.execute-api.ap-south-1.amazonaws.com) is deprecated.
API_BASE = "https://livsmart-origin.thelivsmart.com/api/v1"

# Firebase project the app authenticates against (Google Identity Platform).
# A Firebase Web API key is a public client identifier, not a secret.
FIREBASE_API_KEY = "AIzaSyDB5hEoRXDXlZhtnITfNLw2DdNBCMnucLM"
ANDROID_PACKAGE = "com.livsmartautomation.livsmart"

IDENTITY_URL = "https://identitytoolkit.googleapis.com/v1"
SECURETOKEN_URL = "https://securetoken.googleapis.com/v1/token"

# Config entry keys
CONF_REFRESH_TOKEN = "refresh_token"

DEFAULT_SCAN_INTERVAL = 30  # seconds
