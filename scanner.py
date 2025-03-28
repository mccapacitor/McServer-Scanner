import csv
import discord
import logging
import os
import re
import socket
from discord.ext import commands
from mcstatus import JavaServer

DISCARD_PHRASES = [
    "Server not found",
    "Server doesn't exist",
    "Connection refused",
    "Not reachable"
]

intents = discord.Intents.default()
intents.message_content = True

PREFIX = "!"
bot = commands.Bot(command_prefix=PREFIX, intents=intents)
logging.basicConfig(level=logging.ERROR)
logging.getLogger("discord.gateway").setLevel(logging.ERROR)

tasks = []

def generate_similar_ips(ip):
    ip_parts = list(map(int, ip.split(".")))

    while True:
        yield ".".join(map(str, ip_parts))
        ip_parts[3] += 1
        for i in range(3, 0, -1):
            if ip_parts[i] > 255:
                ip_parts[i] = 0
                ip_parts[i - 1] += 1
        if ip_parts[0] > 255:
            ip_parts = [0, 0, 0, 0]

def clean_motd(motd):
    return re.sub(r'[\x00-\x1F\x7F]', '', motd)

async def check_server(ip, port):
    server = JavaServer(ip, port)
    try:
        status = server.status()
        motd_text = ''
        for item in status.motd.parsed:
            if isinstance(item, str):
                motd_text += item
            elif hasattr(item, 'text'):
                motd_text += item.text

        motd = clean_motd(motd_text)
        players_online = status.players.online
        max_players = status.players.max
        favicon_url = status.icon 
        is_cracked = status.version.name.lower() == 'offline'
        
        whitelist_enabled = "whitelist" in status.description.lower() or status.players.sample == []

        for phrase in DISCARD_PHRASES:
            if phrase.lower() in motd.lower():
                print(f"Server at {ip}:{port} discarded due to MOTD: {motd}")
                return False

        print(f"Found Minecraft server at {ip}:{port} with MOTD: {motd}")
        
        return {
            "ip": ip,
            "port": port,
            "motd": motd,
            "players_online": players_online,
            "max_players": max_players,
            "favicon": favicon_url,
            "is_cracked": is_cracked,
            "whitelist": whitelist_enabled,
        }
    except (socket.timeout, ConnectionRefusedError, OSError) as e:
        print(f"Error with {ip}:{port} - {e}")
        return False

async def scan_minecraft_servers(ctx, ip_list, port_start, port_end):
    global tasks 
    tasks = [] 

    for ip in ip_list:
        for port in range(port_start, port_end + 1):
            print(f"Checking {ip}:{port}...")
            server_info = await check_server(ip, port)
            if server_info:
                server_type = "Cracked" if server_info["is_cracked"] else "Premium"
                whitelist_status = "Enabled" if server_info["whitelist"] else "Disabled"

                save_to_csv([[server_info["ip"], server_info["port"], server_type]])

                embed = discord.Embed(
                    title="Server pinged!",
                    description=f"**{server_info['ip']}:{server_info['port']}**",
                    color=discord.Color.red()
                )
                embed.add_field(name="MOTD", value=server_info["motd"], inline=False)
                embed.add_field(
                    name="Players Online",
                    value=f"{server_info['players_online']} / {server_info['max_players']}",
                    inline=False
                )
                embed.add_field(name="Auth method", value=server_type, inline=False)
                embed.add_field(name="Whitelist", value=whitelist_status, inline=False)

                favicon_path = "default_favicon.png"
                if os.path.exists(favicon_path):
                    file = discord.File(favicon_path, filename="favicon.png")
                    embed.set_thumbnail(url="attachment://favicon.png")
                    await ctx.send(file=file, embed=embed)
                else:
                    embed.set_thumbnail(url="https://media.minecraftforum.net/attachments/thumbnails/300/619/115/115/636977108000120237.png")
                    await ctx.send(embed=embed)

def save_to_csv(servers):
    try:
        with open('scannedServers.csv', mode='a', newline='', encoding='utf-8') as file:
            writer = csv.writer(file)
            for server in servers:
                writer.writerow(server)
        print(f"Server info saved to 'scannedServers.csv'.")
    except PermissionError:
        print("Permission error: Close 'scannedServers.csv' or run as admin.")
    except Exception as e:
        print(f"Failed to save to CSV: {e}")

@bot.command()
async def scan(ctx, ip: str, port_start: int, port_end: int):
    await ctx.send(f"Scanning similar IPs based on {ip}...")
    similar_ips = generate_similar_ips(ip)
    await scan_minecraft_servers(ctx, similar_ips, port_start, port_end)
    await ctx.send(f"Scanning complete! Results saved to 'scannedServers.csv'.")
    
# Run the bot
bot.run("")
