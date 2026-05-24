#!/usr/bin/env python3
"""
Advanced Reverse IP Lookup Telegram Bot
Multi-Source IP domain finder for Telegram
Auto-installs required libraries
Direct IP input only - no commands needed
Added VirusTotal API integration (silent mode)
"""

import subprocess
import sys
import importlib
import os

def install_package(package):
    """Install a Python package automatically"""
    try:
        subprocess.check_call([sys.executable, "-m", "pip", "install", "--quiet", package])
        return True
    except Exception as e:
        print(f"Failed to install {package}: {e}")
        return False

def check_and_install_requirements():
    """Check and install required packages"""
    required_packages = {
        'requests': 'requests',
        'telegram': 'python-telegram-bot',
        'colorama': 'colorama'
    }
    
    missing_packages = []
    
    print("=" * 60)
    print("Checking required libraries...")
    print("=" * 60)
    
    for module_name, package_name in required_packages.items():
        try:
            importlib.import_module(module_name)
            print(f"✓ {package_name} - Already installed")
        except ImportError:
            print(f"✗ {package_name} - Not found, installing...")
            if install_package(package_name):
                print(f"✓ {package_name} - Successfully installed")
            else:
                print(f"✗ {package_name} - Failed to install")
                missing_packages.append(package_name)
    
    if missing_packages:
        print("\n" + "=" * 60)
        print("ERROR: Some packages failed to install. Please install manually:")
        print(f"pip install {' '.join(missing_packages)}")
        print("=" * 60)
        return False
    
    print("\n" + "=" * 60)
    print("All required libraries are ready!")
    print("=" * 60 + "\n")
    return True

# Install requirements before importing
if not check_and_install_requirements():
    sys.exit(1)

# Now import all required libraries
import requests
import asyncio
import logging
from concurrent.futures import ThreadPoolExecutor
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, MessageHandler, filters, CallbackQueryHandler, ContextTypes
from colorama import init, Fore, Style
import re
import time
from typing import List, Set
import io

# Initialize colorama
init(autoreset=True)

# Bot Token
TOKEN = "8005589345:AAHCUaZO4VVap18dUbnLtY6KjzWIRC_cJOQ"

# VirusTotal API Key (Added silently)
VIRUSTOTAL_API_KEY = "dc0deb9c0d474efc73f78eb427d7a0b19c54a3dddfb3954f9d865a409452e0d0"

# Owner Info
OWNER_NAME = "K2"
OWNER_USERNAME = "@mujta1n"
OWNER_LINK = "https://t.me/mujta1n"

# Setup logging
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# Store user sessions and states
user_sessions = {}
user_states = {}

BANNER = """
╔═════════════════════╗
║               K2 Tools                ║
╚═════════════════════╝
"""

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Send welcome message on /start"""
    user_id = update.effective_user.id
    user_states[user_id] = False
    
    welcome_message = f"""
{BANNER}

🌟 *Welcome to Reverse IP Lookup Bot!* 🌟

I can help you find all domains hosted on any IP address.

📌 *How to use:*
• Simply send me any IP address

📝 *Examples:*
8.8.8.8
185.199.108.153
1.1.1.1

✨ *Features:*
• Send IP directly
• Results as text file
• Fast and simple

Just send me an IP address to get started!
    """
    
    keyboard = [
        [InlineKeyboardButton("🔍 Try Now - Send IP", callback_data="example_ip")],
        [InlineKeyboardButton("ℹ️ Help", callback_data="help"),
         InlineKeyboardButton("👤 Owner", url=OWNER_LINK)],
        [InlineKeyboardButton("📖 About", callback_data="about")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await update.message.reply_text(welcome_message, parse_mode='Markdown', reply_markup=reply_markup)

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle direct IP messages only"""
    message_text = update.message.text.strip()
    
    # Check if message is an IP address
    ip_pattern = re.compile(r'^(\d{1,3}\.){3}\d{1,3}$')
    
    if ip_pattern.match(message_text):
        await process_ip_lookup(update, context, message_text)
    else:
        await update.message.reply_text(
            f"❌ '{message_text}' is not a valid IP address\n\n"
            f"Please send a valid IP address like:\n"
            f"8.8.8.8\n185.199.108.153\n1.1.1.1\n\n"
            f"Use /start to see welcome message."
        )

async def process_ip_lookup(update: Update, context: ContextTypes.DEFAULT_TYPE, ip: str):
    """Process IP lookup and send results"""
    user_id = update.effective_user.id
    
    status_message = await update.message.reply_text(
        f"🔍 Scanning IP: {ip}\n\n"
        f"⏳ Processing request...\n"
        f"🔄 This may take a few moments\n\n"
        f"✨ Please wait..."
    )
    
    try:
        domains_set = await search_ip(ip)
        domains = sorted(list(domains_set))
        total_count = len(domains)
        
        file_obj = create_domains_file(domains, ip)
        
        caption = f"""
✅ Scan Completed!

🌐 IP Address: {ip}
📊 Total Domains Found: {total_count}

📁 File attached below contains all domains

🔍 Scan Date: {time.strftime('%Y-%m-%d')}
        """
        
        keyboard = [
            [InlineKeyboardButton("🔄 New Search", callback_data="new_search"),
             InlineKeyboardButton("👤 Owner", url=OWNER_LINK)],
            [InlineKeyboardButton("ℹ️ Help", callback_data="help")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await status_message.delete()
        await update.message.reply_document(
            document=file_obj,
            filename=file_obj.name,
            caption=caption,
            reply_markup=reply_markup
        )
        
        user_sessions[user_id] = {
            'domains': domains,
            'ip': ip,
            'count': total_count,
            'timestamp': time.time()
        }
        
        logger.info(f"Search completed for {ip}: Found {total_count} domains for user {user_id}")
        
        if total_count == 0:
            keyboard = [
                [InlineKeyboardButton("🔄 New Search", callback_data="new_search"),
                 InlineKeyboardButton("👤 Owner", url=OWNER_LINK)]
            ]
            reply_markup = InlineKeyboardMarkup(keyboard)
            await update.message.reply_text(
                f"⚠️ No domains found for IP: {ip}\n\n"
                f"💡 Tips:\n"
                f"• Verify the IP address is correct\n"
                f"• Try again later\n\n"
                f"Press 'New Search' to try another IP",
                reply_markup=reply_markup
            )
        
    except Exception as e:
        logger.error(f"Error in process_ip_lookup: {str(e)}")
        await status_message.edit_text(
            f"❌ Failed to scan {ip}\n\nPlease try again later."
        )

async def search_ip(ip: str) -> Set[str]:
    """Search domains using all sources including VirusTotal (silent)"""
    all_domains = set()
    
    queries = [
        query_yougetsignal,
        query_hackertarget,
        query_viewdns,
        query_criminalip,
        query_virustotal,  # Added VirusTotal query (silent)
    ]
    
    with ThreadPoolExecutor(max_workers=5) as executor:
        futures = [executor.submit(query, ip) for query in queries]
        
        for future in futures:
            try:
                domains = future.result(timeout=30)
                all_domains.update(domains)
                await asyncio.sleep(0.5)
            except Exception as e:
                logger.error(f"Search error: {str(e)}")
    
    return all_domains

def query_yougetsignal(ip: str) -> List[str]:
    """Source 1: YouGetSignal"""
    domains = []
    try:
        url = "https://domains.yougetsignal.com/domains.php"
        payload = {"remoteAddress": ip, "key": "", "_": ""}
        headers = {"User-Agent": "Mozilla/5.0", "Content-Type": "application/x-www-form-urlencoded"}
        
        response = requests.post(url, data=payload, headers=headers, timeout=15)
        data = response.json()
        
        if data.get("status") == "Success":
            domains = [d[0] for d in data.get("domainArray", [])]
        logger.info(f"Source 1: Found {len(domains)} domains for {ip}")
    except Exception as e:
        logger.error(f"Source 1 Error: {str(e)}")
    return domains

def query_hackertarget(ip: str) -> List[str]:
    """Source 2: HackerTarget"""
    domains = []
    try:
        url = f"https://api.hackertarget.com/reverseiplookup/?q={ip}"
        response = requests.get(url, timeout=15)
        if response.status_code == 200:
            domains = [d.strip() for d in response.text.split('\n') if d.strip() and 'error' not in d.lower()]
        logger.info(f"Source 2: Found {len(domains)} domains for {ip}")
    except Exception as e:
        logger.error(f"Source 2 Error: {str(e)}")
    return domains

def query_viewdns(ip: str) -> List[str]:
    """Source 3: ViewDNS.info"""
    domains = []
    try:
        session = requests.Session()
        session.headers.update({"User-Agent": "Mozilla/5.0"})
        
        resp = session.get(f"https://viewdns.info/reverseip/?host={ip}&t=1")
        
        token = ""
        if 'name="token"' in resp.text:
            token_match = re.search(r'name="token"\s+value="([^"]+)"', resp.text)
            if token_match:
                token = token_match.group(1)
        
        data = {"host": ip, "t": "1", "submit": "Submit"}
        if token:
            data["token"] = token
            
        resp = session.post("https://viewdns.info/reverseip/", data=data)
        
        if 'Reverse IP Lookup Results' in resp.text:
            lines = resp.text.split('\n')
            for line in lines:
                if any(ext in line for ext in ['.com', '.net', '.org', '.io', '.xyz']):
                    if 'target="_blank">' in line:
                        domain = line.split('target="_blank">')[1].split('<')[0]
                        if domain and '.' in domain and len(domain) < 100:
                            domains.append(domain)
        domains = list(set(domains))[:1000]
        logger.info(f"Source 3: Found {len(domains)} domains for {ip}")
    except Exception as e:
        logger.error(f"Source 3 Error: {str(e)}")
    return domains

def query_criminalip(ip: str) -> List[str]:
    """Source 4: CriminalIP"""
    domains = []
    try:
        url = f"https://api.criminalip.com/v1/ip/domain?ip={ip}"
        headers = {"User-Agent": "Mozilla/5.0"}
        response = requests.get(url, headers=headers, timeout=10)
        if response.status_code == 200:
            data = response.json()
            domains = data.get("data", {}).get("domains", [])
        logger.info(f"Source 4: Found {len(domains)} domains for {ip}")
    except Exception as e:
        logger.error(f"Source 4 Error: {str(e)}")
    return domains

def query_virustotal(ip: str) -> List[str]:
    """Source 5: VirusTotal API - Silent mode (no user notification)"""
    domains = []
    try:
        # VirusTotal API endpoint for IP address reports
        url = f"https://www.virustotal.com/api/v3/ip_addresses/{ip}"
        
        headers = {
            "x-apikey": VIRUSTOTAL_API_KEY,
            "User-Agent": "Mozilla/5.0"
        }
        
        response = requests.get(url, headers=headers, timeout=15)
        
        if response.status_code == 200:
            data = response.json()
            
            # Extract domains from resolved URLs
            if 'data' in data and 'attributes' in data['data']:
                attributes = data['data']['attributes']
                
                # Get resolutions (domain resolutions)
                if 'resolutions' in attributes:
                    for resolution in attributes['resolutions']:
                        if 'hostname' in resolution:
                            domain = resolution['hostname']
                            if domain and '.' in domain:
                                domains.append(domain)
                
                # Get historical resolutions if available
                if 'last_resolution' in attributes and 'hostname' in attributes['last_resolution']:
                    domain = attributes['last_resolution']['hostname']
                    if domain and '.' in domain:
                        domains.append(domain)
                
                # Get URL-based domains
                if 'urls' in attributes:
                    # URLs contain domain information, but we need to extract domains
                    for url_data in attributes['urls'][:200]:  # Limit to 200 URLs
                        if 'url' in url_data:
                            url_string = url_data['url']
                            # Extract domain from URL
                            domain_match = re.search(r'https?://([^/]+)', url_string)
                            if domain_match:
                                domain = domain_match.group(1)
                                if domain and '.' in domain:
                                    domains.append(domain)
        
        # Remove duplicates and filter
        domains = list(set(domains))
        
        # Filter out invalid domains
        valid_domains = []
        for domain in domains:
            if (len(domain) < 100 and 
                '.' in domain and 
                not domain.startswith('*.') and
                not domain.startswith('localhost') and
                not domain.endswith('.local')):
                valid_domains.append(domain)
        
        logger.info(f"Source 5 (VirusTotal): Found {len(valid_domains)} domains for {ip}")
        
    except requests.exceptions.RequestException as e:
        logger.error(f"VirusTotal Request Error: {str(e)}")
    except Exception as e:
        logger.error(f"VirusTotal Error: {str(e)}")
    
    return valid_domains

def create_domains_file(domains: List[str], ip: str) -> io.BytesIO:
    """Create a text file with all domains and count at the bottom"""
    total_domains = len(domains)
    
    file_content = f"""
{'='*70}
REVERSE IP LOOKUP RESULTS
{'='*70}
Target IP: {ip}
Scan Date: {time.strftime('%Y-%m-%d')}
{'='*70}

TOTAL DOMAINS FOUND: {total_domains}
{'='*70}


"""
    
    if total_domains > 0:
        for idx, domain in enumerate(domains, 1):
            file_content += f"{idx:5d}. {domain}\n"
    else:
        file_content += "No domains found for this IP address.\n"
    
    file_content += f"""
{'='*70}
SUMMARY
{'='*70}
Total Domains: {total_domains}
IP Address: {ip}
Scan completed successfully
Sources: YouGetSignal, HackerTarget, ViewDNS, CriminalIP, VirusTotal
{'='*70}
"""
    
    file_obj = io.BytesIO()
    file_obj.write(file_content.encode('utf-8'))
    file_obj.seek(0)
    file_obj.name = f"reverse_ip_{ip}_{int(time.time())}.txt"
    
    return file_obj

async def button_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle button callbacks"""
    query = update.callback_query
    await query.answer()
    
    data = query.data
    user_id = update.effective_user.id
    
    if data == "new_search":
        keyboard = [
            [InlineKeyboardButton("🔙 Back to Start", callback_data="back_to_start")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await query.edit_message_text(
            "🔄 New Search Ready!\n\n"
            "Simply send me any IP address:\n"
            "8.8.8.8\n185.199.108.153\n1.1.1.1\n\n"
            "Just type or paste the IP and send.",
            reply_markup=reply_markup
        )
        
    elif data == "back_to_start":
        keyboard = [
            [InlineKeyboardButton("🔍 Try Now - Send IP", callback_data="example_ip")],
            [InlineKeyboardButton("ℹ️ Help", callback_data="help"),
             InlineKeyboardButton("👤 Owner", url=OWNER_LINK)],
            [InlineKeyboardButton("📖 About", callback_data="about")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await query.edit_message_text(
            "🏠 Back to Main Menu\n\n"
            "Welcome to Reverse IP Lookup Bot!\n\n"
            "Simply send me any IP address to get started!\n\n"
            "Examples:\n8.8.8.8\n185.199.108.153\n1.1.1.1",
            reply_markup=reply_markup
        )
        
    elif data == "example_ip":
        await query.edit_message_text(
            "📝 Try this example:\n\n"
            "Send this IP address:\n8.8.8.8\n\n"
            "Or type any other IP address you want to lookup!"
        )
        await asyncio.sleep(2)
        # Create a dummy update for process_ip_lookup
        await process_ip_lookup(update, context, "8.8.8.8")
        
    elif data == "help":
        help_text = """
🔍 Help Guide

How to use this bot:

1. Direct IP Input (Easiest)
   Just type or paste any IP address
   Example: 8.8.8.8

2. New Search Button
   Press "New Search" after results
   Then send another IP directly

Commands:
/start - Show welcome menu
/help - Show this help
/about - Bot information

Notes:
- Search takes a few moments
- Results sent as text file
- File includes total domain count
- No commands needed - just send IP
- Includes VirusTotal data (silent mode)

Need help? Contact the owner via the Owner button!
        """
        keyboard = [[InlineKeyboardButton("🔙 Back", callback_data="back_to_start")]]
        reply_markup = InlineKeyboardMarkup(keyboard)
        await query.edit_message_text(help_text, reply_markup=reply_markup)
        
    elif data == "about":
        about_text = """
🤖 Bot Information

Version: 3.1
Developer: K2

Features:
- Direct IP input - no commands needed
- Advanced multi-source scanning
- VirusTotal API integration (silent)
- File output with domain count
- Simple button interface
- Fast and reliable

Usage:
- Just send any IP address
- Unlimited searches
- Text file results
- Real-time processing

Contact: @mujta1n

@K2_IP_reverse_bot
        """
        keyboard = [[InlineKeyboardButton("🔙 Back", callback_data="back_to_start")]]
        reply_markup = InlineKeyboardMarkup(keyboard)
        await query.edit_message_text(about_text, reply_markup=reply_markup)

async def error_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle general errors - silent"""
    logger.error(f"Update {update} caused error {context.error}")

def main():
    """Run the bot"""
    print(Fore.CYAN + BANNER + Style.RESET_ALL)
    print(Fore.GREEN + "[✓] Starting Telegram bot..." + Style.RESET_ALL)
    print(Fore.YELLOW + f"[*] Token: {TOKEN[:10]}..." + Style.RESET_ALL)
    print(Fore.MAGENTA + f"[*] Owner: {OWNER_NAME} ({OWNER_USERNAME})" + Style.RESET_ALL)
    print(Fore.BLUE + "[✓] VirusTotal API integrated (silent mode)" + Style.RESET_ALL)
    
    application = Application.builder().token(TOKEN).build()
    
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("help", help_command_wrapper))
    application.add_handler(CommandHandler("about", about_command_wrapper))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    application.add_handler(CallbackQueryHandler(button_callback))
    
    application.add_error_handler(error_handler)
    
    print(Fore.GREEN + "[✓] Bot is ready!" + Style.RESET_ALL)
    print(Fore.CYAN + "[*] Bot features:" + Style.RESET_ALL)
    print(Fore.YELLOW + "    • Send IP directly" + Style.RESET_ALL)
    print(Fore.YELLOW + "    • Results as file" + Style.RESET_ALL)
    print(Fore.YELLOW + "    • Interactive buttons" + Style.RESET_ALL)
    print(Fore.YELLOW + f"    • Owner: {OWNER_NAME}" + Style.RESET_ALL)
    print(Fore.GREEN + "    • VirusTotal API (silent mode)" + Style.RESET_ALL)
    print(Fore.CYAN + "\n[*] Find your bot on Telegram and start with /start" + Style.RESET_ALL)
    
    application.run_polling(allowed_updates=Update.ALL_TYPES)

async def help_command_wrapper(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Wrapper for help command"""
    help_text = """
🔍 Help Guide

How to use this bot:

1. Direct IP Input (Easiest)
   Just type or paste any IP address
   Example: 8.8.8.8

2. New Search Button
   Press "New Search" after results
   Then send another IP directly

Commands:
/start - Show welcome menu
/help - Show this help
/about - Bot information

Notes:
- Search takes a few moments
- Results sent as text file
- File includes total domain count
- No commands needed - just send IP
- Multi-source includes VirusTotal (silent)

Need help? Contact @mujta1n
    """
    await update.message.reply_text(help_text)

async def about_command_wrapper(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Wrapper for about command"""
    about_text = """
🤖 Bot Information

Version: 3.1
Developer: K2

Features:
- Direct IP input - no commands needed
- Advanced multi-source scanning
- File output with domain count
- Simple button interface
- Fast and reliable
- VirusTotal integration

Usage:
- Just send any IP address
- Unlimited searches
- Text file results
- Real-time processing

Contact: @mujta1n

@K2_IP_reverse_bot
    """
    await update.message.reply_text(about_text)

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print(Fore.RED + "\n[!] Bot stopped by user" + Style.RESET_ALL)
    except Exception as e:
        print(Fore.RED + f"\n[!] Fatal error: {str(e)}" + Style.RESET_ALL)