import socket
import time
import numpy as np
from scipy.signal import find_peaks, butter, filtfilt
import matplotlib.pyplot as plt
from matplotlib.animation import FuncAnimation
import queue

def wifi_connect():
    # Set up the UDP server
    server_ip = "192.168.22.72"  # Replace with your computer's IP address if different
    server_port = 12345  # Must match the port used in the phone's code

    # Create the socket
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.bind((server_ip, server_port))

    print(f"Listening for data on {server_ip}:{server_port}...")

    return sock

def calculate_sampling_rate(timestamps):
    """
    Calculate the sampling rate based on time intervals between received data.
    :param timestamps: List of timestamps of received data.
    :return: Estimated sampling rate in Hz.
    """
    if len(timestamps) < 2:
        return None  # Not enough data points to calculate sampling rate
    
    # Calculate intervals between timestamps
    intervals = [t2 - t1 for t1, t2 in zip(timestamps[:-1], timestamps[1:])]
    mean_interval = sum(intervals) / len(intervals)  # Average interval in seconds
    sampling_rate = 1 / mean_interval  # Convert to Hz
    return sampling_rate

def apply_low_pass_filter(data, cutoff, fs, order=3):
    """
    Apply a low-pass Butterworth filter to the data.
    :param data: The input data array.
    :param cutoff: The cutoff frequency in Hz.
    :param fs: The sampling rate in Hz.
    :param order: The filter order.
    :return: The filtered data array.
    """
    nyquist = 0.5 * fs
    normal_cutoff = cutoff / nyquist
    b, a = butter(order, normal_cutoff, btype='low', analog=False)
    return filtfilt(b, a, data)

def estimate_stride_rate(data_buffer, sampling_rate, stride_rate_threshold=30):
    """
    Estimate the stride rate from accelerometer data using peak detection.
    :param data_buffer: List of accelerometer Z-axis values.
    :param sampling_rate: Sampling rate of the accelerometer in Hz.
    :return: Stride rate in strides per minute.
    """
    if len(data_buffer) < 10:
        return None  # Not enough data to calculate stride rate
    # Convert the buffer to a NumPy array for processing
    acc_vector = [np.sqrt(np.sum(x ** 2)) - 9.8 for x in data_buffer]# Calculate the acceleration vector magnitude



    # Apply a low-pass filter to reduce noise
    filtered_data = apply_low_pass_filter(acc_vector, cutoff=3, fs=sampling_rate)
    # Find peaks in the filtered Z-axis data
    peaks, _ = find_peaks(filtered_data, height=6, distance=5)  # Adjust height and distance as needed
    # Calculate time intervals between peaks (stride times)
    if len(peaks) > 1:
        last_peaks = peaks[-5:] if len(peaks) >= 5 else peaks
        time_intervals = np.diff(last_peaks) / sampling_rate  # Convert to seconds
        mean_stride_time = np.mean(time_intervals)  # Average time per stride
        stride_rate = 60 / mean_stride_time  # Strides per minute

        # Ignore stride rates below the threshold
        if stride_rate < stride_rate_threshold:
            return None
        return stride_rate, filtered_data, peaks
    return None

# Function to update the plot
def update_plot(frame, ax, line, filtered_data, peaks):
    filtered_data = filtered_data['data']
    peaks = peaks['peaks']
    if len(filtered_data) > 0:
        # Compute the acceleration magnitude
        acc_vector = filtered_data
        line.set_ydata(acc_vector[-500:])  # Show only the latest 500 samples
        line.set_xdata(range(len(acc_vector[-500:])))  # Update x-axis

        # Clear previous peaks
        [vline.remove() for vline in ax.collections if isinstance(vline, plt.Line2D)]
        
        # Add vertical lines for detected peaks
        if peaks is not None:
            for peak in peaks:
                ax.axvline(x=peak, color='r', linestyle='--', linewidth=0.7)

        ax.relim()
        ax.autoscale_view()
    return line,


def setup_plot():
    fig, ax = plt.subplots()
    line, = ax.plot([], [], lw=2)
    ax.set_xlim(0, 500)  # Default buffer size
    ax.set_ylim(-10, 10)  # Adjust as per your expected accelerometer range
    ax.set_title('Real-Time Stride Rate Visualization')
    ax.set_xlabel('Time (samples)')
    ax.set_ylabel('Acceleration (m/s²)')
    return fig, ax, line

def main(sock, cadence_queue):
    print(cadence_queue)
    # Buffers to store data and timestamps
    data_buffer = []
    timestamps = []
    peaks = {"peaks": []}
    filtered_data = {"data": []}

    # Parameters
    buffer_size = 100  # Number of samples to keep in the buffer
    default_sampling_rate = 50  # Default sampling rate in Hz (used if dynamic calculation fails)
    stride_rate_threshold = 50  # Minimum realistic stride rate in strides per minute

    """
    # Set up the real-time plot
    fig, ax, line = setup_plot()
    ani = FuncAnimation(fig, update_plot, fargs=(ax, line, filtered_data, peaks), interval=50)
    plt.show(block=False)
    """

    try:
        i = 0
        while True:
            # Receive data from the phone
            data, addr = sock.recvfrom(1024)  # Buffer size is 1024 bytes
            accelerometer_data = data.decode('utf-8')  # Decode byte data to string

            # Record the current timestamp
            current_time = time.time()
            timestamps.append(current_time)

            # Maintain a limited buffer of timestamps
            if len(timestamps) > 100:  # Adjust buffer size if needed
                timestamps.pop(0)

            # Calculate the sampling rate dynamically
            sampling_rate = calculate_sampling_rate(timestamps)
            if not sampling_rate:
                sampling_rate = default_sampling_rate  # Use default if dynamic calculation is unavailable

            # Parse the accelerometer data (assuming it's sent as comma-separated x,y,z values)
            try:
                x, y, z = map(float, accelerometer_data.split(','))
                data_buffer.append(np.array([x, y, z]))

                # Maintain buffer size
                if len(data_buffer) > buffer_size:
                    data_buffer.pop(0)

                # Estimate stride rate if buffer is sufficiently filled
                try:
                    stride_rate, filtered_data, peaks = estimate_stride_rate(data_buffer, sampling_rate)
                    #filtered_data['data'] = filt
                    #peaks['peaks'] = p 
                    #print(stride_rate)
                    cadence_queue.put(stride_rate, timeout=1)

                except  TypeError as e:
                    #print(i, e)
                    i += 1
                    stride_rate = 0
                    cadence_queue.put(stride_rate)


            except ValueError:
                print("Invalid data format received. Skipping...")

            #plt.pause(0.01)  # Allow the plot to update in real time

            #print(f"Received data from {addr}: {accelerometer_data}")
    except KeyboardInterrupt:
        plt.plot(filtered_data)
        plt.vlines(peaks, min(filtered_data), max(filtered_data), color='r')
        plt.show()
        quit()
        print("Server stopped.")

    finally:
        sock.close()


if __name__ == '__main__':
    sock = wifi_connect()
    cadence_queue = queue.Queue()
    main(sock, cadence_queue)
