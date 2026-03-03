sudo apt update
sudo apt upgrade -y
sudo apt install -y wireguard
wg genkey | sudo tee /etc/wireguard/server_private.key 
sudo cat /etc/wireguard/server_private.key | wg pubkey | sudo tee /etc/wireguard/server_public.key

# IP forwarding
sudo sysctl -w net.ipv4.ip_forward=1
sudo sysctl -p
ip route show default # display interface name (e.g., ens5) for NAT configuration

# WireGuard server configuration file
# /etc/wireguard/wg0.conf
[Interface]
Address = 10.0.0.1/24
PostUp = iptables -A FORWARD -i wg0 -j ACCEPT; iptables -t nat -A POSTROUTING -o ens5 -j MASQUERADE
PostDown = iptables -D FORWARD -i wg0 -j ACCEPT; iptables -t nat -D POSTROUTING -o ens5 -j MASQUERADE
ListenPort = 51820
# Server's private key, generated with 
# wg genkey | sudo tee /etc/wireguard/server_private.key 
PrivateKey = <AWS_PRIVATE_KEY>
             

[Peer]
AllowedIPs = 10.0.0.2/32
# Client's public key, generated with wg pubkey
PublicKey = <MAC_PUBLIC_KEY>

# Start WireGuard
sudo wg-quick up wg0
sudo systemctl enable wg-quick@wg0
sudo wg


# WireGuard client configuration file
[Interface]
PrivateKey = <MAC_PRIVATE_KEY>
Address = 10.0.0.2/32
DNS = 1.1.1.1  # Or your internal VPC DNS if needed

[Peer]
PublicKey = <AWS_PUBLIC_KEY>
Endpoint = <AWS_PUBLIC_IP>:44281
AllowedIPs = 0.0.0.0/0  # Use 0.0.0.0/0 to route ALL traffic, or 10.0.0.0/16 for just VPC
PersistentKeepalive = 25
