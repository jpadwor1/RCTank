import bluetooth

def start_server():
    # Create a Bluetooth socket
    server_socket = bluetooth.BluetoothSocket(bluetooth.RFCOMM)

    # Bind the socket to any address and a port (use port 1)
    server_socket.bind(("", 1))
    server_socket.listen(1)

    print("Waiting for connection...")

    # Accept a connection from a client
    client_socket, client_address = server_socket.accept()
    print(f"Connected to {client_address}")

    try:
        while True:
            # Receive data from the client (buffer size of 1024 bytes)
            data = client_socket.recv(1024)
            if not data:
                break
            
            # Decode and print the received data
            command = data.decode("utf-8")
            print(f"Received command: {command}")
            
            # Implement your command handling logic here
            # For example:
            if command == "forward":
                print("Moving forward")
                # Add GPIO code to move forward
            elif command == "backward":
                print("Moving backward")
                # Add GPIO code to move backward
            elif command == "left":
                print("Turning left")
                # Add GPIO code to turn left
            elif command == "right":
                print("Turning right")
                # Add GPIO code to turn right
            elif command == "stop":
                print("Stopping")
                # Add GPIO code to stop the car

    except KeyboardInterrupt:
        print("Server stopped.")

    finally:
        # Close the sockets when done
        client_socket.close()
        server_socket.close()
        print("Connections closed.")

if __name__ == "__main__":
    start_server()
