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
        self.amount = TextInput(
            label="Enter your wager amount", 
            placeholder="Amount to wager", 
            required=True
        )
        self.add_item(self.amount)

    async def callback(self, interaction: nextcord.Interaction):
        try:
            amount = int(self.amount.value)
            if amount <= 0:
                raise ValueError
        except ValueError:
            await interaction.response.send_message("Invalid amount. Please enter a positive number.", ephemeral=True)
            return

        # 🔥 Always resolve internal user ID safely
        user_id = await ensure_user_exists(interaction.user)
        print(f"[WAGER DEBUG] User: {interaction.user.display_name} (ID: {interaction.user.id}), Internal User ID: {user_id}")

        # 🔥 Find active session
        session_row = await db_fetchone(
            "SELECT id FROM sessions WHERE is_active = 1 ORDER BY id DESC LIMIT 1"
        )
        if not session_row:
            print("[WAGER DEBUG] No active session found")
            await interaction.response.send_message("⚠️ No active session.", ephemeral=True)
            return
        session_id = session_row[0]
        print(f"[WAGER DEBUG] Active Session ID: {session_id}")

        # 🔥 Check bet exists and is not resolved
        bet_row = await db_fetchone(
            "SELECT is_resolved FROM bet WHERE id = ?", (self.bet_id,)
        )
        if not bet_row:
            print(f"[WAGER DEBUG] Bet {self.bet_id} not found")
            await interaction.response.send_message("⚠️ Bet not found.", ephemeral=True)
            return
        if bet_row[0]:  # Already resolved
            print(f"[WAGER DEBUG] Bet {self.bet_id} already resolved")
            await interaction.response.send_message("⚠️ This bet is already resolved.", ephemeral=True)
            return

        # 🔥 Find the option ID for this bet
        option_row = await db_fetchone(
            "SELECT id FROM bet_options WHERE prop_id = ? AND label = ?",
            (self.bet_id, self.option_label)
        )
        if not option_row:
            print(f"[WAGER DEBUG] Option {self.option_label} not found for bet {self.bet_id}")
            await interaction.response.send_message("⚠️ That option does not exist for this bet.", ephemeral=True)
            return
        option_id = option_row[0]
        print(f"[WAGER DEBUG] Option ID: {option_id}")

        # 🔥 Check balance
        try:
            if self.use_wallet:
                # Ensure wallet entry exists
                wallet_row = await db_fetchone(
                    "SELECT balance FROM wallet WHERE user_id = ?", 
                    (user_id,)
                )
                if not wallet_row:
                    print(f"[WAGER DEBUG] Creating wallet for {interaction.user.display_name}")
                    await db_execute(
                        "INSERT INTO wallet (user_id, balance) VALUES (?, ?)", 
                        (user_id, 1000)
                    )
                    balance = 1000
                else:
                    balance = wallet_row[0]
                balance_source = "wallet"
                print(f"[WAGER DEBUG] Wallet Balance for {interaction.user.display_name}: {balance}")
            else:
                # Ensure bankroll entry exists for this session
                bankroll_row = await db_fetchone(
                    "SELECT balance FROM bankroll WHERE user_id = ? AND session_id = ?", 
                    (user_id, session_id)
                )
                if not bankroll_row:
                    # Create a new bankroll entry with default 1000 if it doesn't exist
                    print(f"[WAGER DEBUG] Creating bankroll for {interaction.user.display_name} in session {session_id}")
                    await db_execute(
                        "INSERT INTO bankroll (user_id, session_id, balance) VALUES (?, ?, ?)", 
                        (user_id, session_id, 1000)
                    )
                    balance = 1000
                else:
                    balance = bankroll_row[0]
                balance_source = "bankroll"
                print(f"[WAGER DEBUG] Bankroll Balance for {interaction.user.display_name} in session {session_id}: {balance}")

            if amount > balance:
                print(f"[WAGER DEBUG] Insufficient {balance_source} balance for {interaction.user.display_name}. Have {balance}, tried to wager {amount}")
                await interaction.response.send_message(
                    f"⚠️ Insufficient {balance_source} balance. You have {balance}.", 
                    ephemeral=True
                )
                return

            # 🔥 Deduct amount
            if self.use_wallet:
                await db_execute(
                    "UPDATE wallet SET balance = balance - ? WHERE user_id = ?",
                    (amount, user_id)
                )
                print(f"[WAGER DEBUG] Deducted {amount} from wallet for {interaction.user.display_name}")
            else:
                await db_execute(
                    "UPDATE bankroll SET balance = balance - ? WHERE user_id = ? AND session_id = ?",
                    (amount, user_id, session_id)
                )
                print(f"[WAGER DEBUG] Deducted {amount} from bankroll for {interaction.user.display_name} in session {session_id}")

            # 🔥 Insert the wager
            await db_execute(
                """
                INSERT INTO wagers 
                (user_id, session_id, prop_id, prop_option_id, amount, odds, result, payout, from_wallet)
                VALUES (?, ?, ?, ?, ?, 100, 'pending', 0, ?)
                """,
                (user_id, session_id, self.bet_id, option_id, amount, int(self.use_wallet))
            )
            print(f"[WAGER DEBUG] Wager inserted for {interaction.user.display_name}")

            await interaction.response.send_message(
                f"🎯 Successfully wagered {amount} credits from your **{balance_source}** on '{self.option_label}'.",
                ephemeral=True
            )

        except Exception as e:
            print(f"[WAGER DEBUG] Error during wager for {interaction.user.display_name}: {e}")
            await interaction.response.send_message("An unexpected error occurred while placing your wager.", ephemeral=True)


class WagerButton(Button):
    def __init__(self, label: str, option_label: str, bet_id: int, use_wallet: bool = False):
        super().__init__(label=label, style=nextcord.ButtonStyle.primary)
        self.option_label = option_label
        self.bet_id = bet_id
        self.use_wallet = use_wallet

    async def callback(self, interaction: nextcord.Interaction):
        # 🔥 Debugging prints
        print(f"[WAGER BUTTON DEBUG] {interaction.user.display_name} pressed button - Option: {self.option_label}, Bet ID: {self.bet_id}")
        
        # Open the modal for wagering
        modal = WagerModal(self.option_label, self.bet_id, self.use_wallet)
        await interaction.response.send_modal(modal)

class WalletTransferModal(Modal):
    def __init__(self, session_id):
        super().__init__(title="Transfer Wallet Balance to Session")
        self.session_id = session_id
        
        self.transfer_amount = TextInput(
            label="Transfer Amount",
            placeholder="How many credits to transfer from wallet?",
            required=True
        )
        self.add_item(self.transfer_amount)

    async def callback(self, interaction: nextcord.Interaction):
        try:
            # Validate transfer amount
            transfer_amount = int(self.transfer_amount.value)
            
            # Get user's wallet balance
            user_id = await ensure_user_exists(interaction.user)
            wallet_row = await db_fetchone(
                "SELECT balance FROM wallet WHERE user_id = ?", 
                (user_id,)
            )
            
            if not wallet_row or wallet_row[0] < transfer_amount:
                await interaction.response.send_message(
                    "⚠️ Insufficient wallet balance.", 
                    ephemeral=True
                )
                return
            
            # Deduct from wallet
            await db_execute(
                "UPDATE wallet SET balance = balance - ? WHERE user_id = ?",
                (transfer_amount, user_id)
            )
            
            # Add to session bankroll with wallet flag
            await db_execute(
                "INSERT INTO bankroll (user_id, session_id, balance, from_wallet) VALUES (?, ?, ?, 1) "
                "ON CONFLICT(user_id, session_id) DO UPDATE SET balance = balance + ?, from_wallet = 1",
                (user_id, self.session_id, transfer_amount, transfer_amount)
            )
            
            await interaction.response.send_message(
                f"💰 Transferred {transfer_amount} credits from wallet to session. Wallet transfers will have special multipliers!", 
                ephemeral=True
            )
        
        except ValueError:
            await interaction.response.send_message(
                "⚠️ Please enter a valid number.", 
                ephemeral=True
            )
        except Exception as e:
            print(f"Wallet transfer error: {e}")
            await interaction.response.send_message(
                "An unexpected error occurred.", 
                ephemeral=True
            )

class WalletTransferButton(Button):
    def __init__(self, session_id):
        super().__init__(
            label="Transfer Wallet Balance", 
            style=nextcord.ButtonStyle.primary
        )
        self.session_id = session_id

    async def callback(self, interaction: nextcord.Interaction):
        modal = WalletTransferModal(self.session_id)
        await interaction.response.send_modal(modal)

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

        # Create buttons view - include both bankroll and wallet options
        view = View(timeout=None)

        # Add bankroll wager buttons
        for idx, label in enumerate(options):
            emoji = EMOJI_MAP[idx]
            view.add_item(WagerButton(label=f"{emoji} {label}", option_label=label, bet_id=bet_id, use_wallet=False))

        # Add a separator (blank) button if needed
        view.add_item(Button(label="───── Wallet Betting ─────", style=nextcord.ButtonStyle.secondary, disabled=True))

        # Add wallet wager buttons
        for idx, label in enumerate(options):
            emoji = EMOJI_MAP[idx]
            view.add_item(WagerButton(label=f"💰 {emoji} {label}", option_label=label, bet_id=bet_id, use_wallet=True))

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

        # Fetch bet details
        bet_details = await db_fetchone(
            "SELECT name FROM bet WHERE id = ?", 
            (self.bet_id,)
        )
        bet_name = bet_details[0] if bet_details else "Unnamed Bet"

        # Fetch winning option label
        winning_option = await db_fetchone(
            "SELECT label FROM bet_options WHERE id = ?", 
            (winning_option_id,)
        )
        winning_label = winning_option[0] if winning_option else "Unknown Option"

        # Update database: mark winner
        await db_execute(
            "UPDATE bet_options SET is_winner = 1 WHERE id = ?", (winning_option_id,)
        )
        await db_execute(
            "UPDATE bet SET is_resolved = 1 WHERE id = ?", (self.bet_id,)
        )

        # Update wagers: mark win/loss
        winning_wagers = await db_fetchall(
            "SELECT id, user_id, amount FROM wagers WHERE prop_id = ? AND prop_option_id = ?", (self.bet_id, winning_option_id)
        )
        losing_wagers = await db_fetchall(
            "SELECT id, user_id, amount FROM wagers WHERE prop_id = ? AND prop_option_id != ?", (self.bet_id, winning_option_id)
        )

        # Prepare tracking for payout summary
        session_id = await get_active_session_id()
        payout_details = []

        # Pay out winnings 
        for wager_id, user_id, amount in winning_wagers:
            # Calculate payout (simple 2x for now)
            payout = amount * 2
            await db_execute("UPDATE wagers SET result = 'win', payout = ? WHERE id = ?", (payout, wager_id))
            
            # Update the user's balance
            await db_execute(
                "UPDATE bankroll SET balance = balance + ? WHERE user_id = ? AND session_id = ?",
                (payout, user_id, session_id)
            )

            # Track for summary
            user_details = await db_fetchone("SELECT username FROM users WHERE id = ?", (user_id,))
            username = user_details[0] if user_details else f"User {user_id}"
            payout_details.append(f"🎉 **{username}** won {payout} credits")

        for wager_id, user_id, amount in losing_wagers:
            await db_execute("UPDATE wagers SET result = 'lose', payout = 0 WHERE id = ?", (wager_id,))
            
            # Track for summary
            user_details = await db_fetchone("SELECT username FROM users WHERE id = ?", (user_id,))
            username = user_details[0] if user_details else f"User {user_id}"
            payout_details.append(f"😔 **{username}** lost {amount} credits")

        # Create an embed to show bet resolution
        embed = nextcord.Embed(
            title="🏆 Bet Resolved",
            description=f"**Bet:** {bet_name}\n**Winning Option:** {winning_label}",
            color=nextcord.Color.green()
        )

        # Add payout details
        if payout_details:
            payout_summary = "\n".join(payout_details[:10])  # Limit to 10 entries
            if len(payout_details) > 10:
                payout_summary += f"\n... and {len(payout_details) - 10} more"
            embed.add_field(name="Payout Details", value=payout_summary, inline=False)

        # Send the summary
        await interaction.channel.send(embed=embed)

        # Confirm to the admin
        await interaction.response.send_message(f"🏆 Bet '{bet_name}' resolved. Winning option: {winning_label}", ephemeral=True)

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
        print(f"[DEBUG] Active Session ID found: {row[0]}")
        return row[0]
    print("[DEBUG] No active session found!")
    return None

async def resolve_bet_and_payout(interaction: nextcord.Interaction, bet_id: int, winning_option_id: int):
    session_id = await get_active_session_id()

    # Mark the bet as resolved
    await db_execute("UPDATE bet SET is_resolved = 1 WHERE id = ?", (bet_id,))

    # Mark the winning option
    await db_execute("UPDATE bet_options SET is_winner = 1 WHERE id = ?", (winning_option_id,))

    # Find all wagers for this bet
    wagers = await db_fetchall(
        "SELECT user_id, amount, prop_option_id FROM wagers WHERE prop_id = ?",
        (bet_id,)
    )

    # Fetch bet details for context
    bet_details = await db_fetchone(
        "SELECT name FROM bet WHERE id = ?",
        (bet_id,)
    )
    bet_name = bet_details[0] if bet_details else "Unnamed Bet"

    # Fetch winning option label
    winning_option = await db_fetchone(
        "SELECT label FROM bet_options WHERE id = ?",
        (winning_option_id,)
    )
    winning_label = winning_option[0] if winning_option else "Unknown Option"

    result_lines = []
    # Track guild to get member objects for sending messages
    guild = interaction.guild

    for user_id, amount, prop_option_id in wagers:
        won = prop_option_id == winning_option_id
        
        if won:
            # Calculate payout (simple 2x for now)
            odds_row = await db_fetchone(
                "SELECT odds FROM bet_options WHERE id = ?",
                (prop_option_id,)
            )
            odds = odds_row[0] if odds_row else 100

            payout = int(amount * (odds / 100))

            # Update bankroll
            await db_execute(
                "UPDATE bankroll SET balance = balance + ? WHERE user_id = ? AND session_id = ?",
                (payout, user_id, session_id)
            )

            # Update wager result
            await db_execute(
                "UPDATE wagers SET result = 'win', payout = ? WHERE user_id = ? AND prop_id = ?",
                (payout, user_id, bet_id)
            )

            # Try to get the user to send a personal message
            try:
                member = guild.get_member(int(user_id))
                if member:
                    # Send an ephemeral-style personal message about the win
                    await member.send(
                        f"🎉 **Congratulations!**\n"
                        f"You won the bet: **{bet_name}**\n"
                        f"Winning Option: {winning_label}\n"
                        f"Bet Amount: {amount}\n"
                        f"Payout: {payout} credits\n"
                        f"Net Gain: +{payout - amount} credits"
                    )
                result_lines.append(f"🎉 **{member.display_name}** won {payout} credits!")
            except:
                # Fallback if DM fails
                result_lines.append(f"🎉 User {user_id} won {payout} credits!")

        else:
            # Update losing wager
            await db_execute(
                "UPDATE wagers SET result = 'lose' WHERE user_id = ? AND prop_id = ?",
                (user_id, bet_id)
            )

            # Try to send loss message
            try:
                member = guild.get_member(int(user_id))
                if member:
                    # Send an ephemeral-style personal message about the loss
                    await member.send(
                        f"😔 **Better luck next time!**\n"
                        f"You lost the bet: **{bet_name}**\n"
                        f"Winning Option: {winning_label}\n"
                        f"Bet Amount: {amount}\n"
                        f"Net Loss: -{amount} credits"
                    )
            except:
                pass  # Silently fail if DM can't be sent

    # Final embed with overall results
    embed = nextcord.Embed(
        title="🏁 Bet Resolved!",
        description="\n".join(result_lines) if result_lines else "No participants this time!",
        color=nextcord.Color.green()
    )
    embed.add_field(name="Bet", value=bet_name, inline=False)
    embed.add_field(name="Winning Option", value=winning_label, inline=False)
    await interaction.channel.send(embed=embed)

# Ensures a user exists in the database. 
# If not, inserts them using their Discord ID and username.
async def ensure_user_exists(discord_user: nextcord.User):
    user_row = await db_fetchone(
        "SELECT id FROM users WHERE discord_id = ?", (str(discord_user.id),)
    )
    if user_row:
        await db_execute(
            "UPDATE users SET username = ? WHERE discord_id = ?",
            (discord_user.display_name, str(discord_user.id))
        )
        return user_row[0]

    await db_execute(
        "INSERT INTO users (discord_id, username) VALUES (?, ?)",
        (str(discord_user.id), discord_user.display_name)
    )
    new_user_row = await db_fetchone(
        "SELECT id FROM users WHERE discord_id = ?", (str(discord_user.id),)
    )
    return new_user_row[0]




# Slash commands

@bot.slash_command(name="force_sync", description="Force sync application commands")
async def force_sync(interaction: nextcord.Interaction):
    await bot.sync_application_commands()
    await interaction.response.send_message("🔄 Commands synced.", ephemeral=True)


@bot.slash_command(name="balance", description="Check your Wallet and Bankroll balances")
async def balance(interaction: nextcord.Interaction):
    # 🔥 Get internal database user_id (not discord ID!)
    user_id = await ensure_user_exists(interaction.user)

    session_id = await get_active_session_id()

    # 🔵 Persistent (wallet) balance
    persistent_balance_row = await db_fetchone(
        "SELECT balance FROM wallet WHERE user_id = ?", 
        (user_id,)
    )
    persistent_balance = persistent_balance_row[0] if persistent_balance_row else 1000

    # 🔵 Session (bankroll) balance
    session_balance_row = await db_fetchone(
        "SELECT balance FROM bankroll WHERE user_id = ? AND session_id = ?", 
        (user_id, session_id)
    )
    session_balance = session_balance_row[0] if session_balance_row else 1000

    # 🔵 Amount currently wagered from wallet
    persistent_wagered_row = await db_fetchone(
        "SELECT SUM(amount) FROM wagers WHERE user_id = ? AND session_id IS NULL AND result = 'pending'", 
        (user_id,)
    )
    persistent_wagered = persistent_wagered_row[0] if persistent_wagered_row and persistent_wagered_row[0] else 0

    # 🔵 Amount currently wagered from  bankroll
    session_wagered_row = await db_fetchone(
        "SELECT SUM(amount) FROM wagers WHERE user_id = ? AND session_id = ? AND result = 'pending'", 
        (user_id, session_id)
    )
    session_wagered = session_wagered_row[0] if session_wagered_row and session_wagered_row[0] else 0

    # 🎨 Create the embed
    embed = nextcord.Embed(
        title=f"💰 {interaction.user.display_name} Balances",
        color=nextcord.Color.green()
    )
    embed.add_field(
        name="Wallet Balance",
        value=f"Available: {persistent_balance}\nWagered: {persistent_wagered}",
        inline=False
    )
    embed.add_field(
        name="Bankroll Balance",
        value=f"Available: {session_balance}\nWagered: {session_wagered}",
        inline=False
    )

    await interaction.response.send_message(embed=embed, ephemeral=True)

@bot.slash_command(name="mywagers", description="View your current active wagers")
async def mywagers(interaction: nextcord.Interaction):
    # 🔥 Get internal database user ID safely
    user_id = await ensure_user_exists(interaction.user)

    # 🔥 Fetch active wagers
    wagers = await db_fetchall(
        "SELECT prop_id, prop_option_id, amount FROM wagers WHERE user_id = ? AND result = 'pending'",
        (user_id,)
    )

    if not wagers:
        await interaction.response.send_message("You have no active wagers.", ephemeral=True)
        return

    description = ""

    # 🔥 For each wager, fetch bet and option labels
    for bet_id, option_id, amount in wagers:
        bet_row = await db_fetchone(
            "SELECT name FROM bet WHERE id = ?",
            (bet_id,)
        )
        option_row = await db_fetchone(
            "SELECT label FROM bet_options WHERE id = ?",
            (option_id,)
        )

        bet_name = bet_row[0] if bet_row else "Unknown Bet"
        option_label = option_row[0] if option_row else "Unknown Option"

        description += (
            f"🎯 **{bet_name}**\n"
            f"➔ Option: **{option_label}**\n"
            f"➔ Amount Wagered: `{amount}` credits\n\n"
        )

    embed = nextcord.Embed(
        title=f"🎲 {interaction.user.display_name}'s Active Wagers",
        description=description,
        color=nextcord.Color.blurple()
    )

    await interaction.response.send_message(embed=embed, ephemeral=True)


@bot.slash_command(name="createbet", description="Start creating a new bet")
@commands.has_permissions(manage_guild=True)
async def createbet(interaction: nextcord.Interaction):
    await interaction.response.send_modal(CreateBetModal())

@bot.slash_command(name="startsession", description="Start a new betting session")
@commands.has_permissions(manage_guild=True)
async def startsession(interaction: nextcord.Interaction):
    # Check if an active session already exists
    existing_session = await db_fetchone(
        "SELECT id FROM sessions WHERE is_active = 1 ORDER BY id DESC LIMIT 1"
    )
    print(f"[DEBUG] Existing active session: {existing_session}")

    if existing_session:
        await interaction.response.send_message(
            f"⚠️ An active session (ID {existing_session[0]}) already exists. You must end it first with `/endsession`.",
            ephemeral=True
        )
        return

    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    await db_execute(
        "INSERT INTO sessions (name, description, created_at, is_active) VALUES (?, ?, ?, ?)",
        (f"Session {now}", "New session started.", now, 1)
    )
    
    # Fetch the newly created session ID
    session_row = await db_fetchone(
        "SELECT id FROM sessions WHERE name = ? ORDER BY id DESC LIMIT 1",
        (f"Session {now}",)
    )
    session_id = session_row[0]

    print(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] [🟢] Started a new session.")

    # Create a view with a wallet transfer button
    view = View(timeout=None)
    view.add_item(WalletTransferButton(session_id))

    await interaction.response.send_message(
        "🟢 A new betting session has been started! Would you like to transfer credits from your wallet?", 
        view=view, 
        ephemeral=False
    )


class WinnerSelect(Select):
    def __init__(self, bet_id, options):
        self.bet_id = bet_id
        select_options = [nextcord.SelectOption(label=opt[1], value=str(opt[0])) for opt in options]
        super().__init__(placeholder="Select the winning option", min_values=1, max_values=1, options=select_options)

    async def callback(self, interaction: nextcord.Interaction):
        winning_option_id = int(self.values[0])

        # Fetch bet details
        bet_details = await db_fetchone(
            "SELECT name FROM bet WHERE id = ?", 
            (self.bet_id,)
        )
        bet_name = bet_details[0] if bet_details else "Unnamed Bet"

        # Fetch winning option label
        winning_option = await db_fetchone(
            "SELECT label FROM bet_options WHERE id = ?", 
            (winning_option_id,)
        )
        winning_label = winning_option[0] if winning_option else "Unknown Option"

        # Update database: mark winner
        await db_execute(
            "UPDATE bet_options SET is_winner = 1 WHERE id = ?", (winning_option_id,)
        )
        await db_execute(
            "UPDATE bet SET is_resolved = 1 WHERE id = ?", (self.bet_id,)
        )

        # Update wagers: mark win/loss
        winning_wagers = await db_fetchall(
            "SELECT id, user_id, amount FROM wagers WHERE prop_id = ? AND prop_option_id = ?", (self.bet_id, winning_option_id)
        )
        losing_wagers = await db_fetchall(
            "SELECT id, user_id, amount FROM wagers WHERE prop_id = ? AND prop_option_id != ?", (self.bet_id, winning_option_id)
        )

        # Prepare tracking for payout summary
        session_id = await get_active_session_id()
        payout_details = []

        # Pay out winnings 
        for wager_id, user_id, amount in winning_wagers:
            # Calculate payout (simple 2x for now)
            payout = amount * 2
            await db_execute("UPDATE wagers SET result = 'win', payout = ? WHERE id = ?", (payout, wager_id))
            
            # Update the user's balance
            await db_execute(
                "UPDATE bankroll SET balance = balance + ? WHERE user_id = ? AND session_id = ?",
                (payout, user_id, session_id)
            )

            # Track for summary
            user_details = await db_fetchone("SELECT username FROM users WHERE id = ?", (user_id,))
            username = user_details[0] if user_details else f"User {user_id}"
            payout_details.append(f"🎉 **{username}** won {payout} credits")

        for wager_id, user_id, amount in losing_wagers:
            await db_execute("UPDATE wagers SET result = 'lose', payout = 0 WHERE id = ?", (wager_id,))
            
            # Track for summary
            user_details = await db_fetchone("SELECT username FROM users WHERE id = ?", (user_id,))
            username = user_details[0] if user_details else f"User {user_id}"
            payout_details.append(f"😔 **{username}** lost {amount} credits")

        # Create an embed to show bet resolution
        embed = nextcord.Embed(
            title="🏆 Bet Resolved",
            description=f"**Bet:** {bet_name}\n**Winning Option:** {winning_label}",
            color=nextcord.Color.green()
        )

        # Add payout details
        if payout_details:
            payout_summary = "\n".join(payout_details[:10])  # Limit to 10 entries
            if len(payout_details) > 10:
                payout_summary += f"\n... and {len(payout_details) - 10} more"
            embed.add_field(name="Payout Details", value=payout_summary, inline=False)

        # Send the summary
        await interaction.channel.send(embed=embed)

        # Confirm to the admin
        await interaction.response.send_message(f"🏆 Bet '{bet_name}' resolved. Winning option: {winning_label}", ephemeral=True)

@bot.slash_command(name="wager", description="Place a wager on an active bet")
async def wager(
    interaction: nextcord.Interaction,
    bet_id: int,
    option_id: int,
    amount: int,
    use_wallet: bool = False
):
    # 🔥 Debugging: Print input parameters
    print(f"[WAGER DEBUG] User: {interaction.user.id}, Bet ID: {bet_id}, Option ID: {option_id}, Amount: {amount}, Use Wallet: {use_wallet}")

    # 🔥 Always resolve internal user ID safely
    user_id = await ensure_user_exists(interaction.user)
    print(f"[WAGER DEBUG] Internal User ID: {user_id}")

    # 🔥 Find active session
    session_row = await db_fetchone(
        "SELECT id FROM sessions WHERE is_active = 1 ORDER BY id DESC LIMIT 1"
    )
    if not session_row:
        print("[WAGER DEBUG] No active session found")
        await interaction.response.send_message("⚠️ No active session.", ephemeral=True)
        return
    session_id = session_row[0]
    print(f"[WAGER DEBUG] Active Session ID: {session_id}")

    # 🔥 Check bet exists and is not resolved
    bet_row = await db_fetchone(
        "SELECT is_resolved FROM bet WHERE id = ?", (bet_id,)
    )
    if not bet_row:
        print(f"[WAGER DEBUG] Bet {bet_id} not found")
        await interaction.response.send_message("⚠️ Bet not found.", ephemeral=True)
        return
    if bet_row[0]:  # Already resolved
        print(f"[WAGER DEBUG] Bet {bet_id} already resolved")
        await interaction.response.send_message("⚠️ This bet is already resolved.", ephemeral=True)
        return

    # 🔥 Check option exists
    option_row = await db_fetchone(
        "SELECT id FROM bet_options WHERE id = ? AND prop_id = ?",
        (option_id, bet_id)
    )
    if not option_row:
        print(f"[WAGER DEBUG] Option {option_id} does not exist for bet {bet_id}")
        await interaction.response.send_message("⚠️ That option does not exist for this bet.", ephemeral=True)
        return

    # 🔥 Check balance
    if use_wallet:
        # Ensure wallet entry exists
        wallet_row = await db_fetchone(
            "SELECT balance FROM wallet WHERE user_id = ?", 
            (user_id,)
        )
        if not wallet_row:
            print(f"[WAGER DEBUG] Creating wallet for user {user_id}")
            await db_execute(
                "INSERT INTO wallet (user_id, balance) VALUES (?, ?)", 
                (user_id, 1000)
            )
            balance = 1000
        else:
            balance = wallet_row[0]
        balance_source = "wallet"
        print(f"[WAGER DEBUG] Wallet Balance for user {user_id}: {balance}")
    else:
        # Ensure bankroll entry exists for this session
        bankroll_row = await db_fetchone(
            "SELECT balance FROM bankroll WHERE user_id = ? AND session_id = ?", 
            (user_id, session_id)
        )
        if not bankroll_row:
            # Create a new bankroll entry with default 1000 if it doesn't exist
            print(f"[WAGER DEBUG] Creating bankroll for user {user_id} in session {session_id}")
            await db_execute(
                "INSERT INTO bankroll (user_id, session_id, balance) VALUES (?, ?, ?)", 
                (user_id, session_id, 1000)
            )
            balance = 1000
        else:
            balance = bankroll_row[0]
        balance_source = "bankroll"
        print(f"[WAGER DEBUG] Bankroll Balance for user {user_id} in session {session_id}: {balance}")

    if amount > balance:
        print(f"[WAGER DEBUG] Insufficient {balance_source} balance. Have {balance}, tried to wager {amount}")
        await interaction.response.send_message(
            f"⚠️ Insufficient {balance_source} balance. You have {balance}.", 
            ephemeral=True
        )
        return

    # 🔥 Deduct amount
    if use_wallet:
        await db_execute(
            "UPDATE wallet SET balance = balance - ? WHERE user_id = ?",
            (amount, user_id)
        )
        print(f"[WAGER DEBUG] Deducted {amount} from wallet for user {user_id}")
    else:
        await db_execute(
            "UPDATE bankroll SET balance = balance - ? WHERE user_id = ? AND session_id = ?",
            (amount, user_id, session_id)
        )
        print(f"[WAGER DEBUG] Deducted {amount} from bankroll for user {user_id} in session {session_id}")

    # 🔥 Insert the wager
    await db_execute(
        """
        INSERT INTO wagers 
        (user_id, session_id, prop_id, prop_option_id, amount, odds, result, payout, from_wallet)
        VALUES (?, ?, ?, ?, ?, 100, 'pending', 0, ?)
        """,
        (user_id, session_id, bet_id, option_id, amount, int(use_wallet))
    )
    print(f"[WAGER DEBUG] Wager inserted for user {user_id}")

    await interaction.response.send_message(
        f"🎯 Successfully wagered {amount} credits from your **{balance_source}**.",
        ephemeral=True
    )




@bot.event
async def on_ready():
    now = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S")
    print(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] [🫼] Bot is online and ready.")

    # Initialize database structure
    async with aiosqlite.connect(DB_FILE) as db:
        # Users table
        await db.execute('''
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            discord_id TEXT,
            username TEXT,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP
        )
        ''')

        # Sessions table
        await db.execute('''
        CREATE TABLE IF NOT EXISTS sessions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT,
            description TEXT,
            created_at DATETIME,
            is_active INTEGER DEFAULT 0
        )
        ''')

        # Bankroll table - adding from_wallet column
        await db.execute('''
        CREATE TABLE IF NOT EXISTS bankroll (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            session_id INTEGER,
            balance INTEGER DEFAULT 1000,
            from_wallet INTEGER DEFAULT 0,
            UNIQUE(user_id, session_id)
        )
        ''')

        # Wallet table
        await db.execute('''
        CREATE TABLE IF NOT EXISTS wallet (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER UNIQUE,
            balance INTEGER DEFAULT 1000
        )
        ''')

        # Bet table
        await db.execute('''
        CREATE TABLE IF NOT EXISTS bet (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            session_id INTEGER,
            name TEXT,
            description TEXT,
            bet_type TEXT,
            is_resolved INTEGER DEFAULT 0
        )
        ''')

        # Bet options table
        await db.execute('''
        CREATE TABLE IF NOT EXISTS bet_options (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            prop_id INTEGER,
            label TEXT,
            odds INTEGER DEFAULT 100,
            is_winner INTEGER DEFAULT 0
        )
        ''')

        # Wagers table
        await db.execute('''
        CREATE TABLE IF NOT EXISTS wagers (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            session_id INTEGER,
            prop_id INTEGER,
            prop_option_id INTEGER,
            amount INTEGER,
            odds INTEGER,
            result TEXT,
            payout INTEGER,
            from_wallet INTEGER DEFAULT 0
        )
        ''')

        await db.commit()

    cmds = bot.get_application_commands()  # NO await
    print(f"Registered {len(cmds)} slash commands.")




# Run the bot
bot.run(os.getenv("DISCORD_BOT_TOKEN"))
