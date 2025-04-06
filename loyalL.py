import time
import logging
from selenium.webdriver.common.keys import Keys
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException, NoSuchElementException
from webdriver_manager.chrome import ChromeDriverManager
from dotenv import load_dotenv

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler("whatsapp_bot.log"),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

# Load environment variables
load_dotenv()

# Define trigger words
TRIGGER_WORDS = ["hellokaun"]

def setup_driver():
    """Set up and return the WebDriver with appropriate options."""
    try:
        options = Options()
        options.add_argument("--user-data-dir=./chrome_data")
        options.add_argument("--profile-directory=Default")
        # Prevent detection
        options.add_argument("--disable-blink-features=AutomationControlled")
        options.add_experimental_option("excludeSwitches", ["enable-automation"])
        options.add_experimental_option("useAutomationExtension", False)
        
        service = Service(ChromeDriverManager().install())
        driver = webdriver.Chrome(service=service, options=options)
        driver.execute_script("Object.defineProperty(navigator, 'webdriver', {get: () => undefined})")
        return driver
    except Exception as e:
        logger.error(f"Failed to set up WebDriver: {str(e)}")
        raise

def wait_for_element(driver, xpath, timeout=10):
    """Wait for element to be clickable and return it."""
    try:
        element = WebDriverWait(driver, timeout).until(
            EC.element_to_be_clickable((By.XPATH, xpath))
        )
        return element
    except TimeoutException:
        logger.warning(f"Element not found: {xpath}")
        return None

def sanitize_message(message):
    """Removes non-BMP (e.g., emoji) characters that crash ChromeDriver."""
    return ''.join(c for c in message if ord(c) <= 0xFFFF)

def send_message(driver, response_message):
    """Try all selectors to find message input box and send the message."""
    input_selectors = [
        '//div[@title="Type a message"]',
        '//div[@data-tab="10"]',
        '//div[contains(@class, "selectable-text")][@contenteditable="true"]',
        '//div[@contenteditable="true"]'
    ]

    # Sanitize the response to remove emojis or unsupported characters
    response_message = sanitize_message(response_message)

    for selector in input_selectors:
        logger.info(f"Trying selector: {selector}")
        message_box = wait_for_element(driver, selector, timeout=5)


        if message_box:
            try:
                logger.info("Found message input box, attempting to send message.")
                message_box.click()
                time.sleep(0.5)
                message_box.send_keys(response_message)
                time.sleep(0.3)
                message_box.send_keys(Keys.ENTER)
                logger.info("Message sent successfully.")
                return True
            except Exception as e:
                logger.error(f"Failed to send message with selector {selector}: {e}")
                continue
        else:
            logger.warning(f"Could not find input with selector: {selector}")
    
    logger.error("All selectors failed. Could not send the message.")
    return False


def check_for_messages(driver):
    """Check for messages containing trigger words and respond."""
    try:
        # Try different selectors for unread messages
        unread_selectors = [
            '//span[@data-testid="msg-unread"]',
            '//span[contains(@aria-label, "unread message")]',
            '//span[contains(@class, "unread")]'
        ]
        
        unread_messages = []
        for selector in unread_selectors:
            try:
                elements = driver.find_elements(By.XPATH, selector)
                if elements:
                    unread_messages = elements
                    logger.info(f"Found {len(elements)} unread messages with selector: {selector}")
                    break
            except:
                continue
                
        if not unread_messages:
            return
            
        for message_indicator in unread_messages:
            try:
                # Try multiple methods to click on the chat
                try:
                    # Try clicking directly on the unread message indicator
                    message_indicator.click()
                except:
                    # Try finding the parent chat element
                    try:
                        parent = message_indicator.find_element(By.XPATH, "./ancestor::div[contains(@class, 'chat')]")
                        parent.click()
                    except:
                        # Try a more general approach
                        parent = message_indicator.find_element(By.XPATH, "./../../..")
                        parent.click()
                
                # Wait for chat to load
                time.sleep(2)
                
                # Try multiple selectors for message text
                message_selectors = [
                    '//div[@class="_21Ahp"]',
                    '//div[contains(@class, "message-in")]//span[contains(@class, "selectable-text")]',
                    '//div[contains(@data-testid, "msg-container")]'
                ]
                
                all_messages = []
                for selector in message_selectors:
                    try:
                        elements = driver.find_elements(By.XPATH, selector)
                        if elements:
                            all_messages = elements
                            break
                    except:
                        continue
                
                if not all_messages:
                    logger.warning("Could not find messages in the open chat")
                    continue
                    
                # Get the last message
                last_message = all_messages[-1].text.lower()
                logger.info(f"Last message: {last_message}")
                
                # Check for trigger words
                if any(word in last_message for word in TRIGGER_WORDS):
                    logger.info(f"Trigger word detected in: {last_message}")
                    
                    # Send response
                    success = send_message(driver, "Hi, I'm interested! Can you share more details?")
                    
                    if success:
                        logger.info("Auto-reply sent successfully")
                    else:
                        logger.error("Failed to send auto-reply")
                    
                    # Wait to avoid spamming
                    time.sleep(3)
                    
            except Exception as e:
                logger.error(f"Error processing message: {str(e)}")
                
            finally:
                # Go back to the main chat list
                try:
                    back_button = wait_for_element(driver, '//span[@data-testid="back"]')
                    if back_button:
                        back_button.click()
                        time.sleep(1)
                except:
                    logger.warning("Could not go back to chat list")
        
    except Exception as e:
        logger.error(f"Error in check_for_messages: {str(e)}")

def main():
    """Main function to run the WhatsApp bot."""
    driver = None
    try:
        driver = setup_driver()
        driver.get("https://web.whatsapp.com/")
        logger.info("Opened WhatsApp Web. Waiting for login...")
        
        # Wait for WhatsApp to load
        wait_for_element(driver, '//div[@data-testid="chat-list"]', timeout=60)
        logger.info("WhatsApp Web loaded successfully")
        
        # Main loop
        while True:
            check_for_messages(driver)
            time.sleep(5)  # Check every 5 seconds
            
    except KeyboardInterrupt:
        logger.info("Bot stopped by user")
    except Exception as e:
        logger.critical(f"Fatal error: {str(e)}")
    finally:
        if driver:
            driver.quit()
            logger.info("WebDriver closed")

if __name__ == "__main__":
    main()