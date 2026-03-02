wg genkey | sudo tee /etc/wireguard/server_private.key 
sudo cat /etc/wireguard/server_private.key | wg pubkey | sudo tee /etc/wireguard/server_public.key

[Interface]
Address = 10.0.0.1/24
PostUp = iptables -A FORWARD -i wg0 -j ACCEPT; iptables -t nat -A POSTROUTING -o ens5 -j MASQUERADE
PostDown = iptables -D FORWARD -i wg0 -j ACCEPT; iptables -t nat -D POSTROUTING -o ens5 -j MASQUERADE
ListenPort = 51820
# Server's private key, generated with 
# wg genkey | sudo tee /etc/wireguard/server_private.key 
PrivateKey = iCTcrqA8YDTLZBiirWWeXo3Reb7EbjdMVZSoRVEmVFg=
             

[Peer]
AllowedIPs = 10.0.0.2/32
# Client's public key, generated with wg pubkey
PublicKey = 5fbKvo8VL7FF68ds0HlbW/ibwo65X1VYcAO8nKsCrR4=


sudo wg-quick up wg0
sudo systemctl enable wg-quick@wg0
sudo wg