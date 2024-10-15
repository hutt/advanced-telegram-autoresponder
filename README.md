# Advanced Telegram Autoresponder Bot

A Python-based Telegram autoresponder bot for personal accounts. It acts like a normal Telegram client and can be configured easily using commands in a chat with yourself.

The autoresponder allows scheduled activiation/deactivation (optionally), supports message templates and a few more features (see below).

## Installation

### Prerequisites

- Python 3.7 or higher
- Telegram account credentials (API ID and API Hash)

### Installation

1. Obtain Telegram API Credentials:
   1. Go to [my.telegram.org](https://my.telegram.org).
   2. Log in with your phone number and use the confirmation code sent to your Telegram app.
   3. Navigate to "API development tools" and create a new application.
   4. Note down your api_id and api_hash.
2. Clone the repository
   ```bash
   git clone https://github.com/hutt/advanced-telegram-autoresponder.git
   cd advanced-telegram-autoresponder
   ```
3. Set Up the Environment
   
   Create a `.env` file in the project root directory and fill in the API credentials:
   ```text
   # Telegram API credentials
   TELEGRAM_API_ID=<your api_id here>
   TELEGRAM_API_HASH=<your api_hash here>
   TELEGRAM_PHONE_NUMBER=<your phone number here (international format, starting with +)>

   # Database configuration
   DB_FILE=database.db

   # Logging configuration
   LOG_FILE=logs/advanced-telegram-autoresponder.log
   LOG_LEVEL=INFO
   ```
4. Install Dependencies
   ```bash
   pip install -r requirements.txt
   ```
5. Start the bot using your system's Python interpreter:
   ```bash
   python autoresponder.py
   ```

   If you've set up 2FA and/or a login password, you'll be prompted for a verification code and/or the password.


## Using the Autoresponder Bot

* Open Telegram and start a chat with yourself (search for your own contact).
* Use commands like /autoresponder on, /setmessage <message>, etc., directly in this chat to configure and test the bot.

### Available Commands

You can configure the bot in a chat with yourself using the following commands:

- `/autoresponder on|off`: Toggle the autoresponder.
- `/activate from <date/time>`: Schedule activation of the autoresponder.
- `/activate until <date/time>`: Schedule deactivation of the autoresponder.
- `/setmessage <message>`: Set a default response message.
- `/settemplate <name>:<message>`: Save a new response template.
- `/usetemplate <name>`: Use a saved template as the response message.
- `/listtemplates`: List all saved templates.
- `/deletetemplate <name>`: Delete a specified template.
- `/setdelay <seconds>`: Set a delay between receiving and responding to messages.
- `/setfrequency <limit>`: Set frequency limits for responses (e.g., every message, daily, weekly, monthly).
- `/types personal|group|all`: Select message types to respond to.
- `/stats`: Display statistics about sent auto-responses.
- `/showconfig`: Display current configuration settings.
- `/reset`: Reset all settings to default; requires confirmation with `/confirmreset`.
- `/help`: Provide information about available commands and their usage.


## License

This project is licensed under the MIT License. You are free to use, modify, and distribute this software, provided that the original license terms are included with any substantial portions of the software. For more details, please refer to the [LICENSE](LICENSE) file included in this repository.
