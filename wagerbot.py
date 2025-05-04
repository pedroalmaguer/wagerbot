import nextcord
from nextcord.ext import commands
from nextcord import SlashOptionChoice
from nextcord.ui import Button, View, Modal, TextInput, Select
import os
from datetime import datetime

intents = nextcord.Intents.default()
intents.message_content = True
intents.members = True
intents.reactions = True

bot = commands.Bot(intents=intents)

EMOJI_MAP = [
    "🇦", "🇧", "🇨", "🇩", "🇪", "🇫", "🇬", "🇭",
    "🇮", "🇯", "🇰", "🇱", "🇲", "🇳", "🇴", "🇵",
    "🇶", "🇷", "🇸", "🇹", "🇺", "🇻", "🇼", "🇽",
    "🇾", "🇿"
]

class WagerModal(Modal):
    def __init__(self, option_label, message_id):
        super().__init__(title=f"Your Wager On \"{option_label}\"")
        self.option_label = option_label
        self.message_id = message_id
        self.amount = TextInput(label="Wager Amount", required=True)
        self.add_item(self.amount)

    async def callback(self, interaction: nextcord.Interaction):
        
        try:
            amount = int(self.amount.value)
            if amount <= 0:
                raise ValueError
        except ValueError:
            await interaction.response.send_message("Invalid amount.", ephemeral=True)
            return

        user_id = interaction.user.id
        user_balance = balances.get(user_id, 1000)

        if amount > user_balance:
            await interaction.response.send_message("Insufficient funds.", ephemeral=True)
            return

        bet = bets.get(self.message_id)
        if bet is None or bet.get("locked"):
            await interaction.response.send_message("Bet is closed.", ephemeral=True)
            return

        bet["wagers"][user_id] = {
            "option": self.option_label,
            "amount": amount,
            "name": interaction.user.display_name
        }
        print(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] f"[💸] {interaction.user.display_name} wagered {amount} on '{self.option_label}'"")
        balances[user_id] = user_balance - amount

        # Update message with current pot, participant count, and option breakdown
        channel = interaction.channel
        message = await channel.fetch_message(self.message_id)
        total_pot = sum(w["amount"] for w in bet["wagers"].values())
        unique_users = len(bet["wagers"])

        option_totals = {}
        for wager in bet["wagers"].values():
            option = wager["option"]
            option_totals[option] = option_totals.get(option, 0) + wager["amount"]

        breakdown = " | ".join([f"{opt}: {amt}" for opt, amt in option_totals.items()])

        embed = message.embeds[0]
        embed.set_footer(text=f"Total Pot: {total_pot} | Participants: {unique_users} | {breakdown}")
        await message.edit(embed=embed)

        await interaction.response.send_message(
            f"Wagered {amount} on {self.option_label}. Remaining: {balances[user_id]}", ephemeral=True
        )

class LockBetButton(Button):
    def __init__(self, message_id):
        super().__init__(label="🔒 Lock Bet", style=nextcord.ButtonStyle.success)
        self.message_id = message_id

    async def callback(self, interaction: nextcord.Interaction):
        bet = bets.get(self.message_id)
        if bet:
            bet["locked"] = True
            print(f"[🔒] Bet '{bet['question']}' has been locked.")
            await interaction.response.send_message("✅ Bet has been locked. No more wagers allowed.", ephemeral=True)

class ResolveBetButton(Button):
    def __init__(self, message_id):
        super().__init__(label="🏁 Resolve Bet", style=nextcord.ButtonStyle.primary)
        self.message_id = message_id

    async def callback(self, interaction: nextcord.Interaction):
        bet = bets.get(self.message_id)
        if not bet or not bet.get("locked"):
            await interaction.response.send_message("Bet is not locked or doesn't exist.", ephemeral=True)
            return

        options = bet["options"]
        await interaction.response.send_message(view=ResolveBetView(self.message_id, options), ephemeral=True)


class ResolveBetView(View):
    def __init__(self, message_id, options):
        super().__init__(timeout=60)
        self.add_item(WinnerSelect(message_id, options))


class WinnerSelect(Select):
    resolved_bets = set()
    def __init__(self, message_id, options):
        self.message_id = message_id
        select_options = [nextcord.SelectOption(label=opt) for opt in options]
        super().__init__(placeholder="Select winning option", min_values=1, max_values=1, options=select_options)

    async def callback(self, interaction: nextcord.Interaction):
        winning_option = self.values[0]
        await interaction.response.send_message(f"You selected: {winning_option}", ephemeral=True)
        print(f"[🏁] Bet resolved. Winning option: {winning_option}")
        await update_user_stats(self.message_id, winning_option)

        bet = bets.get(self.message_id)
        if not bet:
            return

        total_pot = sum(w["amount"] for w in bet["wagers"].values())
        winners = [w for w in bet["wagers"].values() if w["option"] == winning_option]

        result_lines = []
        for w in winners:
            result_lines.append(f"🎉 {w['name']} won their share!")

        description = f"""**{bet['question']}**
Winning Option: **{winning_option}**
Total Pot: **{total_pot}**

{chr(10).join(result_lines)}"""

        embed = nextcord.Embed(
            title="🏁 Bet Resolved!",
            description=description,
            color=nextcord.Color.green()
        )

        channel = interaction.channel
        message = await channel.fetch_message(self.message_id)
        await message.edit(embed=embed, view=None)
        del bets[self.message_id]
save_data()

        # Send updated balance messages to all participants
        for uid in bet["wagers"]:
            member = interaction.guild.get_member(uid)
            if member:
                user_balance = balances.get(uid, 1000)
                try:
                    await interaction.followup.send(
                        content=f"💰 {member.mention}, your new balance is: **{user_balance}** credits.",
                        ephemeral=True
                    )
                except nextcord.HTTPException:
                    pass


class CancelBetButton(Button):
    def __init__(self, message_id):
        super().__init__(label="❌ Cancel Bet", style=nextcord.ButtonStyle.danger)
        self.message_id = message_id

    async def callback(self, interaction: nextcord.Interaction):
        if self.message_id in bets:
            del bets[self.message_id]
        await interaction.message.edit(content="❌ Bet cancelled.", view=None)
        await interaction.response.send_message("Bet has been cancelled.", ephemeral=True)


class WagerButton(Button):
    def __init__(self, label, option, message_id):
        super().__init__(label=label, style=nextcord.ButtonStyle.primary)
        self.option = option
        self.message_id = message_id

    async def callback(self, interaction: nextcord.Interaction):
        await interaction.response.send_modal(WagerModal(self.option, self.message_id))

@bot.slash_command(name="createbet", description="Create a new bet")
@commands.has_permissions(manage_guild=True)
async def createbet(interaction: nextcord.Interaction, question: str, option1: str, option2: str, option3: str = None, option4: str = None, option5: str = None, option6: str = None):
    if not session_active:
        await interaction.response.send_message("No active session. Start a session with /startsession before creating bets.", ephemeral=True)
        return"No active session. Start a session with !startsession before creating bets.")
        return

    if len(options) < 2:
        await ctx.send("You must provide at least 2 options.")
        return
    if len(options) > len(EMOJI_MAP):
        await ctx.send(f"You can provide at most {len(EMOJI_MAP)} options.")
        return

    description = f"> **{question}**\n"
    for i, opt in enumerate(options):
        description += f"{EMOJI_MAP[i]} {opt}\n"

    embed = nextcord.Embed(
        title="💬 New Bet!",
        description=description,
        color=nextcord.Color.blurple()
    )

    msg = await ctx.send(embed=embed)
    bets[msg.id] = {
        "question": question,
        "options": options,
        "wagers": {},
        "locked": False
    }
    print(f"[📢] New bet created: '{question}' with options {options}")

    view = View(timeout=None)
    for i, option in enumerate(options):
        emoji = EMOJI_MAP[i]
        view.add_item(WagerButton(label=f"{emoji} {option}", option=option, message_id=msg.id))

        # Add lock and cancel buttons
    view.add_item(LockBetButton(msg.id))
    view.add_item(CancelBetButton(msg.id))
    view.add_item(ResolveBetButton(msg.id))

    await msg.edit(view=view)

bets = {}
balances = {}
stats = {}
lifetime_stats = {}
last_session_stats = {}

# Persistence
import json

def save_data():
    if not os.path.exists("data.json"):
        print("[📁] Creating new data.json file for persistent storage.")
    with open("data.json", "w") as f:
        json.dump({
            "balances": balances,
            "stats": stats,
            "lifetime_stats": lifetime_stats,
            "last_session_stats": last_session_stats
        }, f)

def load_data():
    global balances, stats, lifetime_stats, last_session_stats
    try:
        with open("data.json", "r") as f:
            data = json.load(f)
            balances = {int(k): v for k, v in data.get("balances", {}).items()}
            stats = {int(k): v for k, v in data.get("stats", {}).items()}
            lifetime_stats = {int(k): v for k, v in data.get("lifetime_stats", {}).items()}
            last_session_stats = {int(k): v for k, v in data.get("last_session_stats", {}).items()}
    except (FileNotFoundError, json.JSONDecodeError):
        pass

load_data()
session_active = False
    save_data()
    print("[🛑] Session ended.")

@bot.slash_command(name="startsession", description="Start a new betting session")
@commands.has_permissions(manage_guild=True)
async def startsession(interaction: nextcord.Interaction):
    global stats, balances, session_active, last_session_stats

    if session_active:
        await ctx.send("A session is already active.")
        return

    last_session_stats = stats.copy()
    stats = {}
    balances = {}
    session_active = True
    save_data()
    print("[🎲] New session started. Balances and stats reset.")

    await ctx.send("🟢 A new betting session has started! Balances and stats reset.")

@bot.slash_command(name="endsession", description="End the current betting session")
@commands.has_permissions(manage_guild=True)
async def endsession(interaction: nextcord.Interaction):
    global session_active
    if not session_active:
        await ctx.send("No session is currently active.")
        return

    session_active = False

    await ctx.send("🔴 Session ended.")

    if not stats:
        await ctx.send("No stats to display for this session.")
        return

    biggest_winner = max(stats.items(), key=lambda x: x[1].get("total_won", 0))[0]
    biggest_loser = max(stats.items(), key=lambda x: x[1].get("total_lost", 0))[0]
    most_bets = max(stats.items(), key=lambda x: x[1].get("bets_placed", 0))[0]

    best_win_rate = None
    best_win_pct = 0
    for uid, s in stats.items():
        if s["bets_placed"] > 1:
            win_pct = (s["total_won"] / s["total_wagered"] * 100) if s["total_wagered"] else 0
            if win_pct > best_win_pct:
                best_win_pct = win_pct
                best_win_rate = uid

    def get_name(uid):
        member = ctx.guild.get_member(uid)
        return member.display_name if member else f"User {uid}"

    embed = nextcord.Embed(title="📊 Session Highlights", color=nextcord.Color.purple())
    embed.add_field(name="Biggest Winner", value=get_name(biggest_winner), inline=False)
    embed.add_field(name="Biggest Loser", value=get_name(biggest_loser), inline=False)
    embed.add_field(name="Most Bets Placed", value=get_name(most_bets), inline=False)
    if best_win_rate:
        embed.add_field(name="Best Win % (2+ bets)", value=f"{get_name(best_win_rate)} ({best_win_pct:.1f}%)", inline=False)

    await ctx.send(embed=embed)

@bot.slash_command(name="stats", description="View your current session stats")
async def stats(interaction: nextcord.Interaction):
    user_id = interaction.user.id
    user_stats = stats.get(user_id, {
        "bets_placed": 0,
        "total_wagered": 0,
        "total_won": 0,
        "total_lost": 0
    })

    bets_placed = user_stats["bets_placed"]
    total_wagered = user_stats["total_wagered"]
    total_won = user_stats["total_won"]
    total_lost = user_stats["total_lost"]

    percent_won = (total_won / total_wagered * 100) if total_wagered > 0 else 0
    percent_lost = (total_lost / total_wagered * 100) if total_wagered > 0 else 0

    avg_wagered = total_wagered / bets_placed if bets_placed > 0 else 0
    avg_won = total_won / bets_placed if bets_placed > 0 else 0
    avg_lost = total_lost / bets_placed if bets_placed > 0 else 0

    embed = nextcord.Embed(
        title=f"📊 Stats for {ctx.author.display_name}",
        color=nextcord.Color.blue()
    )
    embed.add_field(name="Bets Placed", value=bets_placed)
    embed.add_field(name="Total Wagered", value=total_wagered)
    embed.add_field(name="Total Won", value=total_won)
    embed.add_field(name="Total Lost", value=total_lost)
    embed.add_field(name="% Won", value=f"{percent_won:.1f}%")
    embed.add_field(name="% Lost", value=f"{percent_lost:.1f}%")
    embed.add_field(name="Avg Wagered", value=f"{avg_wagered:.1f}")
    embed.add_field(name="Avg Won", value=f"{avg_won:.1f}")
    embed.add_field(name="Avg Lost", value=f"{avg_lost:.1f}")

    await ctx.send(embed=embed)

@bot.slash_command(name="laststats", description="View your last session stats")
async def laststats(interaction: nextcord.Interaction):
    user_id = ctx.author.id
    user_stats = last_session_stats.get(user_id, {
        "bets_placed": 0,
        "total_wagered": 0,
        "total_won": 0,
        "total_lost": 0
    })

    embed = nextcord.Embed(
        title=f"🕓 Last Session Stats for {ctx.author.display_name}",
        color=nextcord.Color.orange()
    )
    embed.add_field(name="Bets Placed", value=user_stats["bets_placed"])
    embed.add_field(name="Total Wagered", value=user_stats["total_wagered"])
    embed.add_field(name="Total Won", value=user_stats["total_won"])
    embed.add_field(name="Total Lost", value=user_stats["total_lost"])
    await ctx.send(embed=embed)

@bot.slash_command(name="balance", description="Check your balance")
async def balance(interaction: nextcord.Interaction):
    user_id = ctx.author.id
    balance = balances.get(user_id, 1000)
    currently_bet = sum(
        bet["wagers"].get(user_id, {}).get("amount", 0)
        for bet in bets.values() if not bet.get("locked")
    )
    embed = nextcord.Embed(
        title=f"💰 Balance for {ctx.author.display_name}",
        color=nextcord.Color.gold()
    )
    embed.add_field(name="Current Balance", value=balance)
    embed.add_field(name="Currently Wagered", value=currently_bet)
    await ctx.send(embed=embed)

@bot.slash_command(name="rankings", description="View current session rankings")
async def rankings(interaction: nextcord.Interaction):
    if not session_active:
        await ctx.send("⚠️ Rankings are only available during an active session.")
        return
    if not lifetime_stats:
        await ctx.send("No ranking data available yet.")
        return

    sorted_users = sorted(stats.items(), key=lambda x: x[1].get("total_won", 0), reverse=True)
    embed = nextcord.Embed(title="🏆 Session Rankings", color=nextcord.Color.gold())

    for rank, (uid, data) in enumerate(sorted_users[:10], start=1):
        member = ctx.guild.get_member(uid)
        name = member.display_name if member else f"User {uid}"
        embed.add_field(
            name=f"#{rank} - {name}",
            value=f"Won: {data['total_won']} | Lost: {data['total_lost']} | Bets: {data['bets_placed']}",
            inline=False
        )

    await ctx.send(embed=embed)

@bot.slash_command(name="lifetimerankings", description="View all-time rankings")
async def lifetimerankings(interaction: nextcord.Interaction):
    if not lifetime_stats:
        await ctx.send("No lifetime ranking data available yet.")
        return

    sorted_users = sorted(lifetime_stats.items(), key=lambda x: x[1].get("total_won", 0), reverse=True)
    embed = nextcord.Embed(title="🌐 Lifetime Rankings", color=nextcord.Color.green())

    for rank, (uid, data) in enumerate(sorted_users[:10], start=1):
        member = ctx.guild.get_member(uid)
        name = member.display_name if member else f"User {uid}"
        embed.add_field(
            name=f"#{rank} - {name}",
            value=f"Won: {data['total_won']} | Lost: {data['total_lost']} | Bets: {data['bets_placed']}",
            inline=False
        )

    await ctx.send(embed=embed)

@bot.slash_command(name="lifetimestats", description="View your lifetime stats")
async def lifetimestats(interaction: nextcord.Interaction):
    user_id = ctx.author.id
    user_stats = lifetime_stats.get(user_id, {
        "bets_placed": 0,
        "total_wagered": 0,
        "total_won": 0,
        "total_lost": 0
    })

    embed = nextcord.Embed(
        title=f"🌐 Lifetime Stats for {ctx.author.display_name}",
        color=nextcord.Color.teal()
    )
    embed.add_field(name="Bets Placed", value=user_stats["bets_placed"])
    embed.add_field(name="Total Wagered", value=user_stats["total_wagered"])
    embed.add_field(name="Total Won", value=user_stats["total_won"])
    embed.add_field(name="Total Lost", value=user_stats["total_lost"])
    await ctx.send(embed=embed)

# Update stats after bet is resolved
async def update_user_stats(message_id, winning_option):
    bet = bets.get(message_id)
    if not bet:
        return

    for user_id, wager in bet["wagers"].items():
        session = stats.setdefault(user_id, {
            "bets_placed": 0, "total_wagered": 0, "total_won": 0, "total_lost": 0
        })
        lifetime = lifetime_stats.setdefault(user_id, {
            "bets_placed": 0, "total_wagered": 0, "total_won": 0, "total_lost": 0
        })

        for d in [session, lifetime]:
            d["bets_placed"] += 1
            d["total_wagered"] += wager["amount"]

        if wager["option"] == winning_option:
            total_pot = sum(w["amount"] for w in bet["wagers"].values())
            total_winning = sum(w["amount"] for w in bet["wagers"].values() if w["option"] == winning_option)
            share = wager["amount"] / total_winning
            win_amount = int(share * total_pot)

            # 🪙 Apply winnings to balance
            balances[user_id] = balances.get(user_id, 1000) + win_amount
            print(f"[💰] Updated balance for {user_id}: {balances[user_id]}")
    save_data()

            session["total_won"] += win_amount
            lifetime["total_won"] += win_amount
        else: 
            session["total_lost"] += wager["amount"]
            lifetime["total_lost"] += wager["amount"]

# Load token from .env file
from dotenv import load_dotenv
load_dotenv()

@createbet.autocomplete("question")
async def autocomplete_bet_question(interaction: nextcord.Interaction, value: str):
    options = []
    for msg_id, bet in bets.items():
        if not bet.get("locked") and value.lower() in bet["question"].lower():
            label = f"{bet['question'][:90]}..." if len(bet['question']) > 90 else bet['question']
            options.append(SlashOptionChoice(name=label, value=str(msg_id)))
    return options[:25]

# Run the bot using your token stored in the DISCORD_BOT_TOKEN environment variable
bot.run(os.getenv("DISCORD_BOT_TOKEN"))
