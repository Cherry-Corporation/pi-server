#!/bin/bash

# Define ANSI color codes for styled terminal output
GREEN="\033[1;32m"
BLUE="\033[1;34m"
YELLOW="\033[1;33m"
CYAN="\033[1;36m"
RESET="\033[0m"

# Function to print messages with color
print_colored() {
    echo -e "${2}${1}${RESET}"
}

# Function to monitor logs for a service
monitor_logs() {
    local service_name=$1
    print_colored "Monitoring logs for $service_name..." "$CYAN"
    sudo journalctl -u "$service_name" --since "1 minute ago" --no-pager -f
}

# Fetch initial logs
print_colored "Fetching latest logs for master.service..." "$YELLOW"
sudo journalctl -u master.service --since "1 minute ago" --no-pager

print_colored "Fetching latest logs for slave.service..." "$CYAN"
sudo journalctl -u slave.service --since "1 minute ago" --no-pager

# Monitor logs in real time
print_colored "Press Ctrl+C to stop monitoring logs." "$YELLOW"

# Run the log monitoring functions in the background
monitor_logs "master.service" &
monitor_logs "slave.service" &

# Wait for the user to interrupt (Ctrl+C)
wait
