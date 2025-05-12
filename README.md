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
- 📂 Persistent storage via SQLite database
- 🔍 Autocomplete for faster bet selection
- 🤫 Clean ephemeral balance updates after bets resolve

---

## 🚀 Slash Commands

| Command               | Description                                          |
|------------------------|------------------------------------------------------|
| `/startsession`        | Start a new betting session                         |
| `/stopsession`         | End the current session and display summary         |
| `/createbet`           | Create a new session-based bet                      |
| `/funbet`              | Create a bet using persistent balances              |
| `/balance`             | Show your session and persistent balance            |
| `/mywagers`            | View your current active wagers                     |
| `/wager`               | Place a wager on an active bet                      |

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
   DISCORD_APPLICATION_ID=your-application-id-here
   ```

3. Install dependencies:
   ```bash
   pip install nextcord python-dotenv aiosqlite
   ```

4. Initialize the database:
   ```bash
   python init_db.py
   ```

5. Run the bot:
   ```bash
   python wagerbot.py
   ```

---

## 🧠 Notes

- Make sure the bot has **message**, **embed**, and **interaction** permissions
- Persistent data is saved in `wagerbot.db` SQLite database
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