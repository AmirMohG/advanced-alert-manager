from flask import Flask, request, jsonify
import requests
import yaml
import os
import re

app = Flask(__name__)

# Load config from config.yml
def load_config():
    config_path = os.path.join(os.getcwd(), "config.yml")
    if not os.path.exists(config_path):
        raise FileNotFoundError(f"Config file not found at {config_path}")
    with open(config_path, "r") as f:
        return yaml.safe_load(f)

config = load_config()

# Send message to Telegram
def send_telegram_message(api_token, chat_id, message):
    telegram_url = f"https://api.telegram.org/bot{api_token}/sendMessage"
    payload = {"chat_id": chat_id, "text": message}
    response = requests.post(telegram_url, json=payload)
    return response

# Parse and replace variables in message templates
def parse_and_replace(message_template, source):
    # Find all placeholders in the template (e.g., %variable%)
    variables = re.findall(r"%(\w+)%", message_template)

    # Replace each placeholder with its value from the source
    for var in variables:
        value = source.get(var, f"<missing:{var}>")  # Use "<missing:var>" if key is not found
        message_template = message_template.replace(f"%{var}%", value)

    return message_template

# Process JSON and send HTTP requests or Telegram messages based on config
def process_json_and_send_requests(input_json, config):
    responses = []

    for request_config in config["requests"]:
        method = request_config["method"].upper()
        url = request_config.get("url")
        data_mappings = request_config["data"]

        # Telegram-specific configurations
        if method == "TELEGRAM":
            api_token = request_config.get("api_token")
            chat_id = request_config.get("chat_id")

            if not api_token or not chat_id:
                raise ValueError("TELEGRAM method requires 'api_token' and 'chat_id' in config.")

        for item in input_json:
            for mapping in data_mappings:
                input_type = mapping["input"]
                message_template = mapping.get("message")
                source = item.get(input_type + "s", {})  # Use 'labels' or 'annotations'

                if method == "TELEGRAM" and message_template:
                    # Parse and replace variables in the message template
                    message = parse_and_replace(message_template, source)
                    response = send_telegram_message(api_token, chat_id, message)
                    responses.append({
                        "method": method,
                        "status_code": response.status_code,
                        "response_body": response.text,
                        "sent_data": {"message": message}
                    })

                elif method in ["POST", "GET"]:
                    # Handle POST and GET methods as usual
                    key = mapping.get("key")
                    replace_with = mapping.get("replace_with")

                    if key in source:
                        original_value = source[key]

                        if replace_with:
                            source[replace_with] = original_value
                            del source[key]

                        if method == "POST":
                            request_body = {replace_with: original_value}
                            response = requests.post(url, json=request_body)
                        elif method == "GET":
                            params = {replace_with: original_value}
                            response = requests.get(url, params=params)

                        responses.append({
                            "method": method,
                            "url": url,
                            "status_code": response.status_code,
                            "response_body": response.text,
                            "sent_data": {
                                "key": replace_with,
                                "original_value": original_value
                            }
                        })

    return responses

# Flask route to accept POST requests
@app.route("/api/v2/alerts", methods=["POST"])
def process_route():
    try:
        input_json = request.json  # Parse JSON payload
        if not input_json:
            return jsonify({"error": "Invalid JSON payload"}), 400

        # Process the JSON and send requests/messages
        results = process_json_and_send_requests(input_json, config)
        return jsonify({"results": results}), 200

    except Exception as e:
        return jsonify({"error": str(e)}), 500

# Helper route to debug incoming data
@app.route("/", methods=["POST", "GET"])
def printer():
    print(request.json)
    return jsonify({"results": request.json}), 200

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8080)
