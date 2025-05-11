import os
import json
import aiosqlite
import nextcord
from nextcord.ext import commands
from nextcord.ui import View, Button, Modal, TextInput, Select
from datetime import datetime
from dotenv import load_dotenv
from datetime import datetime, timezone

# Intents and bot setup
intents = nextcord.Intents.default()
intents.message_content = True
intents.members = True
bot = commands.Bot(intents=intents)

DB_FILE = "wagerbot.db"

# Load .env
load_dotenv()

# Emojis for options
EMOJI_MAP = [
    "🇦", "🇧", "🇨", "🇩", "🇪", "🇫", "🇬", "🇭",
    "🇮", "🇯", "🇰", "🇱", "🇲", "🇳", "🇴", "🇵",
    "🇶", "🇷", "🇸", "🇹", "🇺", "🇻", "🇼", "🇽",
    "🇾", "🇿"
]


class WagerModal(Modal):
    def __init__(self, option_label, bet_id, use_wallet=False):
        super().__init__(title=f"Wager on '{option_label}'")
        self.option_label = option_label
        self.bet_id = bet_id
        self.use_wallet = use_wallet
        self.amount = TextInput(label="Enter your wager amount", required=True)
        self.add_item(self.amount)

    async def callback(self, interaction: nextcord.Interaction):
        user_id = interaction.user.id
        session_id = await get_active_session_id()

        try:
            amount = int(self.amount.value)
            if amount <= 0:
                raise ValueError
        except ValueError:
            await interaction.response.send_message("Invalid amount.", ephemeral=True)
            return

        # Fetch option_id matching the label
        option = await db_fetchone(
            "SELECT id FROM bet_options WHERE label = ? AND prop_id = ?",
            (self.option_label, self.bet_id)
        )
        if not option:
            await interaction.response.send_message("Option not found.", ephemeral=True)
            return

        option_id = option[0]

        # Decide which balance to use
        if self.use_wallet:
            balance_row = await db_fetchone("SELECT balance FROM wallet WHERE user_id = ?", (user_id,))
            balance = balance_row[0] if balance_row else 1000
        else:
            balance_row = await db_fetchone("SELECT balance FROM bankroll WHERE user_id = ? AND session_id = ?", (user_id, session_id))
            balance = balance_row[0] if balance_row else 1000

        if amount > balance:
            await interaction.response.send_message("Insufficient balance.", ephemeral=True)
            return

        # Deduct balance
        if self.use_wallet:
            await db_execute("UPDATE wallet SET balance = balance - ? WHERE user_id = ?", (amount, user_id))
        else:
            await db_execute("UPDATE bankroll SET balance = balance - ? WHERE user_id = ? AND session_id = ?", (amount, user_id, session_id))

        # Insert wager
        await db_execute(
            "INSERT INTO wagers (user_id, session_id, prop_id, prop_option_id, amount, odds, result, payout) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            (user_id, session_id, self.bet_id, option_id, amount, 100, 'pending', 0)
        )

        print(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] [💸] {interaction.user.display_name} wagered {amount} on '{self.option_label}'")

        await interaction.response.send_message(
            f"Successfully wagered {amount} credits on {self.option_label}.",
            ephemeral=True
        )

class WagerButton(Button):
    def __init__(self, label: str, option_label: str, bet_id: int, use_wallet: bool = False):
        super().__init__(label=label, style=nextcord.ButtonStyle.primary)
        self.option_label = option_label
        self.bet_id = bet_id
        self.use_wallet = use_wallet

    async def callback(self, interaction: nextcord.Interaction):
        await interaction.response.send_modal(WagerModal(self.option_label, self.bet_id, self.use_wallet))


class CreateBetModal(Modal):
    def __init__(self):
        super().__init__(title="Create a New Bet")

        self.bet_question = TextInput(
            label="Bet Question",
            placeholder="E.g., 'Will it rain tomorrow?'",
            required=True,
            max_length=200
        )
        self.bet_options = TextInput(
            label="Options (one per line, max 8)",
            placeholder="Option 1\nOption 2\nOption 3...",
            required=True,
            style=nextcord.TextInputStyle.paragraph,
            max_length=800
        )

        self.add_item(self.bet_question)
        self.add_item(self.bet_options)

    async def callback(self, interaction: nextcord.Interaction):
        session_row = await db_fetchone(
            "SELECT id FROM sessions WHERE is_active = 1 ORDER BY id DESC LIMIT 1"
        )
        if not session_row:
            await interaction.response.send_message("⚠️ No active session.", ephemeral=True)
            return
        session_id = session_row[0]

        options = [opt.strip() for opt in self.bet_options.value.split("\n") if opt.strip()]
        
        if len(options) < 2:
            await interaction.response.send_message("⚠️ You must provide at least 2 options.", ephemeral=True)
            return
        if len(options) > 8:
            await interaction.response.send_message("⚠️ You can provide at most 8 options.", ephemeral=True)
            return

        # Insert the bet
        await db_execute(
            "INSERT INTO bet (session_id, name, description, bet_type, is_resolved) VALUES (?, ?, ?, ?, 0)",
            (session_id, self.bet_question.value, "User created bet", "moneyline")
        )

        bet_row = await db_fetchone("SELECT id FROM bet WHERE name = ? ORDER BY id DESC LIMIT 1", (self.bet_question.value,))
        bet_id = bet_row[0]

        for label in options:
            await db_execute(
                "INSERT INTO bet_options (prop_id, label, odds) VALUES (?, ?, 100)",
                (bet_id, label)
            )

        description = f"**{self.bet_question.value}**\n"
        for idx, label in enumerate(options):
            description += f"{EMOJI_MAP[idx]} {label}\n"

        embed = nextcord.Embed(
            title="💬 New Bet Created!",
            description=description,
            color=nextcord.Color.blue()
        )

        view = View(timeout=None)

        # Add wager buttons
        for idx, label in enumerate(options):
            emoji = EMOJI_MAP[idx]
            view.add_item(WagerButton(label=f"{emoji} {label}", option_label=label, bet_id=bet_id))

        # Add admin control buttons
        view.add_item(ResolveBetButton(bet_id))
        view.add_item(LockBetButton(bet_id))
        view.add_item(CancelBetButton(bet_id))

        await interaction.response.send_message(embed=embed, view=view)


class ResolveBetButton(Button):
    def __init__(self, bet_id):
        super().__init__(label="🏁 Resolve Bet", style=nextcord.ButtonStyle.primary)
        self.bet_id = bet_id

    async def callback(self, interaction: nextcord.Interaction):
        # Fetch all options for the bet
        options_rows = await db_fetchall(
            "SELECT id, label FROM bet_options WHERE prop_id = ?",
            (self.bet_id,)
        )
        if not options_rows:
            await interaction.response.send_message("⚠️ No options found for this bet.", ephemeral=True)
            return

        # Build Select Options
        select_options = [
            nextcord.SelectOption(label=label, value=str(option_id))
            for option_id, label in options_rows
        ]

        view = ResolveBetView(self.bet_id, select_options)

        await interaction.response.send_message(
            "Please select the winning option:",
            view=view,
            ephemeral=True
        )

class LockBetButton(Button):
    def __init__(self, bet_id: int):
        super().__init__(label="🔒 Lock Bet", style=nextcord.ButtonStyle.success)
        self.bet_id = bet_id

    async def callback(self, interaction: nextcord.Interaction):
        await db_execute("UPDATE bet SET is_resolved = 1 WHERE id = ?", (self.bet_id,))
        await interaction.response.send_message("✅ Bet has been locked (no more wagers).", ephemeral=True)

class ResolveBetButton(Button):
    def __init__(self, bet_id: int):
        super().__init__(label="🏁 Resolve Bet", style=nextcord.ButtonStyle.primary)
        self.bet_id = bet_id

    async def callback(self, interaction: nextcord.Interaction):
        options = await db_fetchall(
            "SELECT id, label FROM bet_options WHERE prop_id = ?", (self.bet_id,)
        )
        if not options:
            await interaction.response.send_message("No options found for this bet.", ephemeral=True)
            return

        view = ResolveBetView(self.bet_id, options)
        await interaction.response.send_message("Select the winning option:", view=view, ephemeral=True)

class CancelBetButton(Button):
    def __init__(self, bet_id: int):
        super().__init__(label="❌ Cancel Bet", style=nextcord.ButtonStyle.danger)
        self.bet_id = bet_id

    async def callback(self, interaction: nextcord.Interaction):
        await db_execute("DELETE FROM bet WHERE id = ?", (self.bet_id,))
        await db_execute("DELETE FROM bet_options WHERE prop_id = ?", (self.bet_id,))
        await interaction.response.send_message("❌ Bet cancelled and removed.", ephemeral=True)

class ResolveBetView(View):
    def __init__(self, bet_id, options):
        super().__init__(timeout=60)
        self.add_item(WinnerSelect(bet_id, options))

class WinnerSelect(Select):
    def __init__(self, bet_id, options):
        self.bet_id = bet_id
        select_options = [nextcord.SelectOption(label=opt[1], value=str(opt[0])) for opt in options]
        super().__init__(placeholder="Select the winning option", min_values=1, max_values=1, options=select_options)

    async def callback(self, interaction: nextcord.Interaction):
        winning_option_id = int(self.values[0])

        # Update database: mark winner
        await db_execute(
            "UPDATE bet_options SET is_winner = 1 WHERE id = ?", (winning_option_id,)
        )
        await db_execute(
            "UPDATE bet SET is_resolved = 1 WHERE id = ?", (self.bet_id,)
        )

        # Update wagers: mark win/loss
        winning_wagers = await db_fetchall(
            "SELECT id, amount FROM wagers WHERE prop_id = ? AND prop_option_id = ?", (self.bet_id, winning_option_id)
        )
        losing_wagers = await db_fetchall(
            "SELECT id, amount FROM wagers WHERE prop_id = ? AND prop_option_id != ?", (self.bet_id, winning_option_id)
        )

        # Pay out winnings (simple 2x payout for now)
        for wager_id, amount in winning_wagers:
            payout = amount * 2
            await db_execute("UPDATE wagers SET result = 'win', payout = ? WHERE id = ?", (payout, wager_id))

        for wager_id, _ in losing_wagers:
            await db_execute("UPDATE wagers SET result = 'lose', payout = 0 WHERE id = ?", (wager_id,))

        await interaction.response.send_message(f"🏆 Winning option selected and payouts updated!", ephemeral=True)

# Database helper functions

async def db_execute(query, params=()):
    async with aiosqlite.connect(DB_FILE) as db:
        await db.execute(query, params)
        await db.commit()

async def db_fetchone(query, params=()):
    async with aiosqlite.connect(DB_FILE) as db:
        async with db.execute(query, params) as cursor:
            return await cursor.fetchone()

async def db_fetchall(query, params=()):
    async with aiosqlite.connect(DB_FILE) as db:
        async with db.execute(query, params) as cursor:
            return await cursor.fetchall()

async def get_active_session_id():
    row = await db_fetchone("SELECT id FROM sessions WHERE is_active = 1 ORDER BY created_at DESC LIMIT 1")
    if row:
        return row[0]
    return None


# Slash commands

@bot.slash_command(name="balance", description="View your wallet and current session bankroll")
async def balance(interaction: nextcord.Interaction):
    user_id = interaction.user.id

    # Wallet (persistent balance)
    wallet_row = await db_fetchone(
        "SELECT balance FROM wallet WHERE user_id = (SELECT id FROM users WHERE discord_id = ?)",
        (str(user_id),)
    )
    wallet_balance = wallet_row[0] if wallet_row else 1000

    # Find active session
    session_row = await db_fetchone(
        "SELECT id FROM sessions WHERE is_active = 1 ORDER BY id DESC LIMIT 1"
    )
    if session_row:
        session_id = session_row[0]
        # Bankroll (session-specific balance)
        bankroll_row = await db_fetchone(
            "SELECT balance FROM bankroll WHERE user_id = (SELECT id FROM users WHERE discord_id = ?) AND session_id = ?",
            (str(user_id), session_id)
        )
        bankroll_balance = bankroll_row[0] if bankroll_row else 1000
    else:
        bankroll_balance = "No active session"

    embed = nextcord.Embed(
        title=f"💰 Balance for {interaction.user.display_name}",
        color=nextcord.Color.green()
    )
    embed.add_field(name="Wallet (Persistent)", value=wallet_balance, inline=True)
    embed.add_field(name="Session Bankroll", value=bankroll_balance, inline=True)

    await interaction.response.send_message(embed=embed, ephemeral=True)


@bot.slash_command(name="createbet", description="Start creating a new bet")
@commands.has_permissions(manage_guild=True)
async def createbet(interaction: nextcord.Interaction):
    await interaction.response.send_modal(CreateBetModal())

@bot.slash_command(name="startsession", description="Start a new betting session")
@commands.has_permissions(manage_guild=True)
async def startsession(interaction: nextcord.Interaction):
    # First, close any open sessions
    await db_execute("UPDATE sessions SET is_active = 0 WHERE is_active = 1")

    # Create new session
    now = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S")
    await db_execute(
        "INSERT INTO sessions (name, description, is_active, created_at) VALUES (?, ?, 1, ?)",
        ("Session Started", "A new betting session has begun!", now)
    )

    session_row = await db_fetchone(
        "SELECT id FROM sessions WHERE is_active = 1 ORDER BY id DESC LIMIT 1"
    )
    session_id = session_row[0]

    await interaction.response.send_message(f"🟢 Session {session_id} started successfully.", ephemeral=False)

@bot.slash_command(name="endsession", description="End the current betting session")
@commands.has_permissions(manage_guild=True)
async def endsession(interaction: nextcord.Interaction):
    session_row = await db_fetchone(
        "SELECT id FROM sessions WHERE is_active = 1 ORDER BY id DESC LIMIT 1"
    )
    if not session_row:
        await interaction.response.send_message("⚠️ No active session to end.", ephemeral=True)
        return

    session_id = session_row[0]

    # End the session
    await db_execute("UPDATE sessions SET is_active = 0 WHERE id = ?", (session_id,))
    print(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] [🔴] Ended session ID {session_id}.")

    # Get all users with bankrolls
    users = await db_fetchall(
        "SELECT user_id, balance FROM bankroll WHERE session_id = ? ORDER BY balance DESC",
        (session_id,)
    )

    if not users:
        await interaction.response.send_message("⚠️ No participants found for rewards.", ephemeral=True)
        return

    # Reward multipliers
    multipliers = [2.0, 1.8, 1.6, 1.4]  # Top 1-4
    default_multiplier = 1.2

    result_lines = []
    for idx, (user_id, balance) in enumerate(users):
        if balance <= 0:
            continue  # No bonus if no bankroll

        multiplier = multipliers[idx] if idx < len(multipliers) else default_multiplier
        bonus = int(balance * multiplier)

        # Update wallet
        wallet_row = await db_fetchone("SELECT balance FROM wallet WHERE user_id = ?", (user_id,))
        if wallet_row:
            await db_execute("UPDATE wallet SET balance = balance + ? WHERE user_id = ?", (bonus, user_id))
        else:
            await db_execute("INSERT INTO wallet (user_id, balance) VALUES (?, ?)", (user_id, bonus))

        # Add to the results
        user_obj = interaction.guild.get_member(user_id)
        username = user_obj.display_name if user_obj else f"User {user_id}"
        result_lines.append(f"**{idx+1}. {username}** ➔ {balance} bankroll ➔ 🪙 {bonus} added to wallet (x{multiplier})")

    # Build embed
    embed = nextcord.Embed(
        title="🔴 Session Ended - Rewards",
        description="\n".join(result_lines),
        color=nextcord.Color.red()
    )
    embed.set_footer(text=f"Session ID {session_id}")

    await interaction.response.send_message(embed=embed, ephemeral=False)


@bot.slash_command(name="wager", description="Place a wager on an active bet")
async def wager(
    interaction: nextcord.Interaction,
    bet_id: int,
    option_id: int,
    amount: int,
    use_wallet: bool = False
):
    user_id = interaction.user.id

    # Find active session
    session_row = await db_fetchone(
        "SELECT id FROM sessions WHERE is_active = 1 ORDER BY id DESC LIMIT 1"
    )
    if not session_row:
        await interaction.response.send_message("⚠️ No active session.", ephemeral=True)
        return
    session_id = session_row[0]

    # Get user internal ID
    user_row = await db_fetchone("SELECT id FROM users WHERE discord_id = ?", (str(user_id),))
    if not user_row:
        await interaction.response.send_message("⚠️ You are not registered. Please start by checking your /balance.", ephemeral=True)
        return
    user_db_id = user_row[0]

    # Check bet exists and is unresolved
    bet_row = await db_fetchone("SELECT is_resolved FROM bet WHERE id = ?", (bet_id,))
    if not bet_row:
        await interaction.response.send_message("⚠️ Bet not found.", ephemeral=True)
        return
    if bet_row[0]:  # is_resolved == True
        await interaction.response.send_message("⚠️ This bet is already resolved.", ephemeral=True)
        return

    # Check option exists
    option_row = await db_fetchone(
        "SELECT id FROM bet_options WHERE id = ? AND prop_id = ?",
        (option_id, bet_id)
    )
    if not option_row:
        await interaction.response.send_message("⚠️ That option does not exist for this bet.", ephemeral=True)
        return

    # Choose which balance to use
    if use_wallet:
        balance_row = await db_fetchone(
            "SELECT balance FROM wallet WHERE user_id = ?", (user_db_id,)
        )
        balance = balance_row[0] if balance_row else 1000  # default wallet
        balance_source = "wallet"
    else:
        balance_row = await db_fetchone(
            "SELECT balance FROM bankroll WHERE user_id = ? AND session_id = ?",
            (user_db_id, session_id)
        )
        balance = balance_row[0] if balance_row else 1000  # default session bankroll
        balance_source = "bankroll"

    if amount > balance:
        await interaction.response.send_message(f"⚠️ Insufficient {balance_source} balance. You have {balance}.", ephemeral=True)
        return

    # Deduct the amount
    if use_wallet:
        await db_execute(
            "UPDATE wallet SET balance = balance - ? WHERE user_id = ?",
            (amount, user_db_id)
        )
    else:
        await db_execute(
            "UPDATE bankroll SET balance = balance - ? WHERE user_id = ? AND session_id = ?",
            (amount, user_db_id, session_id)
        )

    # Insert wager, recording if it came from wallet
    await db_execute(
        "INSERT INTO wagers (user_id, session_id, prop_id, prop_option_id, amount, odds, result, payout, from_wallet) VALUES (?, ?, ?, ?, ?, 100, 'pending', 0, ?)",
        (user_db_id, session_id, bet_id, option_id, amount, int(use_wallet))
    )

    await interaction.response.send_message(
        f"🎯 Successfully wagered {amount} credits from your **{balance_source}**.",
        ephemeral=True
    )



@bot.event
async def on_ready():
    now = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S")
    print(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] [🫼] Bot is online and ready.")

    cmds = bot.get_application_commands()  # NO await
    print(f"Registered {len(cmds)} slash commands.")





# Run the bot
bot.run(os.getenv("DISCORD_BOT_TOKEN"))
