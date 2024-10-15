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

# Check if the log directory exists and create it if not
log_dir = os.path.dirname(log_file)
if not os.path.exists(log_dir):
    os.makedirs(log_dir)

# Setup logging
logging.basicConfig(filename=log_file, level=log_level,
                    format='%(asctime)s - %(levelname)s - %(message)s')

# Initialize the Telegram client
client = TelegramClient('telegram_client', api_id, api_hash)

# Initialize the scheduler for task scheduling
scheduler = AsyncIOScheduler()

def execute_query(query, params=None):
    """Execute a query with optional parameters and return the result."""
    try:
        conn = sqlite3.connect(db_file)
        cursor = conn.cursor()
        if params:
            cursor.execute(query, params)
        else:
            cursor.execute(query)
        conn.commit()
        return cursor.fetchall()
    except sqlite3.Error as e:
        logging.error(f'An error occurred: {e}')
        return None
    finally:
        conn.close()

def ensure_table(table_name, table_schema):
    """Ensure a table exists with the given schema."""
    execute_query(f"CREATE TABLE IF NOT EXISTS {table_name} ({table_schema})")
    logging.info(f'{table_name} table ensured.')

def check_database():
    """Check if the database exists, create necessary tables, and ensure settings are initialized."""
    ensure_table('settings', 'key TEXT PRIMARY KEY, value TEXT')
    ensure_table('templates', 'name TEXT PRIMARY KEY, message TEXT')
    ensure_table('auto_responses', 'chat_id TEXT, sent_time TEXT, PRIMARY KEY (chat_id, sent_time)')
    
    # Check if the settings table has any rows
    settings_count_result = execute_query("SELECT COUNT(*) FROM settings")
    
    if settings_count_result and settings_count_result[0][0] == 0:
        reset_settings_to_default()
        logging.info('Settings table was empty. Default settings have been initialized.')

async def handle_messages(event):
    """Process incoming messages and respond accordingly."""
    sender = event.sender_id

    logging.info(f'Received message from {sender}')

    # Check if the message is from the user to themselves (self-chat)
    if sender == event.chat_id:
        command_output = process_command(event.message.text)
        await client.send_message(sender, command_output)
        return

    # Check if the autoresponder is activated
    autoresponder_status = execute_query("SELECT value FROM settings WHERE key='autoresponder_status'")
    
    if autoresponder_status and autoresponder_status[0][0] == 'on':
        message_types_result = execute_query("SELECT value FROM settings WHERE key='message_types'")
        
        if message_types_result:
            message_types = message_types_result[0][0].split(',')

            # Responding to personal messages
            if sender != event.client.uid and 'personal' in message_types:
                auto_response_count_result = execute_query("SELECT COUNT(*) FROM auto_responses WHERE chat_id=?", (event.chat_id,))
                
                if auto_response_count_result and auto_response_count_result[0][0] > 0:
                    last_sent_time_result = execute_query("SELECT sent_time FROM auto_responses WHERE chat_id=? ORDER BY sent_time DESC LIMIT 1", (event.chat_id,))
                    
                    if last_sent_time_result:
                        last_sent_time_str = last_sent_time_result[0][0]
                        last_sent_time = datetime.strptime(last_sent_time_str, '%Y-%m-%d %H:%M:%S')
                        
                        if (datetime.now() - last_sent_time).days < 7:
                            return

                await send_auto_response(event)

async def send_auto_response(event):
    """Send an automatic response based on current configuration and message templates."""
    
    default_message_result = execute_query("SELECT value FROM settings WHERE key='default_message'")
    
    if default_message_result:
        default_message = default_message_result[0][0]

        await client.send_message(event.chat_id, default_message)
        
        logging.info(f'Sent auto response: {default_message}')
        
        execute_query("INSERT INTO auto_responses (chat_id, sent_time) VALUES (?, ?)", 
                      (event.chat_id, datetime.now().strftime('%Y-%m-%d %H:%M:%S')))

def reset_settings_to_default():
    """Reset all settings to default values."""
    
    default_settings = {
        'autoresponder_status': 'off',
        'default_message': "I'm on vacation right now and don't check my messages regularly. If it's important, please call me.",
        'response_delay': '0',
        'response_frequency_limit': 'once a week',
        'message_types': 'personal'
    }
    
    for key, value in default_settings.items():
        execute_query("INSERT OR REPLACE INTO settings (key, value) VALUES (?, ?)", (key, value))
    
    logging.info('All settings have been set to default values.')

def process_command(command):
    """Handle configuration commands and update the database accordingly."""
    
    parts = command.split(maxsplit=1)
    cmd = parts[0]
    args = parts[1] if len(parts) > 1 else ''

    output = ''
    
    if cmd == '/autoresponder':
        status = args if args in ['on', 'off'] else 'off'
        execute_query("INSERT OR REPLACE INTO settings (key, value) VALUES (?, ?)", ('autoresponder_status', status))
        output = f'Autoresponder set to {status}'

    elif cmd == '/activate':
        subcmd, time_str = args.split(maxsplit=1)
        key_name = f'activate_{subcmd}'
        
        execute_query("INSERT OR REPLACE INTO settings (key, value) VALUES (?, ?)", (key_name, time_str))
        
        output_type = "activation" if subcmd == "from" else "deactivation"
        
        output = f'Autoresponder {output_type} scheduled {subcmd} {time_str}'

    elif cmd == '/setmessage':
        message = args
        execute_query("INSERT OR REPLACE INTO settings (key, value) VALUES (?, ?)", ('default_message', message))
        output = f'Default message set to: {message}'

    elif cmd == '/settemplate':
        name, message = args.split(':', 1)
        
        execute_query("INSERT OR REPLACE INTO templates (name, message) VALUES (?, ?)", (name.strip(), message.strip()))
        
        output = f'Template "{name}" set.'

    elif cmd == '/usetemplate':
        name = args.strip()
        
        result = execute_query("SELECT message FROM templates WHERE name=?", (name,))
        
        if result:
            execute_query("INSERT OR REPLACE INTO settings (key, value) VALUES (?, ?)", ('default_message', result[0][0]))
            output = f'Template "{name}" used as default message.'
            
        else:
            output = f'Template "{name}" not found.'

    elif cmd == '/listtemplates':
        
        templates_result= execute_query("SELECT name FROM templates")
        
        templates_list= [row[0] for row in templates_result]
        
        output = "Templates: " + ", ".join(templates_list)

    elif cmd == '/deletetemplate':
       
       name= args.strip()
       
       execute_query("DELETE FROM templates WHERE name=?", (name,))
       
       output= f'Template "{name}" deleted.'

    elif cmd == '/setdelay':
       
       delay= int(args)
       
       execute_query("INSERT OR REPLACE INTO settings (key, value) VALUES (?, ?)", ('response_delay', delay))
       
       output= f'Response delay set to: {delay} seconds'

    elif cmd == '/setfrequency':
      
      frequency= args
      
      execute_query("INSERT OR REPLACE INTO settings (key, value) VALUES (?, ?)", ('response_frequency_limit', frequency))
      
      output= f'Response frequency set to: {frequency}'

    elif cmd == '/types':
     
        message_types= args
        
        execute_query("INSERT OR REPLACE INTO settings (key, value) VALUES (?, ?)", ('message_types', message_types))
        
        output= f'Message types set to: {message_types}'

    elif cmd == '/stats':
     
        total_responses, unique_chats= get_auto_response_statistics()
        
        output= f'Total auto-responses sent: {total_responses}, Unique chats responded to: {unique_chats}'

    elif cmd == '/showconfig':
     
        config_settings_result= execute_query("SELECT key, value FROM settings")
        
        config_settings="\n".join([f"{row[0]}: {row[1]}" for row in config_settings_result])
        
        output=f"Current configuration:\n{config_settings}"

    elif cmd == '/reset':
     
        reset_settings_to_default()
        
        output='All settings have been reset to default.'

    elif cmd == '/confirmreset':
     
        pass

    elif cmd == '/help':
     
        output=("Available commands:\n"
                "/autoresponder on|off\n"
                "/activate from <date/time>\n"
                "/activate until <date/time>\n"
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
                "/confirmreset\n"
                "/help\n\n"
                "More information on GitHub: https://github.com/hutt/advanced-telegram-autoresponder")

    else:
     
        output='Unknown command. Enter /help to see available commands.'

    logging.info(output)

    return "**Telegram Autoresponder Bot**\n" + output

def get_auto_response_statistics():
   
   total_responses_result=execute_query("SELECT COUNT(*) FROM auto_responses")
   
   total_responses=total_responses_result[0][0]if total_responses_result else 0
   
   unique_chats_result=execute_query("SELECT COUNT(DISTINCT chat_id) FROM auto_responses")
   
   unique_chats=unique_chats_result[0][0]if unique_chats_result else 0
   
   return total_responses, unique_chats

def main():
   
   check_database()

   scheduler.start()

   client.add_event_handler(handle_messages, events.NewMessage)

if __name__=='__main__':
   
   client.start(phone=phone_number)
   
   main()
   
   client.run_until_disconnected()