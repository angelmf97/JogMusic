import socket

# Set up the UDP server
server_ip = "192.168.203.72"  # Replace with your computer's IP address if different
server_port = 12345  # Must match the port used in the phone's code

# Create the socket
sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
sock.bind((server_ip, server_port))

print(f"Listening for data on {server_ip}:{server_port}...")

try:
    while True:
        # Receive data from the phone
        data, addr = sock.recvfrom(1024)  # Buffer size is 1024 bytes
        accelerometer_data = data.decode('utf-8')  # Decode byte data to string
        #print(f"Received data from {addr}: {accelerometer_data}")
except KeyboardInterrupt:
    print("Server stopped.")
finally:
    sock.close()
