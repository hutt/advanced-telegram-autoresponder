import os
from dotenv import load_dotenv
from telethon import TelegramClient, events
import sqlite3
from apscheduler.schedulers.asyncio import AsyncIOScheduler
import logging
from datetime import datetime

# Load environment variables from .env file for configuration
load_dotenv()

# Retrieve configuration values from environment variables
api_id = os.getenv('TELEGRAM_API_ID')
api_hash = os.getenv('TELEGRAM_API_HASH')
phone_number = os.getenv('TELEGRAM_PHONE_NUMBER')
db_file = os.getenv('DB_FILE', 'database.db')  # Default database file path
log_file = os.getenv('LOG_FILE', 'logs/advanced-telegram-autoresponder.log')  # Default log file path
log_level = os.getenv('LOG_LEVEL', 'INFO').upper()  # Set log level from environment

# Validate required configurations; raise error if missing
if not all([api_id, api_hash, phone_number]):
    raise ValueError("API ID, API Hash, and phone number must be set in environment variables.")

# Configure logging to output both to a file and console
logging.basicConfig(
    level=getattr(logging, log_level),
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler(log_file),
        logging.StreamHandler()  # Also log to console for real-time feedback
    ]
)

# Initialize Telegram client using Telethon library
client = TelegramClient('session_name', api_id, api_hash)

# Function to initialize the database connection and create tables if they don't exist
def init_db():
    try:
        conn = sqlite3.connect(db_file)  # Connect to SQLite database
        c = conn.cursor()
        # Create settings table for storing key-value pairs of configurations
        c.execute('''CREATE TABLE IF NOT EXISTS settings (
                        key TEXT PRIMARY KEY,
                        value TEXT)''')
        # Create templates table for storing message templates
        c.execute('''CREATE TABLE IF NOT EXISTS templates (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        name TEXT,
                        message TEXT)''')
        conn.commit()  # Commit changes to the database
        return conn  # Return database connection object
    except sqlite3.Error as e:
        logging.error(f"Database error: {e}")
        raise

conn = init_db()  # Initialize database connection

# Initialize scheduler for managing scheduled tasks like activation/deactivation times
scheduler = AsyncIOScheduler()

# Event handler for incoming messages; differentiates between self-messages and others
@client.on(events.NewMessage)
async def handle_new_message(event):
    sender = await event.get_sender()
    
    # Check if the message is from the user themselves for configuration commands
    if sender.is_self:
        logging.info(f"Configuration message from self: {event.text}")
        
        # Process command if it starts with '/'
        if event.text.startswith('/'):
            await handle_command(event)
    else:
        # Handle messages from others using the autoresponder logic
        autoresponder_enabled = get_setting('autoresponder_enabled')
        if autoresponder_enabled == 'true':
            response_message = get_setting('default_message') or "This is an automated response."
            await event.respond(response_message)

async def handle_command(event):
    """Handles commands sent by the user to themselves."""
    command_text = event.text.split(' ')[0]
    
    # Execute corresponding command handler based on command text
    if command_text == '/autoresponder':
        await toggle_autoresponder(event)
    elif command_text.startswith('/activate'):
        if 'from' in command_text:
            await activate_from(event)
        elif 'until' in command_text:
            await activate_until(event)
    elif command_text == '/setmessage':
        await set_message(event)
    elif command_text == '/usetemplate':
        await use_template(event)
    elif command_text == '/listtemplates':
        await list_templates(event)
    elif command_text == '/deletetemplate':
        await delete_template(event)
    elif command_text == '/setdelay':
        await set_delay(event)
    elif command_text == '/setfrequency':
        await set_frequency(event)
    elif command_text == '/types':
        await set_types(event)
    elif command_text == '/stats':
        await show_stats(event)
    elif command_text == '/showconfig':
        await show_config(event)
    elif command_text == '/reset':
        await reset_settings(event)
    elif command_text == '/confirmreset':
        await confirm_reset(event)
    elif command_text == '/help':
        await show_help(event)

# Command to toggle autoresponder on/off based on user input
@client.on(events.NewMessage(pattern='/autoresponder (on|off)'))
async def toggle_autoresponder(event):
    status = event.pattern_match.group(1)
    set_setting('autoresponder_enabled', status)
    await event.respond(f"Autoresponder {status}.")

# Command to schedule activation of the autoresponder from a specific date/time
@client.on(events.NewMessage(pattern='/activate from (.+)'))
async def activate_from(event):
    try:
        start_time = datetime.strptime(event.pattern_match.group(1), '%Y-%m-%d %H:%M')
        set_setting('activation_start', start_time.strftime('%Y-%m-%d %H:%M'))
        
        # Schedule job to activate autoresponder at specified time; replace existing job if necessary
        scheduler.add_job(lambda: set_setting('autoresponder_enabled', 'true'), 'date', run_date=start_time, id='activate_job')
        
        await event.respond(f"Autoresponder scheduled to activate from {start_time}.")
    except ValueError:
        await event.respond("Invalid date/time format. Use YYYY-MM-DD HH:MM.")
    except Exception as e:
        logging.error(f"Error scheduling activation: {e}")

# Command to schedule deactivation of the autoresponder at a specific date/time
@client.on(events.NewMessage(pattern='/activate until (.+)'))
async def activate_until(event):
    try:
        end_time = datetime.strptime(event.pattern_match.group(1), '%Y-%m-%d %H:%M')
        set_setting('activation_end', end_time.strftime('%Y-%m-%d %H:%M'))
        
        # Schedule job to deactivate autoresponder at specified time; replace existing job if necessary
        scheduler.add_job(lambda: set_setting('autoresponder_enabled', 'false'), 'date', run_date=end_time, id='deactivate_job')
        
        await event.respond(f"Autoresponder scheduled to deactivate at {end_time}.")
    except ValueError:
        await event.respond("Invalid date/time format. Use YYYY-MM-DD HH:MM.")
    except Exception as e:
        logging.error(f"Error scheduling deactivation: {e}")

# Command to set a default message for the autoresponder
@client.on(events.NewMessage(pattern='/setmessage (.+)'))
async def set_message(event):
    message = event.pattern_match.group(1).strip()
    set_setting('default_message', message)
    await event.respond(f"Default response message set to: {message}")

# Command to use a saved template as the current response message
@client.on(events.NewMessage(pattern='/usetemplate (.+)'))
async def use_template(event):
    template_name = event.pattern_match.group(1).strip()
    
    template_message = get_template(template_name)
    
    if template_message:
        set_setting('default_message', template_message)
        await event.respond(f"Using template '{template_name}' as the response message.")
    else:
        await event.respond(f"Template '{template_name}' not found.")

# Command to list all saved templates in the database
@client.on(events.NewMessage(pattern='/listtemplates'))
async def list_templates(event):
    
    c = conn.cursor()
    
    c.execute("SELECT name FROM templates")
    
    templates = c.fetchall()
    
    if templates:
        
        template_list = "\n".join([t[0] for t in templates])
         
        await event.respond(f"Saved templates:\n{template_list}")
        
    else:
        
        await event.respond("No templates found.")

# Command to delete a specified template from the database

@client.on(events.NewMessage(pattern='/deletetemplate (.+)'))

async def delete_template(event):

     template_name = event.pattern_match.group(1).strip()

     c = conn.cursor()

     c.execute("DELETE FROM templates WHERE name=?", (template_name,))

     conn.commit()

     if c.rowcount > 0:

         await event.respond(f"Template '{template_name}' deleted.")

     else:

         await event.respond(f"Template '{template_name}' not found.")

# Command to set a delay between receiving and responding to messages

@client.on(events.NewMessage(pattern='/setdelay (\d+)'))

async def set_delay(event):

     delay_seconds = int(event.pattern_match.group(1))

     set_setting('response_delay', str(delay_seconds))

     await event.respond(f"Response delay set to {delay_seconds} seconds.")

# Command to set frequency limits for responses (e.g., daily, weekly)

@client.on(events.NewMessage(pattern='/setfrequency (.+)'))

async def set_frequency(event):

     limit = event.pattern_match.group(1).strip().lower()

     valid_limits = ['every message', 'daily', 'weekly', 'monthly']

     if limit in valid_limits:

         set_setting('response_frequency', limit)

         await event.respond(f"Response frequency set to: {limit}.")

     else:

         await event.respond("Invalid frequency. Use 'every message', 'daily', 'weekly', or 'monthly'.")

# Command to select which types of messages (personal/group/all) should trigger responses

@client.on(events.NewMessage(pattern='/types (personal|group|all)'))

async def set_types(event):

     message_type = event.pattern_match.group(1)

     set_setting('response_type', message_type)

     await event.respond(f"Response type set to: {message_type}.")

# Command to display statistics about sent auto-responses (e.g., total count)

@client.on(events.NewMessage(pattern='/stats'))

async def show_stats(event):

     # Example implementation; adjust based on how you track stats

     total_responses = get_setting('total_responses') or 0

     await event.respond(f"Total auto-responses sent: {total_responses}")

# Command to show current configuration settings stored in the database

@client.on(events.NewMessage(pattern='/showconfig'))

async def show_config(event):

     config_keys = ['autoresponder_enabled', 'default_message', 'response_delay',

                    'response_frequency', 'response_type']

     config_values = {key: get_setting(key) for key in config_keys}

     config_message = "\n".join([f"{key}: {value}" for key, value in config_values.items()])

     await event.respond(f"Current Configuration:\n{config_message}")

# Command that prompts user confirmation before resetting all settings to default values

@client.on(events.NewMessage(pattern='/reset'))

async def reset_settings(event):

     confirmation_message = "Are you sure you want to reset all settings? Reply with '/confirmreset' to proceed."

     await event.respond(confirmation_message)

# Confirmation command that resets all settings when confirmed by user input '/confirmreset'

@client.on(events.NewMessage(pattern='/confirmreset'))

async def confirm_reset(event):

      # Reset all settings to default values

      default_settings = {

          'autoresponder_enabled': 'false',

          'default_message': '',

          'response_delay': '0',

          'response_frequency': 'weekly',

          'response_type': 'personal',

          # Add more default settings as needed

      }

      for key, value in default_settings.items():

          set_setting(key, value)

      await event.respond("All settings have been reset to default.")

# Help command that lists all available commands and their usage descriptions 

@client.on(events.NewMessage(pattern='/help'))

async def show_help(event):

      help_message = (

          "/autoresponder on|off\n"

          "/activate from <date/time>\n"

          "/activate until <date/time>\n"

          "/activate reset\n"

          "/setmessage <message>\n"

          "/settemplate <name>:<message>\n"

          "/usetemplate <name>\n"

          "/listtemplates\n"

          "/deletetemplate <name>\n"

          "/setdelay <seconds>\n"

          "/setfrequency <limit>\n"

          "/types personal|group|all\n"

          "/stats\n"

          "/showconfig\n"

          "/reset\n"

          "/help\n"

      )

      await event.respond(help_message)

# Main function that starts the Telegram client and runs until disconnected 

async def main():

      try:

           await client.start(phone=phone_number)

           scheduler.start()  # Start scheduler for managing scheduled tasks 

           print("Bot is running...")

           await client.run_until_disconnected()  # Keep bot running until manually stopped 

      except Exception as e:

           logging.error(f"An error occurred: {e}")

client.loop.run_until_complete(main())  # Run main function in asyncio loop 

def set_setting(key, value): 

      try: 

           c = conn.cursor() 

           c.execute("INSERT OR REPLACE INTO settings (key, value) VALUES (?, ?)", (key, value)) 

           conn.commit() 

      except sqlite3.Error as e: 

           logging.error(f"Error setting value: {e}")

def get_setting(key): 

      try: 

           c = conn.cursor() 

           c.execute("SELECT value FROM settings WHERE key=?", (key,))
           
           result = c.fetchone() 
           
           return result[0] if result else None 
      
      except sqlite3.Error as e: 
      
           logging.error(f"Error getting setting: {e}") 
           
           return None

def add_template(name, message): 

      try: 
      
           c = conn.cursor() 
           
           c.execute("INSERT INTO templates (name, message) VALUES (?, ?)", (name, message)) 
           
           conn.commit() 
      
      except sqlite3.Error as e: 
      
           logging.error(f"Error adding template: {e}")

def get_template(name): 

      try: 
      
           c = conn.cursor() 
           
           c.execute("SELECT message FROM templates WHERE name=?", (name,))
           
           result = c.fetchone() 
           
           return result[0] if result else None 
      
      except sqlite3.Error as e: 
      
           logging.error(f"Error getting template: {e}")