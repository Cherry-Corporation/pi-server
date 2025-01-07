echo "\033[1;32mRestarting master service...\033[0m"
sudo systemctl restart master.service
sleep 1
echo "\033[1;34mRestarting slave service...\033[0m"
sudo systemctl restart slave.service

sleep 1

echo -e "\033[1;33mFetching latest logs for master.service...\033[0m"
sudo journalctl -u master.service --since "1 minute ago" --no-pager

echo -e "\033[1;36mFetching latest logs for slave.service...\033[0m"
sudo journalctl -u slave.service --since "1 minute ago" --no-pager
