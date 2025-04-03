import time
import os
import logging
import sys
import json
import traceback
from datetime import datetime
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from webdriver_manager.chrome import ChromeDriverManager
from selenium.common.exceptions import (
    TimeoutException, 
    NoSuchElementException, 
    StaleElementReferenceException,
    ElementNotInteractableException,
    WebDriverException
)

# Set up enhanced logging
log_dir = "logs"
os.makedirs(log_dir, exist_ok=True)
log_file = os.path.join(log_dir, f"whatsapp_responder_{datetime.now().strftime('%Y%m%d')}.log")

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler(log_file)
    ]
)
logger = logging.getLogger("WhatsAppResponder")

# Define trigger words and their corresponding responses
TRIGGER_RESPONSES = {
    "hellokaun": "Hello there! This is an automated response. I'll get back to you soon."
}

# File to store responded chats
RESPONDED_CHATS_FILE = "responded_chats.json"

def load_responded_chats():
    """Load the set of responded chats from disk."""
    try:
        if os.path.exists(RESPONDED_CHATS_FILE):
            with open(RESPONDED_CHATS_FILE, 'r') as f:
                data = json.load(f)
                # Convert the list back to a set
                return set(data)
        return set()
    except Exception as e:
        logger.error(f"Error loading responded chats: {e}")
        return set()

def save_responded_chats(responded_chats):
    """Save the set of responded chats to disk."""
    try:
        # Convert set to list for JSON serialization
        with open(RESPONDED_CHATS_FILE, 'w') as f:
            json.dump(list(responded_chats), f)
    except Exception as e:
        logger.error(f"Error saving responded chats: {e}")

def setup_driver():
    """Set up and return a configured Chrome WebDriver."""
    try:
        # Set up Chrome options
        options = Options()
        
        # Create chrome data directory if it doesn't exist
        chrome_data_dir = os.path.join(os.getcwd(), "chrome_data")
        os.makedirs(chrome_data_dir, exist_ok=True)
        logger.info(f"Using Chrome data directory: {chrome_data_dir}")
        
        # Add required Chrome options
        options.add_argument(f"--user-data-dir={chrome_data_dir}")
        options.add_argument("--start-maximized")
        options.add_argument("--disable-extensions")
        options.add_argument("--disable-gpu")
        options.add_argument("--no-sandbox")
        options.add_argument("--disable-dev-shm-usage")
        options.add_argument("--disable-web-security")
        options.add_argument("--disable-features=IsolateOrigins,site-per-process")
        
        # Initialize WebDriver with improved error handling
        try:
            service = Service(ChromeDriverManager().install())
            driver = webdriver.Chrome(service=service, options=options)
            logger.info("Successfully initialized Chrome using ChromeDriverManager")
        except Exception as e:
            logger.warning(f"Failed to initialize Chrome with ChromeDriverManager: {e}")
            logger.info("Attempting to initialize Chrome directly")
            driver = webdriver.Chrome(options=options)
            logger.info("Successfully initialized Chrome directly")
            
        return driver
    except Exception as e:
        logger.error(f"Failed to set up Chrome driver: {e}")
        logger.error(traceback.format_exc())
        raise

def wait_for_element(driver, by, selector, timeout=15, condition="presence"):
    """Wait for an element with improved error handling."""
    try:
        wait = WebDriverWait(driver, timeout)
        if condition == "presence":
            return wait.until(EC.presence_of_element_located((by, selector)))
        elif condition == "clickable":
            return wait.until(EC.element_to_be_clickable((by, selector)))
        elif condition == "all":
            return wait.until(EC.presence_of_all_elements_located((by, selector)))
        elif condition == "visible":
            return wait.until(EC.visibility_of_element_located((by, selector)))
    except TimeoutException:
        logger.warning(f"Timeout waiting for element: {selector}")
        return None
    except Exception as e:
        logger.error(f"Error waiting for element {selector}: {e}")
        return None

def is_whatsapp_loaded(driver):
    """Check if WhatsApp Web is fully loaded."""
    indicators = [
        '//div[@id="pane-side"]',
        '//div[@data-testid="chat-list"]',
        '//*[@data-testid="menu"]',
        '//header'
    ]
    
    for selector in indicators:
        if wait_for_element(driver, By.XPATH, selector, timeout=5):
            return True
    return False

def check_for_trigger_words(message_text):
    """Check if any trigger words are in the message and return the appropriate response."""
    if not message_text:
        return None
    
    message_lower = message_text.lower().strip()
    
    for trigger, response in TRIGGER_RESPONSES.items():
        if trigger.lower() in message_lower:
            return {'trigger': trigger, 'response': response}
    
    return None

def send_message(driver, message):
    """Send a message in the currently open chat with improved reliability."""
    max_attempts = 3
    for attempt in range(max_attempts):
        try:
            logger.info(f"Sending message attempt {attempt+1}/{max_attempts}")
            
            # Wait for the chat to fully load
            time.sleep(2)
            
            # Use multiple possible selectors for the input box with longer timeout
            input_box = None
            selectors = [
                '//div[@title="Type a message"]',
                '//div[@data-testid="conversation-compose-box-input"]',
                '//footer//div[@contenteditable="true"]',
                '//div[@role="textbox"]',
                '//*[@data-tab="10"][@contenteditable="true"]',
                '//div[contains(@class, "copyable-text") and @contenteditable="true"]'
            ]
            
            for selector in selectors:
                try:
                    input_box = WebDriverWait(driver, 15).until(
                        EC.element_to_be_clickable((By.XPATH, selector))
                    )
                    if input_box:
                        logger.info(f"Found input box with selector: {selector}")
                        break
                except:
                    continue
            
            if not input_box:
                logger.warning("Could not find message input box, retrying...")
                # Take screenshot for debugging
                try:
                    screenshot_path = f"debug_screenshot_inputbox_{int(time.time())}.png"
                    driver.save_screenshot(screenshot_path)
                    logger.info(f"Screenshot saved to {screenshot_path}")
                except:
                    pass
                continue

            # Make sure the element is in view and clickable
            driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", input_box)
            time.sleep(1)
            
            # Click the input box first to ensure focus
            try:
                input_box.click()
                time.sleep(0.5)
            except:
                logger.warning("Couldn't click input box directly, trying JavaScript click")
                driver.execute_script("arguments[0].click();", input_box)
                time.sleep(0.5)
            
            # Clear any existing text
            input_box.clear()
            time.sleep(0.5)
            
            # Send message text - try multiple methods
            success = False
            
            # Method 1: Direct send_keys
            try:
                lines = message.split('\n')
                for i, line in enumerate(lines):
                    input_box.send_keys(line)
                    if i < len(lines) - 1:
                        input_box.send_keys(Keys.SHIFT + Keys.ENTER)
                success = True
            except Exception as e:
                logger.warning(f"Direct send_keys failed: {e}")
            
            # Method 2: JavaScript execution as fallback
            if not success:
                try:
                    logger.warning("Using JavaScript to set message text")
                    driver.execute_script(
                        'arguments[0].textContent = arguments[1];', 
                        input_box, 
                        message
                    )
                    # Trigger input event to make WhatsApp recognize the text
                    driver.execute_script(
                        'const event = new Event("input", { bubbles: true });'
                        'arguments[0].dispatchEvent(event);', 
                        input_box
                    )
                    success = True
                except Exception as e:
                    logger.warning(f"JavaScript text input failed: {e}")
            
            if not success:
                logger.error("All methods to input text failed")
                continue
            
            # Try multiple send button selectors
            send_button = None
            send_selectors = [
                '//button[@data-testid="send"]',
                '//button[@aria-label="Send"]',
                '//span[@data-testid="send"]',
                '//span[@data-icon="send"]',
                '//*[contains(@class, "send")][@role="button"]',
                '//div[@title="Send"]',
                '//button[contains(@class, "tvf2evcx")]',
                '//button[contains(@class, "send")]'
            ]
            
            button_found = False
            for selector in send_selectors:
                try:
                    send_button = WebDriverWait(driver, 10).until(
                        EC.element_to_be_clickable((By.XPATH, selector))
                    )
                    if send_button:
                        logger.info(f"Found send button with selector: {selector}")
                        button_found = True
                        break
                except:
                    continue
                    
            if not button_found:
                # Try sending with Enter key as fallback
                logger.warning("Send button not found, trying to send with Enter key")
                try:
                    input_box.send_keys(Keys.ENTER)
                    logger.info("Sent message using Enter key")
                    time.sleep(2)
                    return True
                except Exception as e:
                    logger.error(f"Enter key send failed: {e}")
                    continue
            else:
                try:
                    send_button.click()
                    logger.info("Clicked send button")
                except Exception as click_error:
                    logger.warning(f"Regular click failed: {click_error}, trying JavaScript click")
                    try:
                        driver.execute_script("arguments[0].click();", send_button)
                        logger.info("Used JavaScript click for send button")
                    except Exception as js_error:
                        logger.error(f"JavaScript click also failed: {js_error}")
                        continue
                
            # Wait for message to send
            time.sleep(2)
            logger.info("Message sent successfully")
            return True
            
        except Exception as e:
            logger.error(f"Error in send_message attempt {attempt+1}: {str(e)}")
            logger.error(traceback.format_exc())
            if attempt == max_attempts - 1:
                logger.error(f"Failed to send message after {max_attempts} attempts")
                return False
            time.sleep(2)  # Wait before retrying
    
    return False

def find_unread_chats(driver):
    """Find unread chats with improved detection."""
    unread_elements = []
    
    # Try various selectors for unread messages
    for selector in [
        '//span[contains(@aria-label, "unread message")]',
        '//span[@data-icon="unread-count"]',
        '//div[contains(@class, "unread")]',
        '//div[contains(@data-testid, "unread")]',
        '//span[contains(@data-testid, "unread")]',
        '//span[@data-testid="icon-unread-count"]',
        '//div[@data-testid="cell-frame-container"]//span[contains(@class, "unread")]',
        '//div[@data-testid="chat-list"]//div[contains(@aria-label, "unread")]'
    ]:
        try:
            elements = driver.find_elements(By.XPATH, selector)
            if elements:
                logger.info(f"Found {len(elements)} unread chats with selector: {selector}")
                unread_elements.extend(elements)
        except Exception as e:
            logger.warning(f"Error finding unread chats with selector {selector}: {e}")
    
    return unread_elements

def get_chat_details(driver, chat_row):
    """Extract chat details with improved error handling."""
    try:
        # Execute JavaScript to extract chat information
        chat_info = driver.execute_script("""
            const row = arguments[0];
            
            // Try multiple methods to find the name
            let nameEl = row.querySelector('span[dir="auto"][title]') || 
                         row.querySelector('[data-testid="chat-list-title"]') ||
                         row.querySelector('[data-testid="conversation-info-header-chat-title"]') ||
                         row.querySelector('div[title]');
            let name = nameEl ? (nameEl.getAttribute('title') || nameEl.textContent) : "Unknown";
            
            // Try multiple methods to find the message preview
            let previewEl = row.querySelector('span[dir="ltr"]') || 
                           row.querySelector('.copyable-text') ||
                           row.querySelector('[data-testid="last-msg-status"]') ||
                           row.querySelector('div.copyable-text span.selectable-text');
            let preview = previewEl ? previewEl.textContent : "";
            
            // Include timestamp to make the ID more unique
            let timestamp = Date.now();
            
            return {name: name, preview: preview, id: name + "|" + preview + "|" + timestamp};
        """, chat_row)
        
        return chat_info
    except Exception as e:
        logger.error(f"Error getting chat details: {e}")
        return {'name': 'Unknown', 'preview': '', 'id': f'unknown_{time.time()}'}

def open_chat(driver, chat_element):
    """Open a chat with improved error handling."""
    max_attempts = 3
    for attempt in range(max_attempts):
        try:
            # Try direct click first
            try:
                chat_element.click()
                logger.info("Clicked on chat element directly")
            except:
                # Fall back to JavaScript click
                logger.info("Using JavaScript to click on chat element")
                driver.execute_script("arguments[0].click();", chat_element)
            
            # Wait for chat to load
            time.sleep(2)
            
            # Check if chat is opened successfully
            chat_header_selectors = [
                '//header//div[@data-testid="conversation-header"]',
                '//header//div[contains(@class, "chat-header")]',
                '//div[@data-testid="conversation-header-info"]'
            ]
            
            for selector in chat_header_selectors:
                if wait_for_element(driver, By.XPATH, selector, timeout=5, condition="presence"):
                    logger.info("Chat opened successfully")
                    return True
            
            logger.warning(f"Chat might not have opened properly on attempt {attempt+1}")
            if attempt < max_attempts - 1:
                time.sleep(2)  # Wait before retrying
                
        except Exception as e:
            logger.error(f"Error opening chat on attempt {attempt+1}: {e}")
            if attempt < max_attempts - 1:
                time.sleep(2)  # Wait before retrying
    
    logger.error("Failed to open chat after multiple attempts")
    return False

def go_back_to_chat_list(driver):
    """Return to the chat list from an open conversation."""
    try:
        # Try various back button selectors
        back_selectors = [
            '//span[@data-testid="back"]',
            '//button[@title="Back"]',
            '//button[contains(@class, "back")]',
            '//div[@data-testid="back-btn"]',
            '//span[@data-icon="back"]'
        ]
        
        for selector in back_selectors:
            back_button = wait_for_element(driver, By.XPATH, selector, timeout=5, condition="clickable")
            if back_button:
                try:
                    back_button.click()
                    logger.info("Clicked back button")
                    time.sleep(1)
                    return True
                except:
                    try:
                        driver.execute_script("arguments[0].click();", back_button)
                        logger.info("Used JavaScript to click back button")
                        time.sleep(1)
                        return True
                    except:
                        continue
        
        # Alternative: Try to navigate directly to the main page
        logger.warning("Back button not found, trying to navigate to main page")
        driver.get("https://web.whatsapp.com/")
        time.sleep(5)
        return is_whatsapp_loaded(driver)
        
    except Exception as e:
        logger.error(f"Error going back to chat list: {e}")
        return False

def monitor_and_respond(driver):
    """Monitor unread chats and respond to trigger words with improved reliability."""
    logger.info("Starting auto-responder. Press Ctrl+C to exit.")
    
    # Load previously responded chats
    responded_chats = load_responded_chats()
    logger.info(f"Loaded {len(responded_chats)} previously responded chats")
    
    # Set a maximum size for the responded_chats set to prevent memory issues
    MAX_RESPONDED_CHATS = 1000
    
    # Track last activity time for watchdog
    last_activity_time = time.time()
    WATCHDOG_TIMEOUT = 300  # 5 minutes
    
    scan_count = 0
    while True:
        try:
            scan_count += 1
            logger.info(f"Scanning for unread messages (scan #{scan_count})")
            
            # Check if WhatsApp Web is still loaded properly
            if not is_whatsapp_loaded(driver):
                logger.warning("WhatsApp Web interface not detected, refreshing page")
                driver.refresh()
                time.sleep(10)
                if not is_whatsapp_loaded(driver):
                    logger.error("WhatsApp Web failed to load properly after refresh")
                    logger.info("Attempting to navigate to WhatsApp Web again")
                    driver.get("https://web.whatsapp.com/")
                    time.sleep(15)
                    if not is_whatsapp_loaded(driver):
                        logger.error("Critical error: Unable to load WhatsApp Web")
                        break
            
            # Find unread chats
            unread_elements = find_unread_chats(driver)
            
            if unread_elements:
                logger.info(f"Found {len(unread_elements)} unread chat(s)")
                last_activity_time = time.time()
            
            # Process each unread chat
            for element in unread_elements:
                try:
                    # Find chat container
                    chat_row = driver.execute_script("""
                        let el = arguments[0];
                        for (let i = 0; i < 8; i++) {
                            if (!el) return null;
                            if (el.getAttribute('data-testid') === 'cell-frame-container' || 
                                el.classList.contains('chat') || 
                                el.getAttribute('role') === 'row') return el;
                            el = el.parentElement;
                        }
                        return el;
                    """, element)
                    
                    if not chat_row:
                        logger.warning("Could not find chat container for an unread message")
                        continue
                    
                    # Get chat details
                    chat_info = get_chat_details(driver, chat_row)
                    
                    # Generate a simplified ID for tracking (without timestamp)
                    simplified_id = chat_info['name'] + "|" + chat_info['preview']
                    
                    # Check if already responded to this specific message
                    if simplified_id in responded_chats:
                        logger.info(f"Already responded to message: {simplified_id}")
                        continue
                    
                    logger.info(f"Unread message from: {chat_info['name']}")
                    logger.info(f"Preview: {chat_info['preview']}")
                    
                    # Check for trigger words
                    trigger_match = check_for_trigger_words(chat_info['preview'])
                    
                    if trigger_match:
                        logger.info(f"Trigger word detected: {trigger_match['trigger']}")
                        
                        # Open chat
                        if open_chat(driver, chat_row):
                            # Send response
                            if send_message(driver, trigger_match['response']):
                                logger.info(f"Sent auto-response to {chat_info['name']}")
                                responded_chats.add(simplified_id)
                                
                                # Save responded chats periodically
                                if len(responded_chats) % 5 == 0:
                                    save_responded_chats(responded_chats)
                            else:
                                logger.error(f"Failed to send response to {chat_info['name']}")
                            
                            # Navigate back to chat list
                            go_back_to_chat_list(driver)
                        else:
                            logger.error(f"Failed to open chat with {chat_info['name']}")
                    else:
                        logger.info("No trigger words detected in message")
                        
                except Exception as e:
                    logger.error(f"Error processing unread chat: {e}")
                    logger.error(traceback.format_exc())
                    try:
                        # Try to return to chat list if we got stuck somewhere
                        go_back_to_chat_list(driver)
                    except:
                        pass
            
            # Limit the size of responded_chats
            if len(responded_chats) > MAX_RESPONDED_CHATS:
                logger.info(f"Trimming responded_chats from {len(responded_chats)} to {MAX_RESPONDED_CHATS}")
                responded_chats = set(list(responded_chats)[-MAX_RESPONDED_CHATS:])
                save_responded_chats(responded_chats)
            
            # Watchdog to detect if we're stuck
            current_time = time.time()
            if current_time - last_activity_time > WATCHDOG_TIMEOUT:
                logger.warning(f"No activity for {WATCHDOG_TIMEOUT//60} minutes, refreshing page")
                driver.refresh()
                time.sleep(10)
                last_activity_time = current_time
            
            # Wait before next scan
            time.sleep(5)
            
        except WebDriverException as e:
            logger.error(f"WebDriver exception: {e}")
            logger.error(traceback.format_exc())
            # Try to recover from WebDriver errors
            try:
                driver.refresh()
                time.sleep(10)
            except:
                logger.critical("Failed to recover from WebDriver exception")
                break
        except Exception as e:
            logger.error(f"Unexpected error during scan: {e}")
            logger.error(traceback.format_exc())
            time.sleep(5)

def main():
    """Main function with improved error handling and recovery."""
    driver = None
    max_restarts = 3
    restart_count = 0
    
    while restart_count < max_restarts:
        try:
            # Initialize WebDriver
            if driver is None:
                driver = setup_driver()
            
            # Open WhatsApp Web
            driver.get("https://web.whatsapp.com/")
            logger.info("Please scan the QR code with your phone if prompted.")
            
            # Wait for WhatsApp to load with increased timeout
            wait_seconds = 90
            logger.info(f"Waiting up to {wait_seconds} seconds for WhatsApp Web to load...")
            wait_element = wait_for_element(
                driver, 
                By.XPATH, 
                '//div[@id="pane-side"]', 
                timeout=wait_seconds,
                condition="presence"
            )
            
            if not wait_element:
                logger.error("Failed to load WhatsApp Web in the expected time")
                logger.info("Taking a screenshot for debugging...")
                try:
                    driver.save_screenshot(f"whatsapp_load_failure_{int(time.time())}.png")
                except:
                    logger.error("Failed to save screenshot")
                
                if restart_count < max_restarts - 1:
                    restart_count += 1
                    logger.info(f"Attempting restart ({restart_count}/{max_restarts})")
                    try:
                        driver.quit()
                    except:
                        pass
                    driver = None
                    continue
                else:
                    logger.critical("Exceeded maximum restart attempts. Exiting.")
                    break
            
            logger.info("WhatsApp Web is ready!")
            
            # Start monitoring and responding
            monitor_and_respond(driver)
            
        except KeyboardInterrupt:
            logger.info("Program terminated by user.")
            break
        except Exception as e:
            logger.critical(f"Critical error: {e}")
            logger.critical(traceback.format_exc())
            
            if restart_count < max_restarts - 1:
                restart_count += 1
                logger.info(f"Attempting restart ({restart_count}/{max_restarts}) after critical error")
                try:
                    if driver:
                        driver.quit()
                except:
                    pass
                driver = None
                time.sleep(10)  # Wait before restarting
            else:
                logger.critical("Exceeded maximum restart attempts. Exiting.")
                break
        finally:
            if driver:
                try:
                    driver.quit()
                except:
                    pass

if __name__ == "__main__":
    main()