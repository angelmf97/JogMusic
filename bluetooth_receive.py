import serial
import time
import re
import queue

def main(bluetooth_queue):
    #print("AAAA", bluetooth_queue)
    print("This is working")
    # Replace '/dev/rfcomm0' with your Bluetooth device port
    bluetooth_port = '/dev/rfcomm0'
    baud_rate = 9600  # Match your Bluetooth device's baud rate

    try:
        # Initialize serial connection
        bt_connection = serial.Serial(bluetooth_port, baud_rate, timeout=1)
        print(f"Connected to Bluetooth device on {bluetooth_port} at {baud_rate} baud.")
        time.sleep(2)  # Wait for connection to stabilize
        bt_connection.reset_input_buffer()  # Clear buffer to prevent stale data
        
        print("Listening for data...")
        while True:
            if bt_connection.in_waiting > 0:
                raw_data = bt_connection.readline()
                try:
                    data = raw_data.decode('utf-8').strip()

                    match = re.search(r'\d+', data)
                    if match:
                        data = int(match.group())

                    print(f"Received: {data}")
                    bluetooth_queue.put(data)
                except UnicodeDecodeError as e:
                    print(f"Decode error: {e}")

                except Exception as e:
                    print(f"Error processing data: {e}")
    except serial.SerialException as e:
        print(f"Error connecting to Bluetooth device: {e}")
    except KeyboardInterrupt:
        print("Exiting program.")
    finally:
        if 'bt_connection' in locals() and bt_connection.is_open:
            bt_connection.close()
            print("Bluetooth connection closed.")

if __name__ == '__main__':
    bluetooth_queue = queue.Queue()
    main(bluetooth_queue)
