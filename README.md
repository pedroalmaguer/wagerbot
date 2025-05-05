# 🎲✨ Discord Betting Bot 🎰🔥

A session-based **and standalone** Discord betting bot built with 🐍 Python + ⚡ Nextcord, using **slash commands** and an interactive UI. Users wager fake currency on custom bets and track their stats and balances across and between sessions!

---

## 💡 Features

- ✅ Fully **slash-command** powered (`/createbet`, `/startsession`, `/balance`, etc.)
- 🎯 Emoji-based betting with buttons (A–Z)
- 🔒 Lock, ❌ Cancel, and 🏁 Resolve bets using UI buttons
- 💰 Two balance types: 
  - **Session balance** (resets each session)
  - **Persistent balance** (used for fun bets outside sessions)
- 🧠 Smart ephemeral responses showing win/loss results after each resolved bet
- 📊 Real-time stats tracking (session, last session, lifetime)
- 🏆 Rankings (session and lifetime)
- 📂 Persistent storage via `data.json` (auto-saved and loaded)
- 🔍 Autocomplete for faster bet selection
- 🤫 Clean ephemeral balance updates after bets resolve

---

## 🚀 Slash Commands

| Command               | Description                                          |
|------------------------|------------------------------------------------------|
| `/startsession`        | Start a new betting session                         |
| `/endsession`          | End the current session and display summary         |
| `/createbet`           | Admin-only: Create a new session-based bet          |
| `/funbet`              | Admin-only: Create a bet using persistent balances  |
| `/balance`             | Show your session and persistent balance            |
| `/stats`               | View your current session stats                     |
| `/laststats`           | View your stats from the last session               |
| `/lifetimestats`       | View your all-time stats                            |
| `/rankings`            | Leaderboard for the current session                 |
| `/lifetimerankings`    | All-time leaderboard                                |

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
   python wagerbot.py
   ```

---

## 🧠 Notes

- Make sure the bot has **message**, **embed**, and **interaction** permissions
- Persistent data is saved in `data.json`
- Bets created outside of sessions use persistent balance
- Fun bets allow ongoing, non-session wagering chaos

---

## 📅 Coming Soon

- Bet expiry timers
- User-defined odds or multipliers

---

## 💀 Disclaimer

This bot does **not** use real money.  
Use it responsibly. Make absurd bets. Laugh often.  
Made for my friends to make silly bets on sillier things.

---

## ✨ Bet boldly, win rarely, enjoy always. 🎭
