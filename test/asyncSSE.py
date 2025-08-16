import asyncio
import aiohttp
import json
import logging

# Configure console-only logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s"
)

# Local storage for events
event_data = []

# SSE server URL (replace with your actual local network URL)
SSE_URL = "http://10.0.1.50"

# Exponential backoff settings
INITIAL_DELAY = 2       # seconds
MAX_DELAY = 60          # seconds
BACKOFF_FACTOR = 2

# Alerting settings
FAILURE_ALERT_THRESHOLD = 5
failure_count = 0

async def send_alert(message: str):
    # Placeholder for real alerting (email, webhook, etc.)
    logging.critical(f"ALERT: {message}")

async def listen_to_sse():
    global failure_count
    logging.info("Starting SSE listener...")
    delay = INITIAL_DELAY

    while True:
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(SSE_URL) as response:
                    if response.status != 200:
                        raise aiohttp.ClientError(f"Status code: {response.status}")

                    logging.info("Connected to SSE server.")
                    delay = INITIAL_DELAY
                    failure_count = 0  # Reset on success

                    async for line in response.content:
                        if line:
                            try:
                                decoded_line = line.decode('utf-8').strip()
                                if decoded_line.startswith("data:"):
                                    json_data = decoded_line[5:].strip()
                                    parsed_data = json.loads(json_data)
                                    event_data.append(parsed_data)
                                    logging.info(f"Received event: {parsed_data}")
                            except json.JSONDecodeError as e:
                                logging.warning(f"JSON decode error: {e}")
                            except Exception as e:
                                logging.error(f"Unexpected error while parsing line: {e}")
        except (aiohttp.ClientError, asyncio.TimeoutError) as e:
            failure_count += 1
            logging.warning(f"Connection error ({failure_count}): {e}")
            if failure_count >= FAILURE_ALERT_THRESHOLD:
                await send_alert(f"{failure_count} consecutive failures to connect to SSE server.")
        except asyncio.CancelledError:
            logging.info("SSE listener cancelled.")
            break
        except Exception as e:
            logging.exception(f"Unhandled exception in SSE listener: {e}")

        logging.info(f"Reconnecting in {delay} seconds...")
        await asyncio.sleep(delay)
        delay = min(delay * BACKOFF_FACTOR, MAX_DELAY)

async def polling_loop(interval=10):
    logging.info("Starting polling loop...")
    try:
        while True:
            logging.info(f"Polling... {len(event_data)} events stored.")
            await asyncio.sleep(interval)
    except asyncio.CancelledError:
        logging.info("Polling loop cancelled.")
    except Exception as e:
        logging.exception(f"Unhandled exception in polling loop: {e}")

async def main():
    try:
        await asyncio.gather(
            listen_to_sse(),
            polling_loop()
        )
    except Exception as e:
        logging.exception(f"Unhandled exception in main: {e}")

if __name__ == "__main__":
    asyncio.run(main())
