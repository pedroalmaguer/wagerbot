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
- 🎟️ **Moneyline odds support** for realistic sports betting (+150, -120 format)
- 🏆 **Leaderboards** for both session and wallet balances
- 💎 Special **multiplier rewards** (up to 2.5x) for wallet transfers
- ⏱️ Auto-closing transfer options with fun role assignments
- 🧠 Smart ephemeral responses showing win/loss results after each resolved bet
- 📊 Real-time stats tracking (session, last session, lifetime)
- 📂 Persistent storage via SQLite database
- 🔍 Autocomplete for faster bet selection
- 🤫 Clean ephemeral balance updates after bets resolve

---

## 🚀 Slash Commands

| Command               | Description                                          |
|------------------------|------------------------------------------------------|
| `/startsession`        | Start a new betting session with transfer options    |
| `/stopsession`         | End the current session and display summary         |
| `/createbet`           | Create a new session-based bet                      |
| `/funbet`              | Create a bet using persistent balances              |
| `/moneylinebet`        | Create a bet with American-style odds (+/-)         |
| `/balance`             | Show your session and persistent balance            |
| `/mywagers`            | View your current active wagers                     |
| `/wager`               | Place a wager on an active bet                      |
| `/leaderboard`         | View rankings of session or wallet balances         |


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

- Make sure the bot has message, embed, and interaction permissions
- Persistent data is saved in wagerbot.db SQLite database
- Bets created outside of sessions use persistent balance
- Fun bets allow ongoing, non-session wagering chaos
- Wallet transfers at session start get special multipliers at session end
- Moneyline odds work like real sportsbooks (+150 means bet 100 to win 150)


## 🎯 Odds System

The bot supports American-style moneyline odds:

- Positive odds (+150): Bet 100 credits to win 150 (plus your stake back)
- Negative odds (-120): Bet 120 credits to win 100 (plus your stake back)
- Format when creating bets: Team name|+150 or Team name|-120



## 📅 Coming Soon

- Bet expiry timers



## 💀 Disclaimer

This bot does **not** use real money.  
Use it responsibly. Make absurd bets. Laugh often.  
Made for my friends to make silly bets on sillier things.

---

## ✨ Bet boldly, win rarely, enjoy always. 🎭