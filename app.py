from flask import Flask, request, render_template, redirect, url_for, flash, jsonify
import requests
import json
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime
import os

app = Flask(__name__)
app.secret_key = 'your_secret_key'  # Required for flashing messages

# File to store tokens
token_file = "tokens.json"

# Ensure the tokens file exists
if not os.path.exists(token_file):
    with open(token_file, "w") as file:
        json.dump({}, file)

# Load tokens from file
def load_tokens():
    if os.path.exists(token_file):
        try:
            with open(token_file, "r") as file:
                return json.load(file)
        except json.JSONDecodeError:
            # If the file is empty or contains invalid JSON, return an empty dictionary
            return {}
    return {}

# Save tokens to file
def save_tokens(tokens):
    with open(token_file, "w") as file:
        json.dump(tokens, file, indent=4)

# Function to validate root password
def validate_password(password):
    if (
        len(password) >= 14
        and any(c.islower() for c in password)
        and any(c.isupper() for c in password)
        and sum(c in "!@#$%^&*()-_+=<>?/" for c in password) >= 2
    ):
        return True
    return False

# Function to create a Linode instance
def create_linode_instance(instance_number, results, image, region, instance_type, root_password, token):
    timestamp = datetime.now().strftime("%Y%m%d%H%M%S")
    label = f"{region}-{instance_type}-{instance_number}-{timestamp}"
    data = {
        "image": image,
        "private_ip": False,
        "region": region,
        "type": instance_type,
        "label": label,
        "root_pass": root_password
    }
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {token}"
    }
    response = requests.post("https://api.linode.com/v4/linode/instances", headers=headers, data=json.dumps(data))
    if response.status_code == 200 or response.status_code == 201:
        instance_data = response.json()
        results.append(instance_data.get("ipv4", [])[0])
    else:
        flash(f"Failed to create Linode instance {instance_number}: {response.json()}")

# Function to delete a Linode instance
def delete_linode_instance(instance_id, token):
    url = f"https://api.linode.com/v4/linode/instances/{instance_id}"
    headers = {
        "Authorization": f"Bearer {token}"
    }
    response = requests.delete(url, headers=headers)
    if response.status_code == 200 or response.status_code == 204:
        flash(f"Linode instance {instance_id} deleted successfully.")
    else:
        flash(f"Failed to delete Linode instance {instance_id}: {response.json()}")

# Function to list all Linode instances
def list_linode_instances(token):
    url = "https://api.linode.com/v4/linode/instances"
    headers = {
        "Authorization": f"Bearer {token}"
    }
    response = requests.get(url, headers=headers)
    if response.status_code == 200:
        return response.json().get("data", [])
    else:
        flash(f"Failed to retrieve Linode instances: {response.json()}")
        return []

# Save IPs to a text file
def save_ips_to_file(ips, region, instance_type):
    with open("created_ips.txt", "a") as file:
        file.write(f"{region}, {instance_type}, {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
        file.write(", ".join(ips) + "\n")

@app.route("/")
def index():
    tokens = load_tokens()
    return render_template("index.html", tokens=tokens)

@app.route("/add_token", methods=["POST"])
def add_token():
    account_name = request.form.get("account_name")
    token = request.form.get("token")
    tokens = load_tokens()
    tokens[account_name] = token
    save_tokens(tokens)
    flash("Token added successfully.")
    return redirect(url_for("index"))

@app.route("/create_instances", methods=["POST"])
def create_instances():
    token = request.form.get("token")
    num_instances = int(request.form.get("num_instances"))
    image = request.form.get("image")
    region = request.form.get("region")
    instance_type = request.form.get("instance_type")
    root_password = request.form.get("root_password")

    if not validate_password(root_password):
        flash("Invalid password. Please try again.")
        return redirect(url_for("index"))

    ips = []
    with ThreadPoolExecutor() as executor:
        futures = [
            executor.submit(create_linode_instance, i, ips, image, region, instance_type, root_password, token)
            for i in range(1, num_instances + 1)
        ]
        for future in futures:
            future.result()

    if ips:
        save_ips_to_file(ips, region, instance_type)
        flash("All instance IPs have been saved to 'created_ips.txt'.")
        flash(f"All instance IPs: {', '.join(ips)}")

    return redirect(url_for("index"))

@app.route("/delete_instances", methods=["POST"])
def delete_instances():
    token = request.form.get("token")
    instances = list_linode_instances(token)
    if not instances:
        flash("No instances found.")
        return redirect(url_for("index"))

    delete_choice = request.form.get("delete_choice")
    if delete_choice.lower() == "all":
        for instance in instances:
            delete_linode_instance(instance['id'], token)
    else:
        indices = [int(i.strip()) for i in delete_choice.split(",")]
        for idx in indices:
            if 1 <= idx <= len(instances):
                delete_linode_instance(instances[idx - 1]['id'], token)
            else:
                flash(f"Invalid choice: {idx}")

    return redirect(url_for("index"))

@app.route("/get_instances")
def get_instances():
    token = request.args.get("token")
    instances = list_linode_instances(token)
    return jsonify(instances)

#if __name__ == "__main__":
#    app.run()
