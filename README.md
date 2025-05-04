# 🎲✨ Discord Betting Bot 🎰🔥

A session-based Discord betting bot built with 🐍 Python + ⚡ Nextcord, using **slash commands** and interactive UI. Users wager fake money on custom bets and track their stats across sessions!

---

## 💡 Features

- ✅ Fully slash-command powered (`/createbet`, `/startsession`, `/balance`, etc.)
- 🎯 Emoji-based betting with buttons (A–Z)
- 🔒 Lock, ❌ Cancel, and 🏁 Resolve bets using UI buttons
- 📊 Real-time stats tracking (session, last session, lifetime)
- 💰 Balance display and updates after bet resolution
- 🏆 Rankings (session and lifetime)
- 🤫 Ephemeral balance updates after each bet resolves
- 🔍 Autocomplete support for selecting open bets

---

## 🚀 Slash Commands

| Command               | Description                                  |
|-----------------------|----------------------------------------------|
| `/startsession`       | Start a new betting session                 |
| `/endsession`         | End the current session and display summary |
| `/createbet`          | Admin-only: Create a new bet with options   |
| `/balance`            | Show your balance and amount wagered        |
| `/stats`              | View your current session stats             |
| `/laststats`          | View your stats from the last session       |
| `/lifetimestats`      | View your all-time stats                    |
| `/rankings`           | Leaderboard for the current session         |
| `/lifetimerankings`   | All-time leaderboard                        |

---

## ⚙️ Setup

1. Clone the repo:
   ```bash
   git clone https://github.com/your-username/wagerbot.git
   cd wagerbot
   ```

2. Create a `.env` file:
   ```env
   DISCORD_BOT_TOKEN=your-token-here
   ```

3. Install dependencies:
   ```bash
   pip install nextcord python-dotenv
   ```

4. Run the bot:
   ```bash
   python bot.py
   ```

---

## 🧠 Notes

- Make sure the bot has message, embed, and interaction permissions

---

## 📅 Coming Soon

- Persistent stat and balance storage
- Bet history logs
- Bet expiry timers

---

## 💀 Disclaimer

This bot does **not** use real money.  
Use it responsibly, and don't make your friends cry. 😢🎉

---

## ✨ Now go forth and bet like champions. Or fools. You decide. 🎭