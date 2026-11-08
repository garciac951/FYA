"""One-time: get a YouTube refresh token for the uploader.

Run this on YOUR computer (it opens a browser to sign in):

    pip install google-auth-oauthlib
    python scripts/youtube_auth.py path/to/client_secret.json

Sign in with the Google account that owns the channel, pick the channel, allow access.
It prints YT_CLIENT_ID, YT_CLIENT_SECRET and YT_REFRESH_TOKEN to save as GitHub secrets.
"""
import json
import sys

from google_auth_oauthlib.flow import InstalledAppFlow

SCOPES = ["https://www.googleapis.com/auth/youtube.upload"]


def main() -> None:
    if len(sys.argv) != 2:
        sys.exit(__doc__)
    secrets_file = sys.argv[1]
    flow = InstalledAppFlow.from_client_secrets_file(secrets_file, SCOPES)
    creds = flow.run_local_server(port=0, access_type="offline", prompt="consent")
    info = json.load(open(secrets_file))
    client = info.get("installed") or info.get("web")
    print("\nSave these as GitHub repository secrets (Settings > Secrets and variables > Actions):\n")
    print(f"YT_CLIENT_ID={client['client_id']}")
    print(f"YT_CLIENT_SECRET={client['client_secret']}")
    print(f"YT_REFRESH_TOKEN={creds.refresh_token}")


if __name__ == "__main__":
    main()
