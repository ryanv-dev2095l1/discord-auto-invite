# discord-auto-invite

I got tired of manually DMing invite links every time my friend group spun up a new temporary server. This watches for specific people joining and generates an invite I can paste.

## install

pip install -r requirements.txt

## usage

python discord_auto_invite.py --token YOUR_BOT_TOKEN --watch-user 123456789012345678

The bot needs the 'Create Instant Invite' permission in the target channel. It only generates invites, doesn't send DMs or auto-join anyone.

<!-- refreshed: 2026-10-05 -->
